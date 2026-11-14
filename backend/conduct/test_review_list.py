"""US14 public review list and rating summary API on PostgreSQL."""

import json
from datetime import timedelta

from accounts.models import UserProfile
from accounts.test_support import force_university_login
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from .models import PartyReview
from .test_reviews import ReviewFixture

DATA_KEYS = {
    "user_id",
    "average_rating",
    "rating_count",
    "reviews",
    "page",
    "page_size",
    "total",
}
REVIEW_KEYS = {"id", "rating", "comment", "reviewer", "created_at"}


class ReviewListFixture(ReviewFixture):
    def list_url(self, user=None):
        return reverse("user-reviews", args=[(user or self.member).pk])

    def read(self, user=None, viewer=None, **params):
        force_university_login(self.client, viewer or self.outsider)
        return self.client.get(self.list_url(user), params)

    def read_data(self, user=None, viewer=None, **params):
        response = self.read(user, viewer, **params)
        self.assertEqual(response.status_code, 200, response.content)
        body = json.loads(response.content)
        self.assertEqual(set(body), {"data"})
        return body["data"]

    def add_review(self, reviewer, reviewee=None, rating=4, comment="ดีมาก", created_at=None):
        """Write a row directly; the rating cache is deliberately left unchanged."""
        review = PartyReview.objects.create(
            party=self.party,
            reviewer=reviewer,
            reviewee=reviewee or self.member,
            rating=rating,
            comment=comment,
        )
        if created_at is not None:
            PartyReview.objects.filter(pk=review.pk).update(created_at=created_at)
            review.refresh_from_db()
        return review

    def add_dated_reviews(self, count):
        """Return reviews newest first, with ids in the opposite order to their dates."""
        now = timezone.now()
        return [
            self.add_review(
                self.make_user(f"review_writer_{index}", f"ผู้เขียน {index}"),
                created_at=now - timedelta(hours=count - index),
            )
            for index in range(count)
        ][::-1]

    def set_cache(self, user, rating_sum, rating_count):
        UserProfile.objects.filter(user=user).update(
            rating_sum=rating_sum, rating_count=rating_count
        )


class ReviewSummaryTests(ReviewListFixture, TestCase):
    def test_no_reviews_reports_null_average_and_empty_page(self):
        """IT-US14-READ-01"""
        self.assertEqual(
            self.read_data(),
            {
                "user_id": self.member.pk,
                "average_rating": None,
                "rating_count": 0,
                "reviews": [],
                "page": 1,
                "page_size": 20,
                "total": 0,
            },
        )

    def test_one_submitted_review_is_its_own_average(self):
        """IT-US14-READ-02"""
        self.assertEqual(self.submit(self.host, self.member, rating=5).status_code, 201)
        data = self.read_data()
        self.assertEqual((data["average_rating"], data["rating_count"]), (5.0, 1))

    def test_average_of_several_submitted_reviews_is_rounded_to_two_decimals(self):
        """IT-US14-READ-03: 5 and 4 -> 4.5; 5, 4 and 4 -> 4.33."""
        third = self.make_user("review_third", "สมาชิกสาม")
        self.party.memberships.create(user=third)
        self.assertEqual(self.submit(self.host, self.member, rating=5).status_code, 201)
        self.assertEqual(self.submit(self.peer, self.member, rating=4).status_code, 201)
        data = self.read_data()
        self.assertEqual((data["average_rating"], data["rating_count"]), (4.5, 2))
        self.assertEqual(self.submit(third, self.member, rating=4).status_code, 201)
        data = self.read_data()
        self.assertEqual((data["average_rating"], data["rating_count"]), (4.33, 3))

    def test_summary_comes_from_the_cache_not_the_reviews_table(self):
        """IT-US14-READ-04"""
        self.set_cache(self.member, 9, 2)
        data = self.read_data()
        self.assertEqual((data["average_rating"], data["rating_count"]), (4.5, 2))
        self.assertEqual((data["total"], data["reviews"]), (0, []))
        self.set_cache(self.member, 0, 0)
        self.add_review(self.host, rating=5)
        data = self.read_data()
        self.assertEqual((data["average_rating"], data["rating_count"]), (None, 0))
        self.assertEqual(data["total"], 1)

    def test_submit_then_read_back_end_to_end(self):
        """IT-US14-READ-05"""
        self.assertEqual(
            self.submit(self.host, self.member, rating=5, comment="ตรงเวลา").status_code, 201
        )
        self.assertEqual(
            self.submit(self.peer, self.member, rating=4, comment="เล่นดี").status_code, 201
        )
        data = self.read_data()
        self.assertEqual((data["average_rating"], data["rating_count"]), (4.5, 2))
        self.assertEqual(data["total"], 2)
        self.assertEqual(
            [
                (row["rating"], row["comment"], row["reviewer"]["display_name"])
                for row in data["reviews"]
            ],
            [(4, "เล่นดี", "สมาชิกสอง"), (5, "ตรงเวลา", "ผู้จัดรีวิว")],
        )


class ReviewOrderAndPaginationTests(ReviewListFixture, TestCase):
    def ids(self, data):
        return [row["id"] for row in data["reviews"]]

    def test_newest_first_regardless_of_insert_order(self):
        """IT-US14-READ-06"""
        now = timezone.now()
        older = self.add_review(self.host, created_at=now - timedelta(days=2))
        newest = self.add_review(self.peer, created_at=now)
        oldest_inserted_last = self.add_review(self.outsider, created_at=now - timedelta(days=9))
        self.assertEqual(self.ids(self.read_data()), [newest.pk, older.pk, oldest_inserted_last.pk])

    def test_equal_timestamps_are_ordered_by_id_descending(self):
        """IT-US14-READ-07"""
        now = timezone.now()
        first = self.add_review(self.host, created_at=now)
        second = self.add_review(self.peer, created_at=now)
        self.assertEqual(self.ids(self.read_data()), [second.pk, first.pk])

    def test_only_reviews_of_the_requested_user_are_listed(self):
        """IT-US14-READ-08"""
        own = self.add_review(self.host, self.member)
        self.add_review(self.host, self.peer)
        self.add_review(self.member, self.peer)
        data = self.read_data()
        self.assertEqual((self.ids(data), data["total"]), ([own.pk], 1))

    def test_pages_split_results_and_report_total(self):
        """IT-US14-READ-09"""
        reviews = [review.pk for review in self.add_dated_reviews(5)]
        for page, expected in ((1, reviews[:2]), (2, reviews[2:4]), (3, reviews[4:])):
            with self.subTest(page=page):
                data = self.read_data(page=page, page_size=2)
                self.assertEqual(self.ids(data), expected)
                self.assertEqual((data["page"], data["page_size"], data["total"]), (page, 2, 5))

    def test_page_beyond_the_end_is_empty(self):
        """IT-US14-READ-10: a huge page must not overflow the SQL OFFSET."""
        self.add_dated_reviews(2)
        for page in (2, 2**63 - 1):
            with self.subTest(page=page):
                data = self.read_data(page=page)
                self.assertEqual((data["reviews"], data["page"], data["total"]), ([], page, 2))

    def test_default_and_maximum_page_size(self):
        """IT-US14-READ-11"""
        self.add_dated_reviews(21)
        data = self.read_data()
        self.assertEqual((len(data["reviews"]), data["page_size"]), (20, 20))
        data = self.read_data(page_size=100)
        self.assertEqual((len(data["reviews"]), data["page_size"]), (21, 100))

    def test_invalid_page_parameters_are_rejected(self):
        """IT-US14-READ-12"""
        cases = [
            ("page", value) for value in ("0", "-1", "abc", "1.5", "", " 1", "๕", "1_0", "9" * 5000)
        ] + [("page_size", value) for value in ("0", "-1", "101", "abc", "1.5", "")]
        for field, value in cases:
            with self.subTest(field=field, value=value[:10]):
                self.assert_error(self.read(**{field: value}), 400, "INVALID_INPUT", {field})

    def test_repeated_page_parameter_is_rejected(self):
        """IT-US14-READ-13: the same rule as the venue list."""
        force_university_login(self.client, self.outsider)
        for field in ("page", "page_size"):
            with self.subTest(field=field):
                response = self.client.get(f"{self.list_url()}?{field}=1&{field}=2")
                self.assert_error(response, 400, "INVALID_INPUT", {field})

    def test_unknown_query_parameters_are_ignored(self):
        """IT-US14-READ-14"""
        data = self.read_data(limit="abc", offset="-1", other="x")
        self.assertEqual((data["page"], data["page_size"]), (1, 20))

    def test_query_count_does_not_grow_with_the_page(self):
        """IT-US14-READ-15: reviewers with and without a profile cost no extra query."""
        self.add_review(self.host)
        force_university_login(self.client, self.outsider)
        with CaptureQueriesContext(connection) as one_review:
            response = self.client.get(self.list_url())
        self.assertEqual(len(json.loads(response.content)["data"]["reviews"]), 1)
        for index in range(19):
            display_name = f"ผู้เขียน {index}" if index % 2 else None
            self.add_review(self.make_user(f"review_writer_{index}", display_name))
        with CaptureQueriesContext(connection) as twenty_reviews:
            response = self.client.get(self.list_url())
        self.assertEqual(len(json.loads(response.content)["data"]["reviews"]), 20)
        self.assertEqual(len(twenty_reviews), len(one_review))


class ReviewPublicFieldsTests(ReviewListFixture, TestCase):
    def test_response_keys_are_exactly_the_allowlist(self):
        """IT-US14-READ-16"""
        review = self.add_review(self.host, rating=3, comment="เล่นดี")
        data = self.read_data()
        self.assertEqual(set(data), DATA_KEYS)
        self.assertEqual(set(data["reviews"][0]), REVIEW_KEYS)
        self.assertEqual(
            data["reviews"][0],
            {
                "id": review.pk,
                "rating": 3,
                "comment": "เล่นดี",
                "reviewer": {"display_name": "ผู้จัดรีวิว"},
                "created_at": timezone.localtime(review.created_at).isoformat(),
            },
        )

    def test_body_has_no_identifier_or_credit_data(self):
        """IT-US14-READ-17"""
        UserProfile.objects.filter(user=self.member).update(credit_score=75)
        self.add_review(self.host)
        text = self.read(viewer=self.host).content.decode()
        for private in (
            "email",
            "@example.test",
            "username",
            "review_host",
            "review_member",
            "student",
            "test-user-",
            "party",
            "credit",
            "reviewer_id",
        ):
            self.assertNotIn(private, text)

    def test_reviewer_without_profile_gets_generic_display_name(self):
        """IT-US14-READ-18"""
        self.add_review(self.make_user("review_legacy"))
        data = self.read_data()
        self.assertEqual(data["reviews"][0]["reviewer"], {"display_name": "ผู้ใช้"})


class ReviewListAccessTests(ReviewListFixture, TestCase):
    def test_user_can_read_own_reviews(self):
        """IT-US14-READ-19"""
        self.add_review(self.host)
        data = self.read_data(self.member, viewer=self.member)
        self.assertEqual((data["user_id"], data["total"]), (self.member.pk, 1))

    def test_any_logged_in_user_can_read_another_users_reviews(self):
        """IT-US14-READ-20: viewers need not share a party with the reviewee."""
        self.add_review(self.host)
        data = self.read_data(self.member, viewer=self.outsider)
        self.assertEqual((data["user_id"], data["total"]), (self.member.pk, 1))

    def test_unknown_user_is_404(self):
        """IT-US14-READ-21"""
        force_university_login(self.client, self.outsider)
        for user_id in (self.outsider.pk + 1000, 2**63, 10**30):
            with self.subTest(user_id=user_id):
                response = self.client.get(reverse("user-reviews", args=[user_id]))
                self.assert_error(response, 404, "NOT_FOUND")
                self.assertEqual(json.loads(response.content)["error"]["message"], "ไม่พบผู้ใช้ที่ต้องการ")

    def test_user_without_profile_is_404_even_with_review_rows(self):
        """IT-US14-READ-22"""
        legacy = self.make_user("review_legacy")
        self.add_review(self.host, legacy)
        self.assert_error(self.read(legacy), 404, "NOT_FOUND")

    def test_inactive_user_with_profile_is_readable_like_the_profile_api(self):
        """IT-US14-READ-23"""
        self.add_review(self.host)
        type(self.member).objects.filter(pk=self.member.pk).update(is_active=False)
        force_university_login(self.client, self.outsider)
        profile = self.client.get(reverse("accounts:user-public-profile", args=[self.member.pk]))
        self.assertEqual(profile.status_code, 200)
        data = self.read_data()
        self.assertEqual(data["total"], 1)

    def test_unauthenticated_request_is_401(self):
        """IT-US14-READ-24"""
        self.assert_error(self.client.get(self.list_url()), 401, "AUTH_REQUIRED")

    def test_session_without_university_identity_is_403(self):
        """IT-US14-READ-25"""
        self.client.force_login(self.outsider)
        self.assert_error(self.client.get(self.list_url()), 403, "FORBIDDEN")

    def test_other_methods_are_405_with_allow(self):
        """IT-US14-READ-26"""
        force_university_login(self.client, self.outsider)
        for method in ("post", "put", "patch", "delete"):
            with self.subTest(method=method):
                response = getattr(self.client, method)(self.list_url())
                self.assert_error(response, 405, "METHOD_NOT_ALLOWED")
                self.assertEqual(response["Allow"], "GET")

    def test_response_is_not_cacheable(self):
        """IT-US14-READ-27"""
        self.assertIn("no-store", self.read()["Cache-Control"])
