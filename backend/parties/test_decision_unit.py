"""Task56 UT-US10-API-01..06: no HTTP server or database; mock ORM and clock.

Service tests call __wrapped__ to isolate the atomic-decorated function's logic.
Transaction, SQL and lock guarantees remain covered by integration test suites.
"""

import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, SimpleTestCase

from . import services, views
from .models import JoinRequest

NOW = datetime(2030, 11, 16, 3, tzinfo=timezone.utc)


class UnitFixture(SimpleTestCase):
    def start_patch(self, name, **kwargs):
        patcher = patch(name, **kwargs)
        self.addCleanup(patcher.stop)
        return patcher.start()


class DecisionViewUnitTests(UnitFixture):
    def setUp(self):
        self.actor = SimpleNamespace(pk=1, is_authenticated=True, is_active=True)
        self.identity = self.start_patch("accounts.decorators.UniversityIdentity.objects")
        self.identity.filter.return_value.first.return_value = SimpleNamespace(pk=7)
        self.decide = self.start_patch("parties.views.decide_join_request")

    def call(self, body='{"status":"Approved"}', *, actor=None, session=None, method="POST"):
        request = RequestFactory().generic(
            method,
            "/api/v1/parties/12/join-requests/31/decision",
            body,
            content_type="application/json",
        )
        request.user = actor if actor is not None else self.actor
        request.session = {"university_identity_id": 7} if session is None else session
        return views.decide_join_request_api(request, party_id=12, request_id=31)

    def assert_error(self, response, status, code):
        self.assertEqual(response.status_code, status)
        self.assertEqual(json.loads(response.content)["error"]["code"], code)
        self.assertIn("no-store", response["Cache-Control"])

    def test_ut01_anonymous_never_calls_identity_or_mutation(self):
        self.assert_error(self.call(actor=AnonymousUser()), 401, "AUTH_REQUIRED")
        self.identity.filter.assert_not_called()
        self.decide.assert_not_called()

    def test_ut01_inactive_actor_never_calls_identity_or_mutation(self):
        self.actor.is_active = False
        self.assert_error(self.call(), 403, "ACCOUNT_INACTIVE")
        self.identity.filter.assert_not_called()
        self.decide.assert_not_called()

    def test_ut01_missing_or_invalid_university_evidence_never_calls_mutation(self):
        for identity_id in (None, True, -1, "7"):
            with self.subTest(identity_id=identity_id):
                self.assert_error(
                    self.call(session={"university_identity_id": identity_id}), 403, "FORBIDDEN"
                )
        self.identity.filter.assert_not_called()
        self.identity.filter.return_value.first.return_value = None
        self.assert_error(self.call(), 403, "FORBIDDEN")
        self.identity.filter.assert_called_once_with(
            pk=7,
            user=self.actor,
            provider_key="tu",
            student_verified_at__isnull=False,
            eligibility_checked_at__isnull=False,
        )
        self.decide.assert_not_called()

    def test_invalid_payload_never_reaches_service(self):
        for body in (
            "{",
            "[]",
            "null",
            "{}",
            '{"status":[]}',
            '{"status":{}}',
            '{"status":true}',
            '{"status":"Pending"}',
            '{"status":"Rejected","user_id":99}',
        ):
            with self.subTest(body=body):
                self.assert_error(self.call(body), 400, "INVALID_INPUT")
        self.decide.assert_not_called()

    def test_wrong_method_never_reaches_service(self):
        response = self.call(method="GET")
        self.assert_error(response, 405, "METHOD_NOT_ALLOWED")
        self.assertEqual(response["Allow"], "POST")
        self.decide.assert_not_called()

    def test_ut05_ut06_view_passes_session_actor_and_exact_decision(self):
        for status in ("Approved", "Rejected"):
            with self.subTest(status=status):
                self.decide.reset_mock()
                self.decide.return_value = SimpleNamespace(pk=31, status=status)
                response = self.call(json.dumps({"status": status}))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    json.loads(response.content), {"data": {"id": 31, "status": status}}
                )
                self.decide.assert_called_once_with(
                    party_id=12, request_id=31, user=self.actor, approved=status == "Approved"
                )

    def test_service_error_preserves_status_and_code(self):
        for status, code in ((403, "FORBIDDEN"), (404, "NOT_FOUND"), (409, "REQUEST_DECIDED")):
            with self.subTest(code=code):
                self.decide.side_effect = services.PartyError(code, "test message", status)
                self.assert_error(self.call(), status, code)


class DecisionServiceUnitTests(UnitFixture):
    def setUp(self):
        self.actor = SimpleNamespace(pk=1)
        self.party = SimpleNamespace(
            pk=12,
            host_id=1,
            capacity=2,
            cancelled_at=None,
            starts_at=NOW + timedelta(hours=1),
            ends_at=NOW + timedelta(hours=2),
            memberships=Mock(),
        )
        self.request = SimpleNamespace(
            pk=31, user_id=2, status="Pending", decided_at=None, decided_by=None, save=Mock()
        )
        self.parties = self.start_patch("parties.services.Party.objects")
        self.parties.select_for_update.return_value.get.return_value = self.party
        self.requests = self.start_patch("parties.services.JoinRequest.objects")
        self.requests.select_for_update.return_value.get.return_value = self.request
        self.members = self.start_patch("parties.services.PartyMembership.objects")
        self.members.select_for_update.return_value.filter.return_value.first.return_value = None
        self.count = self.start_patch("parties.services.count_active_members", return_value=1)
        self.clock = self.start_patch("parties.services.timezone.now", return_value=NOW)

    def decide(self, approved=True):
        return services.decide_join_request.__wrapped__(
            party_id=12, request_id=31, user=self.actor, approved=approved
        )

    def assert_no_mutation(self):
        self.request.save.assert_not_called()
        self.members.create.assert_not_called()
        self.assertEqual(self.request.status, "Pending")
        self.assertIsNone(self.request.decided_at)
        self.assertIsNone(self.request.decided_by)

    def assert_denied(self, code, status=409, approved=True):
        with self.assertRaises(services.PartyError) as raised:
            self.decide(approved)
        self.assertEqual((raised.exception.code, raised.exception.status), (code, status))

    def test_ut01_non_host_never_reads_request_or_mutates(self):
        self.actor.pk = 9
        for approved in (True, False):
            self.assert_denied("FORBIDDEN", 403, approved)
        self.requests.select_for_update.assert_not_called()
        self.members.assert_not_called()
        self.assert_no_mutation()

    def test_ut02_request_lookup_is_scoped_to_locked_party(self):
        lookup = self.requests.select_for_update.return_value.get
        lookup.side_effect = JoinRequest.DoesNotExist
        self.assert_denied("NOT_FOUND", 404)
        lookup.assert_called_once_with(pk=31, party=self.party)
        self.assert_no_mutation()
        self.members.select_for_update.assert_not_called()

    def test_ut03_decided_request_does_not_write_again(self):
        for status in ("Approved", "Rejected"):
            self.request.status = status
            for approved in (True, False):
                with self.subTest(status=status, approved=approved):
                    self.assert_denied("REQUEST_DECIDED", approved=approved)
                    self.assertEqual(self.request.status, status)
        self.request.save.assert_not_called()
        self.members.create.assert_not_called()
        self.clock.assert_not_called()

    def test_ut04_full_party_blocks_approve(self):
        self.count.return_value = 2
        self.assert_denied("PARTY_FULL")
        self.assert_no_mutation()

    def test_ut04_cancelled_started_completed_and_exact_start_block_decisions(self):
        for starts, ends, cancelled, code in (
            (NOW + timedelta(hours=1), NOW + timedelta(hours=2), NOW, "PARTY_CANCELLED"),
            (NOW, NOW + timedelta(hours=1), None, "PARTY_STARTED"),
            (NOW - timedelta(hours=1), NOW + timedelta(hours=1), None, "PARTY_STARTED"),
            (NOW - timedelta(hours=2), NOW, None, "PARTY_STARTED"),
        ):
            self.party.starts_at, self.party.ends_at, self.party.cancelled_at = (
                starts,
                ends,
                cancelled,
            )
            for approved in (True, False):
                with self.subTest(starts=starts, ends=ends, approved=approved):
                    self.assert_denied(code, approved=approved)
                    self.assert_no_mutation()

    def test_ut05_approve_creates_member_and_records_host_and_time(self):
        result = self.decide()
        self.assertIs(result, self.request)
        self.members.create.assert_called_once_with(party=self.party, user_id=2)
        self.assertEqual(
            (result.status, result.decided_at, result.decided_by), ("Approved", NOW, self.actor)
        )
        result.save.assert_called_once_with(update_fields=["status", "decided_at", "decided_by"])

    def test_ut05_approve_reactivates_existing_membership(self):
        member = SimpleNamespace(left_at=NOW - timedelta(days=1), save=Mock())
        self.members.select_for_update.return_value.filter.return_value.first.return_value = member
        self.decide()
        self.assertIsNone(member.left_at)
        member.save.assert_called_once_with(update_fields=["left_at"])
        self.members.create.assert_not_called()
        self.assertEqual(self.request.status, "Approved")

    def test_ut05_active_member_cannot_be_approved(self):
        member = SimpleNamespace(left_at=None, save=Mock())
        self.members.select_for_update.return_value.filter.return_value.first.return_value = member
        self.assert_denied("ALREADY_MEMBER")
        member.save.assert_not_called()
        self.assert_no_mutation()

    def test_ut06_reject_full_party_changes_only_decision(self):
        self.count.return_value = 2
        self.decide(False)
        self.assertEqual(
            (self.request.status, self.request.decided_at, self.request.decided_by),
            ("Rejected", NOW, self.actor),
        )
        self.request.save.assert_called_once_with(
            update_fields=["status", "decided_at", "decided_by"]
        )
        self.assertEqual(self.members.mock_calls, [])
        self.assertEqual(self.party.capacity, 2)

    def test_ut06_reapplication_reuses_rejected_row_and_clears_decision(self):
        self.actor.pk = 2
        self.request.status = "Rejected"
        self.request.decided_by = SimpleNamespace(pk=1)
        self.request.decided_at = NOW - timedelta(minutes=5)
        self.party.memberships.filter.return_value.first.return_value = None
        self.requests.select_for_update.return_value.get_or_create.return_value = (
            self.request,
            False,
        )
        result = services.submit_join_request.__wrapped__(party_id=12, user=self.actor)
        self.assertIs(result, self.request)
        self.assertEqual(result.status, "Pending")
        self.assertEqual(result.created_at, NOW)
        self.assertIsNone(result.decided_at)
        self.assertIsNone(result.decided_by)
        self.request.save.assert_called_once_with(
            update_fields=["status", "created_at", "decided_at", "decided_by"]
        )
        self.assertEqual(self.members.mock_calls, [])

    def test_ut06_full_party_blocks_reapplication_before_request_write(self):
        self.actor.pk = 2
        self.count.return_value = 2
        with self.assertRaises(services.JoinRequestError) as raised:
            services.submit_join_request.__wrapped__(party_id=12, user=self.actor)
        self.assertEqual(raised.exception.code, "PARTY_FULL")
        self.requests.select_for_update.assert_not_called()
        self.assert_no_mutation()
