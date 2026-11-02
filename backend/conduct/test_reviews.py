"""US14 review submission API, rules and database constraints on PostgreSQL."""

import json
from datetime import timedelta

from accounts.models import UserProfile
from accounts.test_support import force_university_login
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from parties.models import Party, PartyMembership
from parties.services import PartyError
from venues.models import Sport, Venue

from .models import PartyReview
from .services import submit_review


class ReviewFixture:
    def setUp(self):
        super().setUp()
        self.sport = Sport.objects.create(name="Badminton")
        self.venue = Venue.objects.create(name="Court", location_text="Campus")
        self.host = self.make_user("review_host", "ผู้จัดรีวิว")
        self.member = self.make_user("review_member", "สมาชิกหนึ่ง")
        self.peer = self.make_user("review_peer", "สมาชิกสอง")
        self.outsider = self.make_user("review_outsider", "คนนอก")
        self.party = self.make_party()
        self.complete(self.party)

    def make_user(self, username, display_name=None):
        user = get_user_model().objects.create_user(username, email=f"{username}@example.test")
        if display_name:
            UserProfile.objects.create(user=user, display_name=display_name)
        return user

    def make_party(self, members=None):
        now = timezone.now()
        party = Party.objects.create(
            host=self.host,
            sport=self.sport,
            venue=self.venue,
            title="After class",
            starts_at=now + timedelta(days=1),
            ends_at=now + timedelta(days=1, hours=1),
            capacity=10,
        )
        for user in [self.host, *((self.member, self.peer) if members is None else members)]:
            PartyMembership.objects.create(party=party, user=user)
        return party

    def move_times(self, party, starts_at, ends_at, **changes):
        # The create service rejects past times, so shift them after creation.
        Party.objects.filter(pk=party.pk).update(starts_at=starts_at, ends_at=ends_at, **changes)
        party.refresh_from_db()

    def complete(self, party):
        now = timezone.now()
        self.move_times(party, now - timedelta(hours=3), now - timedelta(hours=2))

    def url(self, party=None):
        return reverse("party-review-create", args=[(party or self.party).pk])

    def payload(self, reviewee=None, **changes):
        return {
            "reviewee_id": (reviewee or self.member).pk,
            "rating": 4,
            "comment": "เล่นสนุกมาก",
            **changes,
        }

    def submit(self, reviewer=None, reviewee=None, party=None, **changes):
        force_university_login(self.client, reviewer or self.host)
        return self.client.post(
            self.url(party), self.payload(reviewee, **changes), content_type="application/json"
        )

    def cache(self, user):
        return UserProfile.objects.values_list("rating_sum", "rating_count").get(user=user)

    def assert_error(self, response, status, code, fields=None):
        self.assertEqual(response.status_code, status, response.content)
        body = json.loads(response.content)
        self.assertEqual(set(body), {"error"})
        self.assertEqual(body["error"]["code"], code)
        if fields is None:
            self.assertNotIn("fields", body["error"])
        else:
            self.assertEqual(set(body["error"]["fields"]), set(fields))

    def assert_no_review_written(self):
        self.assertEqual(PartyReview.objects.count(), 0)
        self.assertFalse(UserProfile.objects.exclude(rating_sum=0, rating_count=0).exists())


class ReviewHappyPathTests(ReviewFixture, TestCase):
    def test_host_reviews_member_with_exact_response_and_cache(self):
        """IT-US14-DB-01"""
        response = self.submit(comment="  เล่นสนุกมาก  ")
        self.assertEqual(response.status_code, 201, response.content)
        review = PartyReview.objects.get()
        self.assertEqual(
            json.loads(response.content),
            {
                "data": {
                    "review": {
                        "id": review.pk,
                        "party_id": self.party.pk,
                        "reviewer": {"id": self.host.pk, "display_name": "ผู้จัดรีวิว"},
                        "reviewee_id": self.member.pk,
                        "rating": 4,
                        "comment": "เล่นสนุกมาก",
                        "created_at": timezone.localtime(review.created_at).isoformat(),
                    }
                }
            },
        )
        self.assertEqual(review.comment, "เล่นสนุกมาก")
        self.assertEqual((review.reviewer, review.reviewee), (self.host, self.member))
        self.assertEqual(self.cache(self.member), (4, 1))
        self.assertEqual(self.cache(self.host), (0, 0))
        self.assertIn("no-store", response["Cache-Control"])

    def test_response_exposes_no_login_or_contact_identifier(self):
        """IT-US14-DB-02"""
        text = self.submit().content.decode()
        for private in ("review_host", "review_member", "@example.test", "email", "username"):
            self.assertNotIn(private, text)

    def test_member_reviews_host_and_member_reviews_member(self):
        """IT-US14-DB-03"""
        self.assertEqual(self.submit(self.member, self.host, rating=5).status_code, 201)
        self.assertEqual(self.submit(self.member, self.peer, rating=2).status_code, 201)
        self.assertEqual(self.cache(self.host), (5, 1))
        self.assertEqual(self.cache(self.peer), (2, 1))

    def test_cache_accumulates_reviews_from_different_reviewers(self):
        """IT-US14-DB-04"""
        self.assertEqual(self.submit(self.host, self.member, rating=5).status_code, 201)
        self.assertEqual(self.submit(self.peer, self.member, rating=2).status_code, 201)
        self.assertEqual(self.cache(self.member), (7, 2))

    def test_same_reviewer_can_review_a_different_reviewee_in_the_party(self):
        """IT-US14-DB-05"""
        self.assertEqual(self.submit(reviewee=self.member).status_code, 201)
        self.assertEqual(self.submit(reviewee=self.peer).status_code, 201)
        self.assertEqual(PartyReview.objects.count(), 2)

    def test_same_reviewee_can_be_reviewed_again_in_another_party(self):
        """IT-US14-DB-06"""
        other_party = self.make_party()
        self.complete(other_party)
        self.assertEqual(self.submit(rating=3).status_code, 201)
        self.assertEqual(self.submit(party=other_party, rating=5).status_code, 201)
        self.assertEqual(self.cache(self.member), (8, 2))

    def test_reviewer_without_profile_gets_generic_display_name(self):
        """IT-US14-DB-07"""
        legacy = self.make_user("review_legacy")
        PartyMembership.objects.create(party=self.party, user=legacy)
        response = self.submit(legacy, self.member)
        self.assertEqual(response.status_code, 201, response.content)
        reviewer = json.loads(response.content)["data"]["review"]["reviewer"]
        self.assertEqual(reviewer, {"id": legacy.pk, "display_name": "ผู้ใช้"})


class ReviewDuplicateTests(ReviewFixture, TestCase):
    def test_duplicate_returns_409_and_does_not_count_twice(self):
        """IT-US14-DB-08"""
        self.assertEqual(self.submit(rating=4).status_code, 201)
        response = self.submit(rating=1, comment="แก้คะแนน")
        self.assert_error(response, 409, "REVIEW_EXISTS")
        review = PartyReview.objects.get()
        self.assertEqual((review.rating, review.comment), (4, "เล่นสนุกมาก"))
        self.assertEqual(self.cache(self.member), (4, 1))

    def test_duplicate_leaves_the_outer_transaction_usable(self):
        """IT-US14-DB-09: the unique conflict is caught outside its failed savepoint."""
        self.assertEqual(self.submit().status_code, 201)
        with transaction.atomic():
            with self.assertRaises(PartyError) as caught:
                submit_review(
                    party_id=self.party.pk,
                    reviewer=self.host,
                    reviewee_id=self.member.pk,
                    rating=5,
                    comment="ซ้ำ",
                )
            self.assertEqual(caught.exception.code, "REVIEW_EXISTS")
            self.assertEqual(PartyReview.objects.count(), 1)

    def test_other_integrity_errors_are_not_reported_as_duplicates(self):
        """IT-US14-DB-10"""
        with self.assertRaises(IntegrityError):
            submit_review(
                party_id=self.party.pk,
                reviewer=self.host,
                reviewee_id=self.member.pk,
                rating=6,
                comment="ข้ามการตรวจของ API",
            )
        self.assert_no_review_written()


class ReviewPartyStateTests(ReviewFixture, TestCase):
    def assert_not_completed(self, party):
        response = self.submit(party=party)
        self.assert_error(response, 409, "PARTY_NOT_COMPLETED")
        self.assert_no_review_written()

    def test_open_party_is_refused(self):
        """IT-US14-DB-11"""
        self.assert_not_completed(self.make_party())

    def test_full_party_is_refused(self):
        """IT-US14-DB-12"""
        party = self.make_party()
        Party.objects.filter(pk=party.pk).update(capacity=3)
        self.assert_not_completed(party)

    def test_in_progress_party_is_refused(self):
        """IT-US14-DB-13"""
        party = self.make_party()
        now = timezone.now()
        self.move_times(party, now - timedelta(hours=1), now + timedelta(hours=1))
        self.assert_not_completed(party)

    def test_cancelled_party_is_refused_before_and_after_its_end_time(self):
        """IT-US14-DB-14"""
        now = timezone.now()
        upcoming = self.make_party()
        Party.objects.filter(pk=upcoming.pk).update(cancelled_at=now)
        self.assert_not_completed(upcoming)
        ended = self.make_party()
        self.move_times(
            ended,
            now - timedelta(hours=3),
            now - timedelta(hours=2),
            cancelled_at=now - timedelta(days=1),
        )
        self.assert_not_completed(ended)

    def test_unknown_party_is_404(self):
        """IT-US14-DB-15"""
        force_university_login(self.client, self.host)
        for party_id in (self.party.pk + 1000, 10**30):
            with self.subTest(party_id=party_id):
                response = self.client.post(
                    reverse("party-review-create", args=[party_id]),
                    self.payload(),
                    content_type="application/json",
                )
                self.assert_error(response, 404, "NOT_FOUND")


class ReviewEligibilityTests(ReviewFixture, TestCase):
    def set_left_at(self, user, delta):
        PartyMembership.objects.filter(party=self.party, user=user).update(
            left_at=self.party.ends_at + delta
        )

    def test_outsider_reviewer_is_forbidden(self):
        """IT-US14-DB-16"""
        self.assert_error(self.submit(self.outsider, self.member), 403, "FORBIDDEN")
        self.assert_no_review_written()

    def test_reviewee_outsider_missing_and_profileless_are_indistinguishable(self):
        """IT-US14-DB-17: no response reveals that an account exists; nothing is stored."""
        legacy = self.make_user("review_legacy")
        PartyMembership.objects.create(party=self.party, user=legacy)
        force_university_login(self.client, self.host)
        bodies = []
        for reviewee_id in (self.outsider.pk, legacy.pk, legacy.pk + 1000):
            response = self.client.post(
                self.url(),
                {"reviewee_id": reviewee_id, "rating": 4, "comment": "ดีมาก"},
                content_type="application/json",
            )
            self.assert_error(response, 400, "INVALID_INPUT", {"reviewee_id"})
            bodies.append(json.loads(response.content))
        self.assertEqual(bodies[0], bodies[1])
        self.assertEqual(bodies[0], bodies[2])
        self.assert_no_review_written()

    def test_reviewee_without_profile_cannot_create_an_uncounted_review(self):
        """IT-US14-DB-18: the insert is rolled back when no rating cache exists."""
        legacy = self.make_user("review_legacy")
        PartyMembership.objects.create(party=self.party, user=legacy)
        self.assert_error(self.submit(reviewee=legacy), 400, "INVALID_INPUT", {"reviewee_id"})
        self.assertEqual(PartyReview.objects.count(), 0)
        self.assertFalse(UserProfile.objects.filter(user=legacy).exists())

    def test_self_review_is_rejected(self):
        """IT-US14-DB-19"""
        for user in (self.host, self.member):
            with self.subTest(user=user.username):
                response = self.submit(user, user)
                self.assert_error(response, 400, "INVALID_INPUT", {"reviewee_id"})
        self.assert_no_review_written()

    def test_member_who_left_before_end_is_not_eligible(self):
        """IT-US14-DB-20"""
        self.set_left_at(self.member, timedelta(seconds=-1))
        self.assert_error(self.submit(self.member, self.peer), 403, "FORBIDDEN")
        self.assert_error(
            self.submit(self.peer, self.member), 400, "INVALID_INPUT", {"reviewee_id"}
        )
        self.assert_no_review_written()

    def test_member_who_left_at_or_after_end_is_eligible(self):
        """IT-US14-DB-21"""
        self.set_left_at(self.member, timedelta(0))
        self.set_left_at(self.peer, timedelta(minutes=1))
        self.assertEqual(self.submit(self.member, self.peer).status_code, 201)
        self.assertEqual(self.submit(self.peer, self.member).status_code, 201)

    def test_host_without_membership_row_is_a_participant(self):
        """IT-US14-DB-22"""
        PartyMembership.objects.filter(party=self.party, user=self.host).delete()
        self.assertEqual(self.submit(self.host, self.member).status_code, 201)
        self.assertEqual(self.submit(self.member, self.host).status_code, 201)

    def test_membership_of_another_party_does_not_count(self):
        """IT-US14-DB-23"""
        other_party = self.make_party(members=[self.outsider])
        self.complete(other_party)
        self.assert_error(self.submit(self.outsider, self.member), 403, "FORBIDDEN")
        self.assert_error(
            self.submit(self.host, self.member, party=other_party),
            400,
            "INVALID_INPUT",
            {"reviewee_id"},
        )


class ReviewInputValidationTests(ReviewFixture, TestCase):
    def setUp(self):
        super().setUp()
        force_university_login(self.client, self.host)

    def post_json(self, payload):
        return self.client.post(self.url(), payload, content_type="application/json")

    def assert_field_rejected(self, field, values):
        for value in values:
            with self.subTest(field=field, value=value):
                response = self.post_json(self.payload(**{field: value}))
                self.assert_error(response, 400, "INVALID_INPUT", {field})
        self.assert_no_review_written()

    def test_rating_must_be_an_integer_from_1_to_5(self):
        """IT-US14-DB-24"""
        self.assert_field_rejected("rating", [0, 6, -1, "5", 5.0, True, None, [5]])

    def test_every_rating_from_1_to_5_is_accepted(self):
        """IT-US14-DB-25"""
        for rating in range(1, 6):
            party = self.make_party()
            self.complete(party)
            response = self.client.post(
                self.url(party), self.payload(rating=rating), content_type="application/json"
            )
            self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(self.cache(self.member), (15, 5))

    def test_comment_is_required_text_within_limits(self):
        """IT-US14-DB-26"""
        self.assert_field_rejected(
            "comment", ["", "   \n\t", "ก" * 501, 5, None, ["ดี"], "ดี\x00มาก", "ดี\ud800"]
        )

    def test_comment_of_500_characters_is_accepted(self):
        """IT-US14-DB-27: the limit counts characters after stripping."""
        response = self.post_json(self.payload(comment=f"  {'ก' * 500}  "))
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(PartyReview.objects.get().comment, "ก" * 500)

    def test_reviewee_id_must_be_an_in_range_integer(self):
        """IT-US14-DB-28"""
        self.assert_field_rejected(
            "reviewee_id", [str(self.member.pk), float(self.member.pk), True, None, 0, -1, 2**63]
        )

    def test_missing_fields_are_reported_individually(self):
        """IT-US14-DB-29"""
        for field in ("reviewee_id", "rating", "comment"):
            with self.subTest(field=field):
                payload = self.payload()
                del payload[field]
                self.assert_error(self.post_json(payload), 400, "INVALID_INPUT", {field})
        self.assert_error(
            self.post_json({}), 400, "INVALID_INPUT", {"reviewee_id", "rating", "comment"}
        )
        self.assert_no_review_written()

    def test_unknown_fields_are_rejected_including_client_selected_actor_and_cache(self):
        """IT-US14-DB-30"""
        for field in ("reviewer_id", "party_id", "rating_sum", "rating_count", "extra"):
            with self.subTest(field=field):
                response = self.post_json(self.payload(**{field: 1}))
                self.assert_error(response, 400, "INVALID_INPUT", {field})
        self.assert_no_review_written()

    def test_non_json_content_type_is_rejected(self):
        """IT-US14-DB-31"""
        body = json.dumps(self.payload())
        for content_type in ("text/plain", "application/x-www-form-urlencoded"):
            with self.subTest(content_type=content_type):
                response = self.client.post(self.url(), body, content_type=content_type)
                self.assert_error(response, 400, "INVALID_INPUT")
        self.assert_no_review_written()

    def test_invalid_json_and_non_objects_are_rejected(self):
        """IT-US14-DB-32"""
        for body in ("{", "", b"\xff", "[]", '"text"', "1", "null"):
            with self.subTest(body=body):
                self.assert_error(self.post_json(body), 400, "INVALID_INPUT")
        self.assert_no_review_written()


class ReviewAccessTests(ReviewFixture, TestCase):
    def test_unauthenticated_request_is_401(self):
        """IT-US14-DB-33"""
        response = self.client.post(self.url(), self.payload(), content_type="application/json")
        self.assert_error(response, 401, "AUTH_REQUIRED")
        self.assert_no_review_written()

    def test_session_without_university_identity_is_403(self):
        """IT-US14-DB-34"""
        self.client.force_login(self.host)
        response = self.client.post(self.url(), self.payload(), content_type="application/json")
        self.assert_error(response, 403, "FORBIDDEN")
        self.assert_no_review_written()

    def test_other_methods_are_405_with_allow(self):
        """IT-US14-DB-35"""
        force_university_login(self.client, self.host)
        for method in ("get", "put", "patch", "delete"):
            with self.subTest(method=method):
                response = getattr(self.client, method)(self.url())
                self.assert_error(response, 405, "METHOD_NOT_ALLOWED")
                self.assertEqual(response["Allow"], "POST")

    def test_csrf_is_enforced_by_the_middleware(self):
        """IT-US14-DB-36"""
        client = Client(enforce_csrf_checks=True)
        force_university_login(client, self.host)
        response = client.post(self.url(), self.payload(), content_type="application/json")
        self.assert_error(response, 403, "CSRF_FAILED")
        self.assert_no_review_written()
        token = client.get(reverse("accounts:csrf")).json()["data"]["csrf_token"]
        response = client.post(
            self.url(), self.payload(), content_type="application/json", HTTP_X_CSRFTOKEN=token
        )
        self.assertEqual(response.status_code, 201, response.content)


class ReviewConstraintTests(ReviewFixture, TestCase):
    def create_row(self, **changes):
        fields = {
            "party": self.party,
            "reviewer": self.host,
            "reviewee": self.member,
            "rating": 3,
            "comment": "",
            **changes,
        }
        with transaction.atomic():
            return PartyReview.objects.create(**fields)

    def test_rating_range_is_enforced_by_the_database(self):
        """IT-US14-DB-37"""
        for rating in (0, 6):
            with self.subTest(rating=rating), self.assertRaises(IntegrityError) as caught:
                self.create_row(rating=rating)
            self.assertIn("party_review_rating_1_to_5", str(caught.exception))

    def test_self_review_is_enforced_by_the_database(self):
        """IT-US14-DB-38"""
        with self.assertRaises(IntegrityError) as caught:
            self.create_row(reviewee=self.host)
        self.assertIn("party_review_not_self", str(caught.exception))

    def test_duplicate_is_enforced_by_the_database(self):
        """IT-US14-DB-39"""
        self.create_row()
        with self.assertRaises(IntegrityError) as caught:
            self.create_row()
        self.assertIn("unique_party_review", str(caught.exception))

    def test_rating_cache_cannot_be_negative(self):
        """IT-US14-DB-40"""
        for field in ("rating_sum", "rating_count"):
            with self.subTest(field=field), self.assertRaises(IntegrityError):
                with transaction.atomic():
                    UserProfile.objects.filter(user=self.member).update(**{field: -1})
