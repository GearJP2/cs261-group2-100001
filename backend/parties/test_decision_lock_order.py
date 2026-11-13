"""Task49: observe actual SQL lock order; rollback/races reuse existing suites."""

from django.db import connection
from django.test import TestCase, skipUnlessDBFeature
from django.test.utils import CaptureQueriesContext

from .models import JoinRequest, PartyMembership
from .services import decide_join_request
from .test_join_requests import JoinRequestFixture


@skipUnlessDBFeature("has_select_for_update")
class DecisionLockOrderTests(JoinRequestFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.pending = JoinRequest.objects.create(party=self.party, user=self.applicant)

    def decide_and_capture(self, approved):
        with CaptureQueriesContext(connection) as captured:
            decide_join_request(
                party_id=self.party.pk,
                request_id=self.pending.pk,
                user=self.host,
                approved=approved,
            )
        return [row["sql"] for row in captured.captured_queries]

    def test_approve_locks_party_then_request_then_membership_before_writes(self):
        # No applicant row exists: Party must protect the missing-row/capacity gap.
        self.assertFalse(self.party.memberships.filter(user=self.applicant).exists())
        sql = self.decide_and_capture(True)
        locks = [query for query in sql if "FOR UPDATE" in query]
        self.assertEqual(len(locks), 3)
        for query, table in zip(
            locks, ("parties_party", "parties_joinrequest", "parties_partymembership"), strict=True
        ):
            self.assertIn(f'FROM "{table}"', query)
        first_write = next(
            i for i, query in enumerate(sql) if query.startswith(("INSERT", "UPDATE"))
        )
        self.assertLess(sql.index(locks[-1]), first_write)
        self.assertTrue(any(query.startswith("SAVEPOINT") for query in sql))
        self.assertTrue(any(query.startswith("RELEASE SAVEPOINT") for query in sql))
        print("DB49-L01 observed lock SQL:", *locks, sep="\n")
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, "Approved")
        self.assertEqual(
            self.party.memberships.filter(user=self.applicant, left_at=None).count(), 1
        )

    def test_reject_locks_party_then_request_and_never_writes_membership(self):
        before = list(PartyMembership.objects.order_by("pk").values())
        sql = self.decide_and_capture(False)
        locks = [query for query in sql if "FOR UPDATE" in query]
        self.assertEqual(len(locks), 2)
        self.assertIn('FROM "parties_party"', locks[0])
        self.assertIn('FROM "parties_joinrequest"', locks[1])
        print("DB49-L02 observed lock SQL:", *locks, sep="\n")
        self.assertFalse(
            any(
                query.startswith(("INSERT", "UPDATE", "DELETE"))
                and '"parties_partymembership"' in query
                for query in sql
            )
        )
        self.assertEqual(before, list(PartyMembership.objects.order_by("pk").values()))
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, "Rejected")
