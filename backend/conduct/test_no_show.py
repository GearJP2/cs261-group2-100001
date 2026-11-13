"""US14 No-show report API, threshold, credit ledger and constraints on PostgreSQL."""

import importlib
import json
import os
from datetime import timedelta
from unittest.mock import patch

from accounts.models import UserProfile
from accounts.test_support import force_university_login
from config import settings as settings_module
from django.db import IntegrityError, transaction
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from parties.models import Party, PartyMembership
from parties.services import PartyError

from .models import ConductCreditEvent, NoShowReport, PartyReview
from .policy import CREDIT_BASE, NO_SHOW_DEDUCTION, REPORT_WINDOW_DAYS, required_reporters
from .services import apply_credit_event, submit_no_show_report
from .test_reviews import ReviewFixture

DEDUCTION_KIND = ConductCreditEvent.Kind.NO_SHOW_DEDUCTION


class NoShowFixture(ReviewFixture):
    def no_show_url(self, party=None):
        return reverse("party-no-show-report-create", args=[(party or self.party).pk])

    def report(self, reporter=None, reported=None, party=None):
        force_university_login(self.client, reporter or self.host)
        return self.client.post(
            self.no_show_url(party),
            {"reported_id": (reported or self.member).pk},
            content_type="application/json",
        )

    def report_ok(self, reporter=None, reported=None, party=None):
        response = self.report(reporter, reported, party)
        self.assertEqual(response.status_code, 201, response.content)
        return response

    def crowded_party(self, extra_members):
        """A completed party of host, reported member and this many other members."""
        others = [self.make_user(f"ns_member_{i}", f"สมาชิก {i}") for i in range(extra_members)]
        party = self.make_party(members=[self.member, *others])
        self.complete(party)
        return party, others

    def credit(self, user=None):
        return UserProfile.objects.get(user=user or self.member).credit_score

    def assert_nothing_stored(self):
        self.assertEqual(NoShowReport.objects.count(), 0)
        self.assertEqual(ConductCreditEvent.objects.count(), 0)
        self.assertFalse(UserProfile.objects.exclude(credit_score=None).exists())


class NoShowFlagDefaultTests(SimpleTestCase):
    def read_flag(self, **environ):
        try:
            with patch.dict(os.environ, environ):
                if not environ:
                    os.environ.pop("NO_SHOW_ENABLED", None)
                return importlib.reload(settings_module).NO_SHOW_ENABLED
        finally:
            importlib.reload(settings_module)

    def test_flag_is_off_unless_the_environment_enables_it(self):
        """UT-US14-NS-02"""
        self.assertIs(self.read_flag(), False)
        self.assertIs(self.read_flag(NO_SHOW_ENABLED="false"), False)
        self.assertIs(self.read_flag(NO_SHOW_ENABLED="true"), True)


@override_settings(NO_SHOW_ENABLED=False)
class NoShowDisabledTests(NoShowFixture, TestCase):
    def assert_hidden(self, response):
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            json.loads(response.content),
            {"error": {"code": "NOT_FOUND", "message": "ไม่พบบริการที่ต้องการ"}},
        )

    def test_disabled_endpoint_is_404_without_database_access(self):
        """IT-US14-NS-01: before authentication, parsing and every query."""
        with self.assertNumQueries(0):
            self.assert_hidden(self.client.post(self.no_show_url(), "{", content_type="text/plain"))
            self.assert_hidden(self.client.get(self.no_show_url()))

    def test_disabled_endpoint_stores_nothing_for_a_valid_report(self):
        """IT-US14-NS-02"""
        self.assert_hidden(self.report())
        self.assert_nothing_stored()

    def test_csrf_middleware_still_runs_first_while_disabled(self):
        """IT-US14-NS-03: the middleware rejects a tokenless POST before the view is reached."""
        client = Client(enforce_csrf_checks=True)
        response = client.post(self.no_show_url(), "{}", content_type="application/json")
        self.assert_error(response, 403, "CSRF_FAILED")


@override_settings(NO_SHOW_ENABLED=True)
class NoShowReportTests(NoShowFixture, TestCase):
    def test_accepted_report_has_exact_response(self):
        """IT-US14-NS-04"""
        response = self.report()
        self.assertEqual(response.status_code, 201, response.content)
        report = NoShowReport.objects.get()
        self.assertEqual((report.reporter, report.reported), (self.host, self.member))
        self.assertEqual(
            json.loads(response.content),
            {
                "data": {
                    "report": {
                        "id": report.pk,
                        "party_id": self.party.pk,
                        "reported_id": self.member.pk,
                        "created_at": timezone.localtime(report.created_at).isoformat(),
                    },
                }
            },
        )
        self.assertIn("no-store", response["Cache-Control"])

    def test_response_exposes_no_login_or_contact_identifier(self):
        """IT-US14-NS-05"""
        text = self.report().content.decode()
        for private in ("review_host", "review_member", "@example.test", "email", "username"):
            self.assertNotIn(private, text)

    def test_member_can_report_host_and_host_can_be_reported(self):
        """IT-US14-NS-06"""
        self.report_ok(self.member, self.host)
        self.assertEqual(NoShowReport.objects.get().reported, self.host)

    def test_duplicate_report_is_409_and_counts_once(self):
        """IT-US14-NS-07"""
        self.report_ok()
        self.assert_error(self.report(), 409, "REPORT_EXISTS")
        self.assertEqual(NoShowReport.objects.count(), 1)
        self.assertEqual(ConductCreditEvent.objects.count(), 0)
        self.assertIsNone(self.credit())

    def test_duplicate_is_caught_outside_its_failed_savepoint(self):
        """IT-US14-NS-08: the outer transaction stays usable."""
        self.report_ok()
        with transaction.atomic():
            with self.assertRaises(PartyError) as caught:
                submit_no_show_report(
                    party_id=self.party.pk, reporter=self.host, reported_id=self.member.pk
                )
            self.assertEqual(caught.exception.code, "REPORT_EXISTS")
            self.assertEqual(NoShowReport.objects.count(), 1)

    def test_other_integrity_errors_are_not_reported_as_duplicates(self):
        """IT-US14-NS-09"""
        with patch.object(NoShowReport.objects, "create", side_effect=IntegrityError("other")):
            with self.assertRaises(IntegrityError):
                submit_no_show_report(
                    party_id=self.party.pk, reporter=self.host, reported_id=self.member.pk
                )


@override_settings(NO_SHOW_ENABLED=True)
class NoShowThresholdTests(NoShowFixture, TestCase):
    def reach_threshold(self, party, reporters, eligible_count):
        needed = required_reporters(eligible_count)
        for reporter in reporters[: needed - 1]:
            self.report_ok(reporter, party=party)
            self.assertIsNone(self.credit())
            self.assertEqual(ConductCreditEvent.objects.count(), 0)
        self.report_ok(reporters[needed - 1], party=party)
        self.assertEqual(ConductCreditEvent.objects.filter(party=party).count(), 1)
        return reporters[needed:]

    def test_deduction_happens_exactly_at_the_threshold(self):
        """IT-US14-NS-10"""
        party, others = self.crowded_party(5)
        self.reach_threshold(party, [self.host, *others], 6)
        self.assertEqual(self.credit(), CREDIT_BASE + NO_SHOW_DEDUCTION)

    def test_ledger_event_records_the_system_deduction(self):
        """IT-US14-NS-11"""
        party, others = self.crowded_party(1)
        self.reach_threshold(party, [self.host, *others], 2)
        event = ConductCreditEvent.objects.get()
        self.assertEqual(
            (event.user, event.party, event.kind, event.delta, event.created_by),
            (self.member, party, DEDUCTION_KIND, NO_SHOW_DEDUCTION, None),
        )
        self.assertTrue(event.note)

    def test_response_is_identical_in_shape_around_the_threshold(self):
        """IT-US14-NS-57: below, crossing and after the deduction look the same to a reporter."""
        party, others = self.crowded_party(5)
        reporters = [self.host, *others]
        needed = required_reporters(len(reporters))
        self.assertGreater(needed, 1)
        self.assertGreater(len(reporters), needed)
        situations = (
            ("below threshold", reporters[0], 0),
            ("crossing threshold", reporters[needed - 1], 1),
            ("after the deduction", reporters[needed], 1),
        )
        for reporter in reporters[1 : needed - 1]:
            self.report_ok(reporter, party=party)
        for situation, reporter, events in situations:
            with self.subTest(situation=situation):
                body = json.loads(self.report_ok(reporter, party=party).content)
                self.assertEqual(ConductCreditEvent.objects.count(), events)
                self.assertEqual(set(body), {"data"})
                self.assertEqual(set(body["data"]), {"report"})
                self.assertEqual(
                    set(body["data"]["report"]), {"id", "party_id", "reported_id", "created_at"}
                )

    def test_later_reports_do_not_deduct_again(self):
        """IT-US14-NS-12"""
        party, others = self.crowded_party(5)
        for reporter in self.reach_threshold(party, [self.host, *others], 6):
            self.report_ok(reporter, party=party)
        self.assertEqual(self.credit(), CREDIT_BASE + NO_SHOW_DEDUCTION)
        self.assertEqual(ConductCreditEvent.objects.count(), 1)

    def test_single_eligible_participant_can_trigger_the_deduction(self):
        """IT-US14-NS-13: a party of only the host and the reported member."""
        party = self.make_party(members=[self.member])
        self.complete(party)
        self.reach_threshold(party, [self.host], 1)

    def test_members_who_left_before_the_end_are_not_eligible_to_count(self):
        """IT-US14-NS-14: they shrink the threshold's denominator."""
        party, others = self.crowded_party(5)
        PartyMembership.objects.filter(party=party, user__in=others[1:]).update(
            left_at=party.ends_at - timedelta(minutes=1)
        )
        self.reach_threshold(party, [self.host, others[0]], 2)

    def test_members_who_left_after_the_end_are_still_eligible(self):
        """IT-US14-NS-15"""
        party, others = self.crowded_party(5)
        PartyMembership.objects.filter(party=party, user__in=others).update(
            left_at=party.ends_at + timedelta(minutes=1)
        )
        self.reach_threshold(party, [self.host, *others], 6)

    def test_reports_about_different_users_do_not_add_up(self):
        """IT-US14-NS-16"""
        party, others = self.crowded_party(1)
        self.report_ok(self.host, self.member, party)
        self.report_ok(others[0], self.host, party)
        self.report_ok(self.member, others[0], party)
        self.assertEqual(ConductCreditEvent.objects.count(), 0)

    def test_same_user_can_be_deducted_once_in_each_party(self):
        """IT-US14-NS-17"""
        for _ in range(2):
            party = self.make_party(members=[self.member])
            self.complete(party)
            self.report_ok(self.host, party=party)
        self.assertEqual(self.credit(), CREDIT_BASE + 2 * NO_SHOW_DEDUCTION)

    def test_existing_event_prevents_a_second_deduction(self):
        """IT-US14-NS-18"""
        party = self.make_party(members=[self.member])
        self.complete(party)
        ConductCreditEvent.objects.create(
            user=self.member, party=party, kind=DEDUCTION_KIND, delta=NO_SHOW_DEDUCTION
        )
        self.report_ok(self.host, party=party)
        self.assertIsNone(self.credit())
        self.assertEqual(ConductCreditEvent.objects.count(), 1)

    def test_deduction_starts_from_an_existing_score(self):
        """IT-US14-NS-19: CREDIT_BASE is used only when credit_score is NULL."""
        party = self.make_party(members=[self.member])
        self.complete(party)
        UserProfile.objects.filter(user=self.member).update(credit_score=CREDIT_BASE + 37)
        self.report_ok(self.host, party=party)
        self.assertEqual(self.credit(), CREDIT_BASE + 37 + NO_SHOW_DEDUCTION)

    def test_deduction_does_not_touch_star_ratings_or_reviews(self):
        """IT-US14-NS-20"""
        self.assertEqual(self.submit(self.host, self.member, rating=5).status_code, 201)
        party = self.make_party(members=[self.member])
        self.complete(party)
        self.report_ok(self.host, party=party)
        self.assertEqual(self.cache(self.member), (5, 1))
        self.assertEqual(PartyReview.objects.count(), 1)
        self.assertEqual(self.credit(), CREDIT_BASE + NO_SHOW_DEDUCTION)

    def test_review_does_not_touch_credit(self):
        """IT-US14-NS-21"""
        self.assertEqual(self.submit(self.host, self.member, rating=1).status_code, 201)
        self.assertIsNone(self.credit())


@override_settings(NO_SHOW_ENABLED=True)
class ApplyCreditEventTests(NoShowFixture, TestCase):
    def apply(self, user=None, delta=NO_SHOW_DEDUCTION):
        return apply_credit_event(
            (user or self.member).pk, self.party, DEDUCTION_KIND, delta, "ทดสอบ"
        )

    def test_null_score_starts_from_base(self):
        """IT-US14-NS-22"""
        self.assertIsNotNone(self.apply())
        self.assertEqual(self.credit(), CREDIT_BASE + NO_SHOW_DEDUCTION)

    def test_unique_violation_means_already_applied(self):
        """IT-US14-NS-23: the balance changes once and the transaction stays usable."""
        with transaction.atomic():
            self.assertIsNotNone(self.apply())
            self.assertIsNone(self.apply())
            self.assertEqual(self.credit(), CREDIT_BASE + NO_SHOW_DEDUCTION)
        self.assertEqual(ConductCreditEvent.objects.count(), 1)

    def test_other_integrity_errors_are_raised(self):
        """IT-US14-NS-24"""
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.apply(delta=0)
        self.assertIsNone(self.credit())

    def test_missing_profile_is_refused(self):
        """IT-US14-NS-25"""
        legacy = self.make_user("ns_legacy")
        with self.assertRaises(PartyError) as caught:
            self.apply(legacy)
        self.assertEqual(caught.exception.code, "INVALID_INPUT")
        self.assertEqual(ConductCreditEvent.objects.count(), 0)


@override_settings(NO_SHOW_ENABLED=True)
class NoShowPartyStateTests(NoShowFixture, TestCase):
    def assert_not_completed(self, party):
        self.assert_error(self.report(party=party), 409, "PARTY_NOT_COMPLETED")
        self.assert_nothing_stored()

    def test_open_party_is_refused(self):
        """IT-US14-NS-26"""
        self.assert_not_completed(self.make_party())

    def test_full_party_is_refused(self):
        """IT-US14-NS-27"""
        party = self.make_party()
        Party.objects.filter(pk=party.pk).update(capacity=3)
        self.assert_not_completed(party)

    def test_in_progress_party_is_refused(self):
        """IT-US14-NS-28"""
        party = self.make_party()
        now = timezone.now()
        self.move_times(party, now - timedelta(hours=1), now + timedelta(hours=1))
        self.assert_not_completed(party)

    def test_cancelled_party_is_refused(self):
        """IT-US14-NS-29"""
        now = timezone.now()
        party = self.make_party()
        self.move_times(
            party,
            now - timedelta(hours=3),
            now - timedelta(hours=2),
            cancelled_at=now - timedelta(days=1),
        )
        self.assert_not_completed(party)

    def test_unknown_party_is_404(self):
        """IT-US14-NS-30"""
        force_university_login(self.client, self.host)
        for party_id in (self.party.pk + 1000, 10**30):
            with self.subTest(party_id=party_id):
                response = self.client.post(
                    reverse("party-no-show-report-create", args=[party_id]),
                    {"reported_id": self.member.pk},
                    content_type="application/json",
                )
                self.assert_error(response, 404, "NOT_FOUND")

    def submit_at(self, moment):
        with patch("conduct.services.timezone.now", return_value=moment):
            return submit_no_show_report(
                party_id=self.party.pk, reporter=self.host, reported_id=self.member.pk
            )

    def test_window_includes_its_exact_end(self):
        """IT-US14-NS-31"""
        report = self.submit_at(self.party.ends_at + timedelta(days=REPORT_WINDOW_DAYS))
        self.assertIsNotNone(report.pk)

    def test_window_includes_the_exact_party_end(self):
        """IT-US14-NS-32"""
        report = self.submit_at(self.party.ends_at)
        self.assertIsNotNone(report.pk)

    def test_report_after_the_window_is_refused(self):
        """IT-US14-NS-33"""
        with self.assertRaises(PartyError) as caught:
            self.submit_at(self.party.ends_at + timedelta(days=REPORT_WINDOW_DAYS, microseconds=1))
        self.assertEqual(caught.exception.code, "REPORT_WINDOW_CLOSED")
        self.assert_nothing_stored()

    def test_window_boundary_through_the_api(self):
        """IT-US14-NS-56: the last instant inside is 201, the next one is 409."""
        force_university_login(self.client, self.host)
        last_instant = self.party.ends_at + timedelta(days=REPORT_WINDOW_DAYS)
        body = {"reported_id": self.member.pk}
        with patch(
            "conduct.services.timezone.now", return_value=last_instant + timedelta(microseconds=1)
        ):
            response = self.client.post(self.no_show_url(), body, content_type="application/json")
        self.assert_error(response, 409, "REPORT_WINDOW_CLOSED")
        self.assert_nothing_stored()
        with patch("conduct.services.timezone.now", return_value=last_instant):
            response = self.client.post(self.no_show_url(), body, content_type="application/json")
        self.assertEqual(response.status_code, 201, response.content)

    def test_closed_window_is_409_through_the_api(self):
        """IT-US14-NS-34"""
        now = timezone.now()
        ends_at = now - timedelta(days=REPORT_WINDOW_DAYS, minutes=1)
        self.move_times(self.party, ends_at - timedelta(hours=1), ends_at)
        self.assert_error(self.report(), 409, "REPORT_WINDOW_CLOSED")
        self.assert_nothing_stored()


@override_settings(NO_SHOW_ENABLED=True)
class NoShowEligibilityTests(NoShowFixture, TestCase):
    def test_outsider_reporter_is_forbidden(self):
        """IT-US14-NS-35"""
        self.assert_error(self.report(self.outsider), 403, "FORBIDDEN")
        self.assert_nothing_stored()

    def test_reporter_who_left_before_end_is_forbidden(self):
        """IT-US14-NS-36"""
        PartyMembership.objects.filter(party=self.party, user=self.peer).update(
            left_at=self.party.ends_at - timedelta(minutes=1)
        )
        self.assert_error(self.report(self.peer), 403, "FORBIDDEN")
        self.assert_nothing_stored()

    def test_self_report_is_rejected(self):
        """IT-US14-NS-37"""
        response = self.report(self.member, self.member)
        self.assert_error(response, 400, "INVALID_INPUT", {"reported_id"})
        self.assert_nothing_stored()

    def test_every_invalid_reported_user_has_one_message(self):
        """IT-US14-NS-38: outsider, missing, left early and profile-less are indistinguishable."""
        left_early = self.make_user("ns_left", "ออกก่อน")
        PartyMembership.objects.create(
            party=self.party, user=left_early, left_at=self.party.ends_at - timedelta(minutes=1)
        )
        legacy = self.make_user("ns_legacy")
        PartyMembership.objects.create(party=self.party, user=legacy)
        force_university_login(self.client, self.host)
        bodies = []
        for reported_id in (self.outsider.pk, legacy.pk + 1000, left_early.pk, legacy.pk):
            response = self.client.post(
                self.no_show_url(), {"reported_id": reported_id}, content_type="application/json"
            )
            self.assert_error(response, 400, "INVALID_INPUT", {"reported_id"})
            bodies.append(json.loads(response.content))
        self.assertEqual([body == bodies[0] for body in bodies], [True] * 4)
        self.assert_nothing_stored()


@override_settings(NO_SHOW_ENABLED=True)
class NoShowInputTests(NoShowFixture, TestCase):
    def setUp(self):
        super().setUp()
        force_university_login(self.client, self.host)

    def post_json(self, payload):
        return self.client.post(self.no_show_url(), payload, content_type="application/json")

    def test_reported_id_must_be_an_in_range_integer(self):
        """IT-US14-NS-39"""
        pk = self.member.pk
        for value in (str(pk), float(pk), True, None, [pk], 0, -1, 2**63):
            with self.subTest(value=value):
                response = self.post_json({"reported_id": value})
                self.assert_error(response, 400, "INVALID_INPUT", {"reported_id"})
        self.assert_nothing_stored()

    def test_missing_and_unknown_fields_are_rejected(self):
        """IT-US14-NS-40"""
        self.assert_error(self.post_json({}), 400, "INVALID_INPUT", {"reported_id"})
        for field in ("reporter_id", "delta", "credit_score", "party_id"):
            with self.subTest(field=field):
                response = self.post_json({"reported_id": self.member.pk, field: 1})
                self.assert_error(response, 400, "INVALID_INPUT", {field})
        self.assert_nothing_stored()

    def test_non_json_content_type_is_rejected(self):
        """IT-US14-NS-41"""
        body = json.dumps({"reported_id": self.member.pk})
        response = self.client.post(self.no_show_url(), body, content_type="text/plain")
        self.assert_error(response, 400, "INVALID_INPUT")
        self.assert_nothing_stored()

    def test_invalid_json_and_non_objects_are_rejected(self):
        """IT-US14-NS-42"""
        for body in ("{", "", b"\xff", "[]", '"text"', "1", "null"):
            with self.subTest(body=body):
                self.assert_error(self.post_json(body), 400, "INVALID_INPUT")
        self.assert_nothing_stored()


@override_settings(NO_SHOW_ENABLED=True)
class NoShowAccessTests(NoShowFixture, TestCase):
    def post_valid(self, client=None, **extra):
        return (client or self.client).post(
            self.no_show_url(),
            {"reported_id": self.member.pk},
            content_type="application/json",
            **extra,
        )

    def test_unauthenticated_request_is_401(self):
        """IT-US14-NS-43"""
        self.assert_error(self.post_valid(), 401, "AUTH_REQUIRED")
        self.assert_nothing_stored()

    def test_session_without_university_identity_is_403(self):
        """IT-US14-NS-44"""
        self.client.force_login(self.host)
        self.assert_error(self.post_valid(), 403, "FORBIDDEN")
        self.assert_nothing_stored()

    def test_other_methods_are_405_with_allow(self):
        """IT-US14-NS-45"""
        force_university_login(self.client, self.host)
        for method in ("get", "put", "patch", "delete"):
            with self.subTest(method=method):
                response = getattr(self.client, method)(self.no_show_url())
                self.assert_error(response, 405, "METHOD_NOT_ALLOWED")
                self.assertEqual(response["Allow"], "POST")

    def test_csrf_is_enforced_by_the_middleware(self):
        """IT-US14-NS-46"""
        client = Client(enforce_csrf_checks=True)
        force_university_login(client, self.host)
        self.assert_error(self.post_valid(client), 403, "CSRF_FAILED")
        self.assert_nothing_stored()
        token = client.get(reverse("accounts:csrf")).json()["data"]["csrf_token"]
        self.assertEqual(self.post_valid(client, HTTP_X_CSRFTOKEN=token).status_code, 201)


class NoShowConstraintTests(NoShowFixture, TestCase):
    def create_report(self, **changes):
        fields = {
            "party": self.party,
            "reporter": self.host,
            "reported": self.member,
            **changes,
        }
        with transaction.atomic():
            return NoShowReport.objects.create(**fields)

    def create_event(self, **changes):
        fields = {
            "user": self.member,
            "party": self.party,
            "kind": DEDUCTION_KIND,
            "delta": NO_SHOW_DEDUCTION,
            **changes,
        }
        with transaction.atomic():
            return ConductCreditEvent.objects.create(**fields)

    def test_self_report_is_enforced_by_the_database(self):
        """IT-US14-NS-47"""
        with self.assertRaises(IntegrityError) as caught:
            self.create_report(reported=self.host)
        self.assertIn("no_show_report_not_self", str(caught.exception))

    def test_duplicate_report_is_enforced_by_the_database(self):
        """IT-US14-NS-48"""
        self.create_report()
        with self.assertRaises(IntegrityError) as caught:
            self.create_report()
        self.assertIn("unique_no_show_report", str(caught.exception))

    def test_zero_delta_is_enforced_by_the_database(self):
        """IT-US14-NS-49"""
        with self.assertRaises(IntegrityError) as caught:
            self.create_event(delta=0)
        self.assertIn("credit_event_delta_not_zero", str(caught.exception))

    def test_one_deduction_per_user_per_party_is_enforced_by_the_database(self):
        """IT-US14-NS-50"""
        self.create_event()
        with self.assertRaises(IntegrityError) as caught:
            self.create_event()
        self.assertIn("unique_conduct_credit_event", str(caught.exception))

    def test_events_without_a_party_are_not_limited(self):
        """IT-US14-NS-51: contract 3.7 keeps party NULL rows outside the unique constraint."""
        self.create_event(party=None)
        self.create_event(party=None)
        self.assertEqual(ConductCreditEvent.objects.count(), 2)

    def test_deleting_a_party_keeps_the_ledger_but_not_its_reports(self):
        """IT-US14-NS-52"""
        self.create_report()
        event = self.create_event()
        self.party.delete()
        self.assertEqual(NoShowReport.objects.count(), 0)
        event.refresh_from_db()
        self.assertIsNone(event.party_id)
