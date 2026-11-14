"""Task69 service/SQL checks; HTTP and full manual race matrix belong to Task75."""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from queue import Queue
from time import monotonic
from unittest.mock import patch

from django.db import DatabaseError, connection, connections, transaction
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature

from .models import JoinRequest, Party, PartyMembership
from .services import (
    PartyError,
    count_active_members,
    decide_join_request,
    get_party_state,
    leave_party,
    submit_join_request,
)
from .test_join_requests import JoinRequestFixture


class LeaveFixture(JoinRequestFixture):
    def setUp(self):
        super().setUp()
        self.member = PartyMembership.objects.create(party=self.party, user=self.applicant)
        self.approved = JoinRequest.objects.create(
            party=self.party,
            user=self.applicant,
            status=JoinRequest.Status.APPROVED,
            decided_at=self.now,
            decided_by=self.host,
        )

    def snapshot(self):
        sql = Path(__file__).resolve().parents[2] / "database/seeds/us4_leave_snapshot.sql"
        with connection.cursor() as cursor:
            cursor.execute(sql.read_text().replace(":party_id", "%s"), [self.party.pk])
            names = [column[0] for column in cursor.description]
            return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]

    def evidence(self, **observed):
        print(
            "DB69_EVIDENCE " + json.dumps({"case": self._testMethodName, **observed}, default=str)
        )

    def assert_error(self, user, code, status):
        before = self.snapshot()
        with self.assertRaises(PartyError) as caught:
            leave_party(party_id=self.party.pk, user=user)
        self.assertEqual((caught.exception.code, caught.exception.status), (code, status))
        self.assertEqual(self.snapshot(), before)


class LeaveServiceTests(LeaveFixture, TestCase):
    def test_soft_leave_and_retry_preserve_history_and_query_count(self):
        before = self.snapshot()
        request_before = list(JoinRequest.objects.values())
        joined_at = self.member.joined_at
        with patch("parties.services.timezone.now", return_value=self.now):
            left = leave_party(party_id=self.party.pk, user=self.applicant)
        after = self.snapshot()
        self.assertEqual(
            (left.pk, left.joined_at, left.left_at), (self.member.pk, joined_at, self.now)
        )
        self.assertEqual((before[0]["active_count"], after[0]["active_count"]), (2, 1))
        self.assertEqual((before[0]["remaining_slots"], after[0]["remaining_slots"]), (0, 1))
        self.assertEqual(count_active_members(self.party), 1)
        self.assertEqual(get_party_state(self.party), "Open")
        self.assertEqual(len(before), len(after))
        self.assertEqual(list(JoinRequest.objects.values()), request_before)
        self.party.refresh_from_db()
        self.assertEqual(self.party.capacity, 2)
        self.assertIsNone(self.party.memberships.get(user=self.host).left_at)
        # Repeat succeeds without UPDATE, even after cancellation/start/end.
        self.party.cancelled_at = self.now
        self.party.starts_at = self.now - timedelta(hours=2)
        self.party.ends_at = self.now - timedelta(hours=1)
        self.party.save()
        with patch.object(PartyMembership, "save", side_effect=AssertionError("retry wrote")):
            retry = leave_party(party_id=self.party.pk, user=self.applicant)
        self.assertEqual(retry.left_at, self.now)
        self.evidence(sql_before=before, sql_after=after, retry_left_at=retry.left_at)

    def test_open_party_allows_leave(self):
        self.party.capacity = 3
        self.party.save()
        self.assertEqual(get_party_state(self.party), "Open")
        leave_party(party_id=self.party.pk, user=self.applicant)
        self.assertEqual(count_active_members(self.party), 1)

    def test_host_and_nonmember_rejected_before_state_checks(self):
        self.party.cancelled_at = self.now
        self.party.save()
        self.assert_error(self.host, "HOST_CANNOT_LEAVE", 403)
        self.assert_error(self.other, "NOT_MEMBER", 403)

    def test_pending_and_rejected_applicants_are_not_members(self):
        for status in (JoinRequest.Status.PENDING, JoinRequest.Status.REJECTED):
            with self.subTest(status=status):
                JoinRequest.objects.filter(party=self.party, user=self.other).delete()
                JoinRequest.objects.create(
                    party=self.party,
                    user=self.other,
                    status=status,
                    decided_at=self.now if status == JoinRequest.Status.REJECTED else None,
                )
                self.assert_error(self.other, "NOT_MEMBER", 403)

    def test_cancelled_precedes_started_and_preserves_membership(self):
        self.party.cancelled_at = self.now
        self.party.save()
        with patch("parties.services.timezone.now", return_value=self.party.ends_at):
            self.assert_error(self.applicant, "PARTY_CANCELLED", 409)

    def test_start_boundary_and_completed_reject_first_leave(self):
        for instant in (self.party.starts_at, self.party.ends_at):
            with (
                self.subTest(instant=instant),
                patch("parties.services.timezone.now", return_value=instant),
            ):
                self.assert_error(self.applicant, "PARTY_STARTED", 409)

    def test_unknown_party(self):
        with self.assertRaises(PartyError) as caught:
            leave_party(party_id=self.party.pk + 999, user=self.applicant)
        self.assertEqual((caught.exception.code, caught.exception.status), ("NOT_FOUND", 404))

    def test_database_error_after_write_rolls_back(self):
        before = self.snapshot()
        original = PartyMembership.save

        def write_then_fail(member, *args, **kwargs):
            original(member, *args, **kwargs)
            raise DatabaseError("Task69 injected failure after UPDATE")

        with patch.object(PartyMembership, "save", write_then_fail):
            with self.assertRaises(DatabaseError):
                leave_party(party_id=self.party.pk, user=self.applicant)
        after = self.snapshot()
        self.assertEqual(before, after)
        self.evidence(sql_before=before, sql_after=after, error="injected after real UPDATE")

    def test_rejoin_requires_approval_then_allows_new_leave_cycle(self):
        first = leave_party(party_id=self.party.pk, user=self.applicant).left_at
        request = submit_join_request(party_id=self.party.pk, user=self.applicant)
        self.assertEqual(request.pk, self.approved.pk)
        self.assertEqual(count_active_members(self.party), 1)
        decide_join_request(
            party_id=self.party.pk, request_id=request.pk, user=self.host, approved=True
        )
        self.assertEqual(count_active_members(self.party), 2)
        instant = first + timedelta(seconds=1)
        with patch("parties.services.timezone.now", return_value=instant):
            left = leave_party(party_id=self.party.pk, user=self.applicant)
        self.assertEqual((left.pk, left.left_at), (self.member.pk, instant))
        self.assertEqual(PartyMembership.objects.filter(party=self.party).count(), 2)


@skipUnlessDBFeature("has_select_for_update")
class LeaveLockTests(LeaveFixture, TransactionTestCase):
    def worker(self, operation, pids):
        connections.close_all()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET lock_timeout = '5s'")
                cursor.execute("SELECT pg_backend_pid()")
                pids.put(cursor.fetchone()[0])
            return operation()
        finally:
            connections.close_all()

    def wait_until_blocked(self, pid):
        deadline = monotonic() + 5
        while monotonic() < deadline:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid(), pg_blocking_pids(%s)", [pid])
                observer, blockers = cursor.fetchone()
            if observer in blockers:
                return {"waiting_pid": pid, "blocking_pids": blockers, "observer_pid": observer}
        self.fail("Worker did not wait on the coordinator Party lock")

    def run_waiting(self, operation, while_locked):
        before = self.snapshot()
        pids = Queue()
        with ThreadPoolExecutor(max_workers=1) as pool:
            with transaction.atomic():
                Party.objects.select_for_update().get(pk=self.party.pk)
                future = pool.submit(self.worker, operation, pids)
                blocking = self.wait_until_blocked(pids.get(timeout=5))
                while_locked()
            result = future.result(timeout=10)
        self.evidence(sql_before=before, blocking=blocking, sql_after=self.snapshot())
        return result

    def test_two_leaves_update_once_after_real_lock_wait(self):
        first = []
        second = self.run_waiting(
            lambda: leave_party(party_id=self.party.pk, user=self.applicant),
            lambda: first.append(leave_party(party_id=self.party.pk, user=self.applicant)),
        )
        self.assertEqual(first[0].left_at, second.left_at)
        self.assertEqual(count_active_members(self.party), 1)
        self.assertEqual(PartyMembership.objects.filter(party=self.party).count(), 2)

    def test_approve_waits_for_leave_then_reads_freed_slot(self):
        request = JoinRequest.objects.create(party=self.party, user=self.other)
        result = self.run_waiting(
            lambda: decide_join_request(
                party_id=self.party.pk, request_id=request.pk, user=self.host, approved=True
            ),
            lambda: leave_party(party_id=self.party.pk, user=self.applicant),
        )
        self.assertEqual(result.status, JoinRequest.Status.APPROVED)
        self.assertEqual(count_active_members(self.party), self.party.capacity)

    def test_leave_rechecks_time_after_lock(self):
        def start_party():
            Party.objects.filter(pk=self.party.pk).update(starts_at=self.now - timedelta(seconds=1))

        with self.assertRaises(PartyError) as caught:
            self.run_waiting(
                lambda: leave_party(party_id=self.party.pk, user=self.applicant), start_party
            )
        self.assertEqual(caught.exception.code, "PARTY_STARTED")
        self.member.refresh_from_db()
        self.assertIsNone(self.member.left_at)

    def test_approve_before_waiting_leave_sees_full_party(self):
        request = JoinRequest.objects.create(party=self.party, user=self.other)

        def reject_full_approval():
            with self.assertRaises(PartyError) as caught:
                decide_join_request(
                    party_id=self.party.pk,
                    request_id=request.pk,
                    user=self.host,
                    approved=True,
                )
            self.assertEqual(caught.exception.code, "PARTY_FULL")

        self.run_waiting(
            lambda: leave_party(party_id=self.party.pk, user=self.applicant),
            reject_full_approval,
        )
        request.refresh_from_db()
        self.assertEqual(request.status, JoinRequest.Status.PENDING)
        self.assertFalse(PartyMembership.objects.filter(party=self.party, user=self.other).exists())
        self.assertEqual(count_active_members(self.party), 1)
