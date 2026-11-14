"""Task87: execute the read-only reconciliation SQL against real review writes."""

import json
from decimal import Decimal
from pathlib import Path

from accounts.models import UserProfile
from django.db import connection
from django.test import TestCase

from .models import ConductCreditEvent, PartyReview
from .services import average_rating, submit_review
from .test_reviews import ReviewFixture


class ReviewCacheAuditTests(ReviewFixture, TestCase):
    def audit(self):
        sql = Path(__file__).resolve().parents[2] / "database/seeds/us14_review_cache_audit.sql"
        with connection.cursor() as cursor:
            cursor.execute(sql.read_text())
            names = [column[0] for column in cursor.description]
            return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]

    def evidence(self, **observed):
        print(
            "DB87_EVIDENCE " + json.dumps({"case": self._testMethodName, **observed}, default=str)
        )

    def test_reconcile_multiple_parties_without_ledger_fanout_or_credit_mutation(self):
        before = self.audit()
        self.assertTrue(all(row["cache_matches"] for row in before))
        self.assertTrue(all(row["actual_average"] is None for row in before))
        second = self.make_party()
        self.complete(second)
        UserProfile.objects.filter(user=self.member).update(credit_score=95)
        # Two historical ledger rows must not multiply the three reviews.
        for party in (self.party, second):
            ConductCreditEvent.objects.create(
                user=self.member, party=party, kind="NoShowDeduction", delta=-5
            )
        credits_before = list(
            UserProfile.objects.order_by("user_id").values("user_id", "credit_score")
        )
        for party, reviewer, rating in (
            (self.party, self.host, 5),
            (self.party, self.peer, 4),
            (second, self.host, 4),
        ):
            submit_review(
                party_id=party.pk,
                reviewer=reviewer,
                reviewee_id=self.member.pk,
                rating=rating,
                comment="Synthetic Task87 review",
            )
        after = self.audit()
        target = next(row for row in after if row["user_id"] == self.member.pk)
        self.assertEqual((target["actual_count"], target["actual_sum"]), (3, 13))
        self.assertEqual(target["actual_average"].quantize(Decimal("0.01")), Decimal("4.33"))
        self.assertTrue(all(row["cache_matches"] for row in after))
        profile = UserProfile.objects.get(user=self.member)
        self.assertEqual(average_rating(profile), 4.33)
        self.assertEqual(
            credits_before,
            list(UserProfile.objects.order_by("user_id").values("user_id", "credit_score")),
        )
        self.assertEqual(ConductCreditEvent.objects.count(), 2)
        self.evidence(sql_before=before, sql_after=after, ledger_rows=2, api_average=4.33)

    def test_audit_detects_drift_and_missing_profile_without_repairing(self):
        submit_review(
            party_id=self.party.pk,
            reviewer=self.host,
            reviewee_id=self.member.pk,
            rating=5,
            comment="Synthetic drift case",
        )
        UserProfile.objects.filter(user=self.member).update(rating_sum=6)
        # Direct imported data can bypass the service's required-profile guard.
        bare = self.make_user("task87_missing_profile")
        PartyReview.objects.create(
            party=self.party,
            reviewer=self.host,
            reviewee=bare,
            rating=4,
            comment="Synthetic imported row",
        )
        rows = self.audit()
        drift = next(row for row in rows if row["user_id"] == self.member.pk)
        orphan = next(row for row in rows if row["user_id"] == bare.pk)
        self.assertEqual(
            (drift["cached_sum"], drift["actual_sum"], drift["cache_matches"]), (6, 5, False)
        )
        self.assertEqual(
            (orphan["profile_exists"], orphan["actual_count"], orphan["cache_matches"]),
            (False, 1, False),
        )
        self.assertEqual(UserProfile.objects.get(user=self.member).rating_sum, 6)
        self.assertFalse(UserProfile.objects.filter(user=bare).exists())
        self.evidence(sql_after_injected_drift=rows, action="read only; no automatic repair")
