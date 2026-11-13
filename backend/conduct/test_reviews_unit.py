"""US14 review rules in isolation: no database, HTTP client or real clock.

The behaviour on PostgreSQL is covered by test_reviews.py, test_review_list.py and
test_reviews_concurrency.py. SimpleTestCase refuses any query, so a mock that misses an
ORM entry point fails the test instead of reaching a database.
"""

import inspect
import json
import unittest
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import F, Q
from django.test import RequestFactory, SimpleTestCase
from parties.services import PartyError

from . import views
from .services import average_rating, is_participant, submit_review
from .views import comment_error, reviewer_display_name, validate_review_payload

PARTY_ID = 7
HOST_ID = 10
MEMBER_ID = 20
PEER_ID = 30
NOW = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)
ENDS_AT = NOW - timedelta(hours=2)
CREATED_AT = datetime(2026, 10, 1, 5, 0, tzinfo=UTC)
CREATED_AT_LOCAL = "2026-10-01T12:00:00+07:00"

SUMMARY_KEYS = {
    "user_id",
    "average_rating",
    "rating_count",
    "reviews",
    "page",
    "page_size",
    "total",
}
LIST_REVIEW_KEYS = {"id", "rating", "comment", "reviewer", "created_at"}
CREATED_REVIEW_KEYS = {
    "id",
    "party_id",
    "reviewer",
    "reviewee_id",
    "rating",
    "comment",
    "created_at",
}


class SubmitReviewUnitBase(SimpleTestCase):
    """Replace every collaborator of submit_review; each test states one departure."""

    def setUp(self):
        super().setUp()
        self.party = SimpleNamespace(pk=PARTY_ID, host_id=HOST_ID, ends_at=ENDS_AT)
        self.reviewer = SimpleNamespace(pk=HOST_ID)
        # The transaction itself needs a connection; rollback is proved by IT-US14-DB-18.
        self.start(patch.object(transaction.Atomic, "__enter__", return_value=None))
        self.start(patch.object(transaction.Atomic, "__exit__", return_value=False))
        self.now = self.start(patch("conduct.services.timezone.now", return_value=NOW))
        self.state = self.start(patch("conduct.services.get_party_state", return_value="Completed"))
        self.participant = self.start(patch("conduct.services.is_participant", return_value=True))
        self.review_model = self.start(patch("conduct.services.PartyReview"))
        self.profile_model = self.start(patch("conduct.services.UserProfile"))
        self.party_model = self.start(patch("conduct.services.Party"))
        self.party_model.DoesNotExist = type("DoesNotExist", (Exception,), {})
        self.lock = self.party_model.objects.select_for_update.return_value.get
        self.lock.return_value = self.party
        self.create = self.review_model.objects.create
        self.cache_update = self.profile_model.objects.filter.return_value.update
        self.cache_update.return_value = 1

    def start(self, patcher):
        self.addCleanup(patcher.stop)
        return patcher.start()

    def submit(self, reviewee_id=MEMBER_ID, rating=4):
        return submit_review(
            party_id=PARTY_ID,
            reviewer=self.reviewer,
            reviewee_id=reviewee_id,
            rating=rating,
            comment="เล่นสนุกมาก",
        )

    def assert_refused(self, code, status, fields=None, **submit_changes):
        with self.assertRaises(PartyError) as caught:
            self.submit(**submit_changes)
        self.assertEqual((caught.exception.code, caught.exception.status), (code, status))
        self.assertEqual(caught.exception.fields and set(caught.exception.fields), fields)

    def assert_no_mutation(self):
        self.create.assert_not_called()
        self.profile_model.objects.filter.assert_not_called()
        self.cache_update.assert_not_called()


class EligibilityUnitTests(SubmitReviewUnitBase):
    def test_party_that_is_not_completed_is_refused_before_any_other_check(self):
        """UT-US14-API-01"""
        for state in ("Open", "Full", "InProgress", "Cancelled"):
            with self.subTest(state=state):
                self.state.return_value = state
                self.assert_refused("PARTY_NOT_COMPLETED", 409)
                self.state.assert_called_with(self.party, NOW)
        self.participant.assert_not_called()
        self.assert_no_mutation()

    def test_clock_is_read_only_after_the_party_lock(self):
        """UT-US14-API-01: a request waiting on the lock may cross ends_at."""

        def read_clock():
            self.lock.assert_called_once_with(pk=PARTY_ID)
            return NOW

        self.now.side_effect = read_clock
        self.submit()
        self.now.assert_called_once_with()

    def test_unknown_party_is_not_found(self):
        """UT-US14-API-01"""
        self.lock.side_effect = self.party_model.DoesNotExist
        self.assert_refused("NOT_FOUND", 404)
        self.state.assert_not_called()
        self.assert_no_mutation()

    def test_reviewer_without_participation_history_is_forbidden(self):
        """UT-US14-API-01"""
        self.participant.return_value = False
        self.assert_refused("FORBIDDEN", 403)
        self.participant.assert_called_once_with(self.party, HOST_ID)
        self.assert_no_mutation()

    def test_reviewee_who_is_not_a_participant_is_invalid_input(self):
        """UT-US14-API-01"""
        self.participant.side_effect = [True, False]
        self.assert_refused("INVALID_INPUT", 400, {"reviewee_id"})
        self.assertEqual(
            self.participant.call_args_list,
            [call(self.party, HOST_ID), call(self.party, MEMBER_ID)],
        )
        self.assert_no_mutation()

    def test_reviewee_without_rating_cache_is_refused_as_invalid_input(self):
        """UT-US14-API-01: raising is what rolls the insert back (IT-US14-DB-18)."""
        self.cache_update.return_value = 0
        self.assert_refused("INVALID_INPUT", 400, {"reviewee_id"})

    def test_eligible_review_is_created_and_counted_once(self):
        """UT-US14-API-01"""
        self.assertIs(self.submit(rating=4), self.create.return_value)
        self.create.assert_called_once_with(
            party=self.party,
            reviewer=self.reviewer,
            reviewee_id=MEMBER_ID,
            rating=4,
            comment="เล่นสนุกมาก",
        )
        self.profile_model.objects.filter.assert_called_once_with(user_id=MEMBER_ID)
        self.cache_update.assert_called_once_with(
            rating_sum=F("rating_sum") + 4,
            rating_count=F("rating_count") + 1,
        )


class FakeMemberships:
    """Evaluate the real Q that is_participant builds against in-memory rows."""

    def __init__(self, *rows):
        self.rows = [SimpleNamespace(user_id=user_id, left_at=left_at) for user_id, left_at in rows]
        self.filter = Mock(side_effect=self.apply)

    def apply(self, *conditions, **lookups):
        wanted = [*conditions, *lookups.items()]
        found = any(all(self.matches(item, row) for item in wanted) for row in self.rows)
        return Mock(exists=Mock(return_value=found))

    def matches(self, condition, row):
        if isinstance(condition, Q):
            results = [self.matches(child, row) for child in condition.children]
            result = any(results) if condition.connector == Q.OR else all(results)
            return not result if condition.negated else result
        lookup, expected = condition
        if lookup == "user_id":
            return row.user_id == expected
        if lookup == "left_at__isnull":
            return (row.left_at is None) is expected
        if lookup == "left_at__gte":
            return row.left_at is not None and row.left_at >= expected
        raise AssertionError(f"Unexpected lookup: {lookup}")


class IsParticipantUnitTests(SimpleTestCase):
    def check(self, *rows, user_id=MEMBER_ID):
        memberships = FakeMemberships(*rows)
        party = SimpleNamespace(host_id=HOST_ID, ends_at=ENDS_AT, memberships=memberships)
        return is_participant(party, user_id), memberships

    def test_host_is_a_participant_without_querying_memberships(self):
        """UT-US14-API-01"""
        result, memberships = self.check(user_id=HOST_ID)
        self.assertIs(result, True)
        memberships.filter.assert_not_called()

    def test_member_who_left_before_the_end_is_not_a_participant(self):
        """UT-US14-API-01"""
        result, memberships = self.check((MEMBER_ID, ENDS_AT - timedelta(seconds=1)))
        self.assertIs(result, False)
        memberships.filter.assert_called_once()

    def test_member_who_left_exactly_at_the_end_is_a_participant(self):
        """UT-US14-API-01"""
        self.assertIs(self.check((MEMBER_ID, ENDS_AT))[0], True)

    def test_member_who_left_after_the_end_is_a_participant(self):
        """UT-US14-API-01"""
        self.assertIs(self.check((MEMBER_ID, ENDS_AT + timedelta(seconds=1)))[0], True)

    def test_member_who_never_left_is_a_participant(self):
        """UT-US14-API-01"""
        self.assertIs(self.check((MEMBER_ID, None))[0], True)

    def test_user_without_own_membership_is_not_a_participant(self):
        """UT-US14-API-01: another member's row must not count."""
        self.assertIs(self.check()[0], False)
        self.assertIs(self.check((PEER_ID, None))[0], False)


class SelfReviewUnitTests(SubmitReviewUnitBase):
    def test_self_review_is_invalid_input_without_any_mutation(self):
        """UT-US14-API-02"""
        self.assert_refused("INVALID_INPUT", 400, {"reviewee_id"}, reviewee_id=HOST_ID)
        self.participant.assert_called_once_with(self.party, HOST_ID)
        self.assert_no_mutation()


class ReviewPayloadUnitTests(SimpleTestCase):
    def errors(self, **changes):
        return validate_review_payload(
            {"reviewee_id": MEMBER_ID, "rating": 4, "comment": "เล่นดี", **changes}
        )

    def test_rating_values_inside_the_range_are_accepted(self):
        """UT-US14-API-03"""
        for rating in (1, 2, 3, 4, 5):
            with self.subTest(rating=rating):
                self.assertEqual(self.errors(rating=rating), {})

    def test_rating_outside_the_range_or_of_another_type_is_rejected(self):
        """UT-US14-API-03"""
        for rating in (0, 6, -1, True, False, "5", 5.0, None, [5]):
            with self.subTest(rating=rating):
                self.assertEqual(set(self.errors(rating=rating)), {"rating"})

    def test_missing_fields_are_reported(self):
        """UT-US14-API-03"""
        for field in ("reviewee_id", "rating", "comment"):
            with self.subTest(field=field):
                payload = {"reviewee_id": MEMBER_ID, "rating": 4, "comment": "เล่นดี"}
                del payload[field]
                self.assertEqual(set(validate_review_payload(payload)), {field})

    def test_comment_within_the_limit_is_accepted(self):
        """UT-US14-API-03: the limit counts characters after stripping."""
        for comment in ("ดี", "ก" * 500, f"  {'ก' * 500}  "):
            with self.subTest(length=len(comment)):
                self.assertIsNone(comment_error(comment))
                self.assertEqual(self.errors(comment=comment), {})

    def test_invalid_comment_is_rejected(self):
        """UT-US14-API-03"""
        invalid = {
            "empty": "",
            "whitespace": "  \n\t",
            "501 characters": "ก" * 501,
            "integer": 5,
            "null": None,
            "list": ["ดี"],
            "NUL": "ดี\x00มาก",
            "only NUL": "\x00",
            "lone surrogate": "ดี\ud800",
        }
        for name, comment in invalid.items():
            with self.subTest(name):
                self.assertIsNotNone(comment_error(comment))
                self.assertEqual(set(self.errors(comment=comment)), {"comment"})

    def test_view_applies_the_validator_before_calling_the_service(self):
        """UT-US14-API-03"""
        view = inspect.unwrap(views.create_review)
        cases = (
            ({"reviewee_id": MEMBER_ID, "rating": 0, "comment": "ดี"}, {"rating"}),
            ({"reviewee_id": MEMBER_ID, "rating": 4, "comment": " "}, {"comment"}),
        )
        with patch("conduct.views.submit_review") as service:
            for payload, fields in cases:
                with self.subTest(fields=fields):
                    request = RequestFactory().post(
                        "/", json.dumps(payload), content_type="application/json"
                    )
                    request.user = SimpleNamespace(pk=HOST_ID)
                    response = view(request, PARTY_ID)
                    self.assertEqual(response.status_code, 400)
                    error = json.loads(response.content)["error"]
                    self.assertEqual(error["code"], "INVALID_INPUT")
                    self.assertEqual(set(error["fields"]), fields)
        service.assert_not_called()


class DuplicateReviewUnitTests(SubmitReviewUnitBase):
    def test_unique_conflict_is_review_exists_and_the_cache_is_untouched(self):
        """UT-US14-API-04"""
        self.create.side_effect = IntegrityError(
            'duplicate key value violates unique constraint "unique_party_review"'
        )
        self.assert_refused("REVIEW_EXISTS", 409)
        self.create.assert_called_once()
        self.profile_model.objects.filter.assert_not_called()
        self.cache_update.assert_not_called()

    def test_other_integrity_error_is_raised_unchanged(self):
        """UT-US14-API-04"""
        error = IntegrityError('violates check constraint "party_review_rating_1_to_5"')
        self.create.side_effect = error
        with self.assertRaises(IntegrityError) as caught:
            self.submit()
        self.assertIs(caught.exception, error)
        self.profile_model.objects.filter.assert_not_called()
        self.cache_update.assert_not_called()


class GuardedProfile:
    """A rating cache whose conduct credit fails the test when read or written."""

    def __init__(self, rating_sum, rating_count, user_id=MEMBER_ID):
        self.rating_sum = rating_sum
        self.rating_count = rating_count
        self.user_id = user_id

    @property
    def credit_score(self):
        raise AssertionError("credit_score was read")

    @credit_score.setter
    def credit_score(self, value):
        raise AssertionError("credit_score was written")


class AverageRatingUnitTests(SimpleTestCase):
    def test_no_reviews_is_none_not_zero(self):
        """UT-US14-API-05"""
        self.assertIsNone(average_rating(GuardedProfile(0, 0)))

    def test_average_is_rounded_to_two_decimals(self):
        """UT-US14-API-05"""
        cases = (
            ("one review", 5, 1, 5.0),
            ("lowest star", 1, 1, 1.0),
            ("5 + 4", 9, 2, 4.5),
            ("5 + 4 + 4 rounds down", 13, 3, 4.33),
            ("5 + 5 + 4 rounds up", 14, 3, 4.67),
        )
        for name, rating_sum, rating_count, expected in cases:
            with self.subTest(name):
                self.assertEqual(average_rating(GuardedProfile(rating_sum, rating_count)), expected)

    def test_large_counts_stay_exact_within_the_integer_columns(self):
        """UT-US14-API-05"""
        cases = (
            (2_000_000_000, 500_000_000, 4.0),
            (1_300_000_000, 300_000_000, 4.33),
            (2_147_483_647, 500_000_000, 4.29),
        )
        for rating_sum, rating_count, expected in cases:
            with self.subTest(rating_count=rating_count):
                self.assertEqual(average_rating(GuardedProfile(rating_sum, rating_count)), expected)

    def test_summary_view_never_reads_or_changes_credit_score(self):
        """UT-US14-API-05: GuardedProfile raises on any credit_score access."""
        profile = GuardedProfile(9, 2)
        view = inspect.unwrap(views.user_reviews)
        with patch("conduct.views.list_reviews", return_value=(profile, [], 0)):
            response = view(RequestFactory().get("/"), MEMBER_ID)
        self.assertEqual(json.loads(response.content)["data"]["average_rating"], 4.5)
        self.assertEqual((profile.rating_sum, profile.rating_count), (9, 2))


class SubmitLeavesCreditUnitTests(SubmitReviewUnitBase):
    def test_submit_updates_only_the_rating_cache_columns(self):
        """UT-US14-API-05"""
        self.submit()
        self.assertEqual(set(self.cache_update.call_args.kwargs), {"rating_sum", "rating_count"})


class ReviewSerializerUnitTests(SimpleTestCase):
    """The serializers are inline in the views, so they are read through the raw view."""

    PRIVATE_VALUES = ("secret-login", "secret@example.test", "6509999999", "424242", "434343")
    PRIVATE_NAMES = ("email", "username", "student", "party", "reviewer_id", "credit")

    def reviewer(self, **changes):
        return SimpleNamespace(
            pk=424242,
            username="secret-login",
            email="secret@example.test",
            student_id="6509999999",
            **changes,
        )

    def source_review(self, reviewer):
        return SimpleNamespace(
            pk=11,
            party_id=434343,
            reviewer_id=reviewer.pk,
            reviewee_id=MEMBER_ID,
            reviewer=reviewer,
            rating=5,
            comment="ตรงเวลา",
            created_at=CREATED_AT,
        )

    def read(self, profile, rows):
        view = inspect.unwrap(views.user_reviews)
        with patch("conduct.views.list_reviews", return_value=(profile, rows, len(rows))):
            response = view(RequestFactory().get("/"), MEMBER_ID)
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def test_list_response_is_exactly_the_public_allowlist(self):
        """UT-US14-API-06: private attributes on the source objects never reach the body."""
        reviewer = self.reviewer(profile=SimpleNamespace(display_name="ผู้จัด", credit_score=75))
        profile = SimpleNamespace(
            user_id=MEMBER_ID,
            rating_sum=5,
            rating_count=1,
            credit_score=75,
            student_id="6509999999",
            display_name="สมาชิก",
        )
        text = self.read(profile, [self.source_review(reviewer)])
        body = json.loads(text)
        self.assertEqual(set(body), {"data"})
        self.assertEqual(set(body["data"]), SUMMARY_KEYS)
        self.assertEqual(set(body["data"]["reviews"][0]), LIST_REVIEW_KEYS)
        self.assertEqual(
            body["data"]["reviews"][0],
            {
                "id": 11,
                "rating": 5,
                "comment": "ตรงเวลา",
                "reviewer": {"display_name": "ผู้จัด"},
                "created_at": CREATED_AT_LOCAL,
            },
        )
        for private in (*self.PRIVATE_VALUES, *self.PRIVATE_NAMES):
            with self.subTest(private=private):
                self.assertNotIn(private, text)

    def test_empty_summary_reports_null_average(self):
        """UT-US14-API-06"""
        data = json.loads(self.read(GuardedProfile(0, 0), []))["data"]
        self.assertEqual(
            data,
            {
                "user_id": MEMBER_ID,
                "average_rating": None,
                "rating_count": 0,
                "reviews": [],
                "page": 1,
                "page_size": 20,
                "total": 0,
            },
        )

    def test_reviewer_without_profile_is_shown_generically_not_by_login(self):
        """UT-US14-API-06: an unsaved user raises Django's real missing-relation error."""
        unsaved_user = get_user_model()(username="secret-login", email="secret@example.test")
        for reviewer in (self.reviewer(), unsaved_user):
            with self.subTest(reviewer=type(reviewer).__name__):
                self.assertEqual(reviewer_display_name(reviewer), "ผู้ใช้")
        text = self.read(GuardedProfile(5, 1), [self.source_review(self.reviewer())])
        self.assertEqual(json.loads(text)["data"]["reviews"][0]["reviewer"]["display_name"], "ผู้ใช้")
        self.assertNotIn("secret-login", text)

    def test_created_review_response_is_exactly_its_contract(self):
        """UT-US14-API-06: unlike the list, this contract includes party_id and reviewer.id."""
        reviewer = self.reviewer(profile=SimpleNamespace(display_name="ผู้จัด"))
        request = RequestFactory().post(
            "/",
            json.dumps({"reviewee_id": MEMBER_ID, "rating": 5, "comment": "  ตรงเวลา  "}),
            content_type="application/json",
        )
        request.user = reviewer
        view = inspect.unwrap(views.create_review)
        with patch("conduct.views.submit_review") as service:
            service.return_value = self.source_review(reviewer)
            response = view(request, PARTY_ID)
        self.assertEqual(response.status_code, 201)
        service.assert_called_once_with(
            party_id=PARTY_ID,
            reviewer=reviewer,
            reviewee_id=MEMBER_ID,
            rating=5,
            comment="ตรงเวลา",
        )
        text = response.content.decode()
        review = json.loads(text)["data"]["review"]
        self.assertEqual(set(review), CREATED_REVIEW_KEYS)
        self.assertEqual(review["reviewer"], {"id": 424242, "display_name": "ผู้จัด"})
        for private in ("secret-login", "secret@example.test", "6509999999", "email", "username"):
            with self.subTest(private=private):
                self.assertNotIn(private, text)

    @unittest.skip("Blocked: policy not confirmed in #100/#105")
    def test_no_show_and_credit_formula_blocked_until_policy_is_confirmed(self):
        """UT-US14-API-06 (Blocked): write these once the policy numbers are agreed."""
        self.fail("Replace this with tests of the confirmed No-show and credit policy.")
