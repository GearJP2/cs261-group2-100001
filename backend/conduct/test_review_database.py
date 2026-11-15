"""Task95 SQL evidence for real API writes, failure atomicity and history."""

import json
from pathlib import Path
from unittest.mock import patch

from accounts.models import UserProfile
from accounts.test_support import force_university_login
from django.db import DatabaseError, IntegrityError, connection
from django.db.models.query import QuerySet
from django.test import Client, TestCase
from django.urls import reverse
from parties.models import PartyMembership

from .models import PartyReview
from .test_reviews import ReviewFixture


class ReviewDatabaseFixture(ReviewFixture):
    def sql_snapshot(self):
        path = Path(__file__).resolve().parents[2] / "database/seeds/us14_review_test_snapshot.sql"
        with connection.cursor() as cursor:
            cursor.execute(path.read_text().replace(":reviewee_id", "%s"), [self.member.pk])
            names = [column[0] for column in cursor.description]
            return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]

    def evidence(self, **observed):
        print(
            "DB95_EVIDENCE " + json.dumps({"case": self._testMethodName, **observed}, default=str)
        )

    def csrf_client(self, user):
        client = Client(enforce_csrf_checks=True)
        force_university_login(client, user)
        token = client.get(reverse("accounts:csrf")).json()["data"]["csrf_token"]
        return client, token


class ReviewDatabaseEvidenceTests(ReviewDatabaseFixture, TestCase):
    def post_review(self, client, token, rating=4, party=None):
        return client.post(
            self.url(party),
            self.payload(rating=rating),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )

    def test_multiple_ratings_match_raw_rows_summary_and_credit_history(self):
        UserProfile.objects.filter(user=self.member).update(credit_score=95)
        before = self.sql_snapshot()
        memberships = list(PartyMembership.objects.order_by("pk").values())
        host, ht = self.csrf_client(self.host)
        peer, pt = self.csrf_client(self.peer)
        responses = [self.post_review(host, ht, 5), self.post_review(peer, pt, 4)]
        second = self.make_party()
        self.complete(second)
        responses.append(self.post_review(host, ht, 4, second))
        self.assertEqual([r.status_code for r in responses], [201, 201, 201])
        after = self.sql_snapshot()
        self.assertEqual(
            (
                after[0]["rating_sum"],
                after[0]["rating_count"],
                after[0]["actual_sum"],
                after[0]["actual_count"],
            ),
            (13, 3, 13, 3),
        )
        self.assertEqual([r["rating"] for r in after], [5, 4, 4])
        self.assertEqual((after[0]["credit_score"], after[0]["credit_events"]), (95, 0))
        self.assertEqual(
            memberships,
            list(PartyMembership.objects.filter(party=self.party).order_by("pk").values()),
        )
        response = host.get(reverse("user-reviews", args=[self.member.pk]))
        summary = response.json()["data"]
        self.assertEqual(
            (summary["average_rating"], summary["rating_count"], summary["total"]), (4.33, 3, 3)
        )
        self.evidence(
            sql_before=before,
            sql_after=after,
            http_statuses=[201, 201, 201],
            summary={k: summary[k] for k in ("average_rating", "rating_count", "total")},
        )

    def test_duplicate_api_leaves_review_id_timestamp_cache_and_credit_unchanged(self):
        client, token = self.csrf_client(self.host)
        self.assertEqual(self.post_review(client, token).status_code, 201)
        before = self.sql_snapshot()
        response = self.post_review(client, token)
        self.assertEqual(
            (response.status_code, response.json()["error"]["code"]), (409, "REVIEW_EXISTS")
        )
        self.assertEqual(self.sql_snapshot(), before)
        self.evidence(
            sql_before=before,
            http_status=409,
            response=response.json(),
            sql_after=self.sql_snapshot(),
        )

    def check_rollback(self, *, real_constraint):
        client, token = self.csrf_client(self.host)
        client.raise_request_exception = False
        before = self.sql_snapshot()
        original = QuerySet.update
        observed = {}

        def fail_cache(queryset, **kwargs):
            if queryset.model is UserProfile and {"rating_sum", "rating_count"} <= kwargs.keys():
                # Review INSERT has executed in the service before the cache update.
                observed["insert_seen_before_failure"] = PartyReview.objects.filter(
                    reviewee=self.member
                ).count()
                if real_constraint:
                    try:
                        return original(queryset, rating_count=-1)
                    except IntegrityError as error:
                        observed["sqlstate"] = error.__cause__.sqlstate
                        observed["constraint"] = error.__cause__.diag.constraint_name
                        raise
                original(queryset, **kwargs)
                observed["updated_cache_before_failure"] = (
                    UserProfile.objects.filter(user=self.member)
                    .values("rating_sum", "rating_count")
                    .get()
                )
                raise DatabaseError("Task95 injected error after actual cache UPDATE")
            return original(queryset, **kwargs)

        with patch.object(QuerySet, "update", fail_cache):
            response = self.post_review(client, token)
        self.assertEqual(response.status_code, 500)
        self.assertEqual(observed["insert_seen_before_failure"], 1)
        self.assertEqual(before, self.sql_snapshot())
        if real_constraint:
            self.assertEqual(
                (observed["sqlstate"], observed["constraint"]),
                ("23514", "user_profile_rating_count_gte_0"),
            )
        else:
            self.assertEqual(
                observed["updated_cache_before_failure"], {"rating_sum": 4, "rating_count": 1}
            )
        self.evidence(
            sql_before=before,
            fault="invalid count injected; real PostgreSQL CHECK violation"
            if real_constraint
            else "injected DatabaseError after real cache UPDATE",
            observed=observed,
            http_status=500,
            sql_after=self.sql_snapshot(),
        )

    def test_api_failure_after_both_writes_rolls_back_review_and_cache(self):
        self.check_rollback(real_constraint=False)

    def test_actual_cache_constraint_violation_rolls_back_inserted_review(self):
        self.check_rollback(real_constraint=True)
