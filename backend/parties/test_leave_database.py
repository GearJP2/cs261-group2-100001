"""Task75: API/SQL evidence plus PostgreSQL lock races, not human UAT."""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import time, timedelta
from queue import Queue
from threading import Barrier, Event
from time import monotonic
from unittest.mock import patch

from accounts.test_support import force_university_login
from django.db import DatabaseError, connection, connections, transaction
from django.test import Client, TransactionTestCase, skipUnlessDBFeature
from django.urls import reverse
from django.utils import timezone
from venues.models import VenueOpeningHour, VenueSport

from .models import JoinRequest, Party, PartyMembership
from .services import PartyError, cancel_party, edit_party, leave_party
from .test_leave import LeaveFixture


@skipUnlessDBFeature("has_select_for_update")
class LeaveDatabaseTests(LeaveFixture, TransactionTestCase):
    def setUp(self):
        super().setUp()
        self.party.starts_at = (timezone.localtime() + timedelta(days=2)).replace(
            hour=10, minute=0, second=0, microsecond=0
        )
        self.party.ends_at = self.party.starts_at + timedelta(hours=1)
        self.party.save()
        VenueSport.objects.create(venue=self.party.venue, sport=self.party.sport)
        VenueOpeningHour.objects.create(
            venue=self.party.venue,
            weekday=self.party.starts_at.weekday(),
            opens_at=time(9),
            closes_at=time(18),
        )
        # Create identities before workers so a race only concerns domain writes.
        for user in (self.host, self.applicant):
            self.client_for(user)

    def client_for(self, user):
        client = Client(enforce_csrf_checks=True)
        force_university_login(client, user)
        token = client.get(reverse("accounts:csrf")).json()["data"]["csrf_token"]
        return client, token

    def post(self, client, token, url=None, payload=None):
        return client.post(
            url or reverse("party-leave", args=[self.party.pk]),
            data={} if payload is None else payload,
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )

    def observe(self, **data):
        print("DB75_EVIDENCE " + json.dumps({"case": self._testMethodName, **data}, default=str))

    def domain_snapshot(self):
        return {
            "sql": self.snapshot(),
            "requests": list(JoinRequest.objects.filter(party=self.party).order_by("pk").values()),
        }

    def test_api_leave_retry_sql_history_and_count(self):
        before = self.domain_snapshot()
        client, token = self.client_for(self.applicant)
        first = self.post(client, token)
        after = self.domain_snapshot()
        retry = self.post(client, token)
        self.assertEqual((first.status_code, retry.status_code), (200, 200))
        self.assertEqual(first.json(), retry.json())
        self.assertEqual(after, self.domain_snapshot())
        self.assertEqual(after["requests"], before["requests"])
        self.assertEqual(
            (after["sql"][0]["active_count"], after["sql"][0]["remaining_slots"]), (1, 1)
        )
        for old, new in zip(before["sql"], after["sql"], strict=True):
            self.assertEqual(
                {
                    k: v
                    for k, v in old.items()
                    if k not in {"left_at", "active_count", "remaining_slots"}
                },
                {
                    k: v
                    for k, v in new.items()
                    if k not in {"left_at", "active_count", "remaining_slots"}
                },
            )
        self.member.refresh_from_db()
        self.assertIsNotNone(self.member.left_at)
        self.assertGreaterEqual(self.member.left_at, self.member.joined_at)
        self.assertIsNone(self.party.memberships.get(user=self.host).left_at)
        self.observe(
            before=before,
            request={"method": "POST", "payload": {}},
            responses=[first.json(), retry.json()],
            http_statuses=[200, 200],
            after=after,
        )

    def test_api_write_failure_returns_500_and_rolls_back_sql(self):
        client, token = self.client_for(self.applicant)
        client.raise_request_exception = False
        before = self.domain_snapshot()
        original = PartyMembership.save

        def fail_after_write(member, *args, **kwargs):
            original(member, *args, **kwargs)
            raise DatabaseError("Task75 injected error after actual UPDATE")

        with patch.object(PartyMembership, "save", fail_after_write):
            response = self.post(client, token)
        self.assertEqual(response.status_code, 500)
        self.assertEqual(before, self.domain_snapshot())
        self.observe(
            before=before,
            after=self.domain_snapshot(),
            http_status=500,
            fault="injected DatabaseError after real UPDATE; not a real DB constraint fault",
        )

    def test_detail_refresh_after_replacement_approval_uses_current_count(self):
        request = JoinRequest.objects.create(party=self.party, user=self.other)
        member_client, token = self.client_for(self.applicant)
        before = self.domain_snapshot()
        self.assertEqual(self.post(member_client, token).status_code, 200)
        host_client, host_token = self.client_for(self.host)
        decision = self.post(
            host_client,
            host_token,
            reverse("party-join-request-decision", args=[self.party.pk, request.pk]),
            {"status": "Approved"},
        )
        self.assertEqual(decision.status_code, 200)
        detail_response = member_client.get(reverse("party-detail", args=[self.party.pk]))
        self.assertEqual(detail_response.status_code, 200)
        detail = detail_response.json()["data"]
        self.assertEqual(
            (
                detail["is_member"],
                detail["member_count"],
                detail["remaining_slots"],
                detail["state"],
            ),
            (False, 2, 0, "Full"),
        )
        self.assertEqual(
            member_client.get(reverse("party-members", args=[self.party.pk])).status_code, 403
        )
        self.observe(
            before=before,
            decision=decision.json(),
            detail={
                key: detail[key]
                for key in ("is_member", "member_count", "remaining_slots", "state")
            },
            after=self.domain_snapshot(),
        )

    def api_worker(self, user, url, payload, barrier, pids):
        connections.close_all()
        try:
            client, token = self.client_for(user)
            pid = None

            def capture(execute, sql, params, many, context):
                nonlocal pid
                if 'FROM "parties_party"' in sql and "FOR UPDATE" in sql:
                    with context["connection"].cursor() as cursor:
                        cursor.execute("SET lock_timeout = '5s'")
                        cursor.execute("SELECT pg_backend_pid()")
                        pid = cursor.fetchone()[0]
                    pids.put(pid)
                return execute(sql, params, many, context)

            barrier.wait(timeout=10)
            with connection.execute_wrapper(capture):
                response = self.post(client, token, url, payload)
            return {
                "pid": pid,
                "url": url,
                "payload": payload,
                "http_status": response.status_code,
                "body": response.json(),
            }
        finally:
            connections.close_all()

    def wait_for_lock(self, pid, workers=()):
        deadline = monotonic() + 5
        while monotonic() < deadline:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid(), pg_blocking_pids(%s)", [pid])
                observer, blockers = cursor.fetchone()
            if observer in blockers or set(workers).intersection(blockers):
                return {"waiting_pid": pid, "blocking_pids": blockers, "observer_pid": observer}
            Event().wait(0.01)
        self.fail("No observed Party lock contention")

    def race(self, actions):
        before = self.domain_snapshot()
        barrier, pids = Barrier(len(actions) + 1), Queue()
        with ThreadPoolExecutor(max_workers=len(actions)) as pool:
            with transaction.atomic():
                Party.objects.select_for_update().get(pk=self.party.pk)
                futures = [
                    pool.submit(self.api_worker, *action, barrier, pids) for action in actions
                ]
                barrier.wait(timeout=10)
                workers = [pids.get(timeout=5) for _ in actions]
                self.assertEqual(len(set(workers)), len(actions))
                blocking = [self.wait_for_lock(pid, workers) for pid in workers]
                self.assertTrue(
                    any(row["observer_pid"] in row["blocking_pids"] for row in blocking)
                )
            results = [future.result(timeout=15) for future in futures]
        self.observe(
            before=before, blocked_workers=blocking, responses=results, after=self.domain_snapshot()
        )
        return results

    def test_two_api_leaves_return_same_timestamp_and_free_one_slot(self):
        url = reverse("party-leave", args=[self.party.pk])
        results = self.race([(self.applicant, url, {}), (self.applicant, url, {})])
        self.assertEqual([r["http_status"] for r in results], [200, 200])
        self.assertEqual(results[0]["body"], results[1]["body"])
        self.assertEqual(self.snapshot()[0]["active_count"], 1)
        self.assertEqual(PartyMembership.objects.filter(party=self.party).count(), 2)

    def test_api_leave_races_approve_without_overcapacity(self):
        request = JoinRequest.objects.create(party=self.party, user=self.other)
        results = self.race(
            [
                (self.applicant, reverse("party-leave", args=[self.party.pk]), {}),
                (
                    self.host,
                    reverse("party-join-request-decision", args=[self.party.pk, request.pk]),
                    {"status": "Approved"},
                ),
            ]
        )
        leave, approval = results
        self.assertEqual(leave["http_status"], 200)
        request.refresh_from_db()
        if approval["http_status"] == 200:
            self.assertEqual(request.status, "Approved")
            self.assertTrue(self.party.memberships.filter(user=self.other, left_at=None).exists())
            self.assertEqual(self.snapshot()[0]["active_count"], 2)
        else:
            self.assertEqual(
                (approval["http_status"], approval["body"]["error"]["code"]), (409, "PARTY_FULL")
            )
            self.assertEqual(request.status, "Pending")
            self.assertFalse(self.party.memberships.filter(user=self.other).exists())
            self.assertEqual(self.snapshot()[0]["active_count"], 1)

    def ordered_worker(self, operation, pids):
        connections.close_all()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET lock_timeout = '5s'")
                cursor.execute("SELECT pg_backend_pid()")
                pids.put(cursor.fetchone()[0])
            try:
                operation()
                return "OK"
            except PartyError as error:
                return error.code
        finally:
            connections.close_all()

    def ordered(self, waiting, first):
        before, pids = self.domain_snapshot(), Queue()
        with ThreadPoolExecutor(max_workers=1) as pool:
            with transaction.atomic():
                Party.objects.select_for_update().get(pk=self.party.pk)
                future = pool.submit(self.ordered_worker, waiting, pids)
                blocking = self.wait_for_lock(pids.get(timeout=5))
                first()
            result = future.result(timeout=10)
        self.observe(
            before=before, blocking=blocking, worker_result=result, after=self.domain_snapshot()
        )
        return result

    def test_cancel_before_waiting_leave_preserves_membership(self):
        result = self.ordered(
            lambda: leave_party(party_id=self.party.pk, user=self.applicant),
            lambda: cancel_party(party_id=self.party.pk, user=self.host),
        )
        self.assertEqual(result, "PARTY_CANCELLED")
        self.member.refresh_from_db()
        self.assertIsNone(self.member.left_at)

    def test_leave_before_waiting_cancel_keeps_leave_history(self):
        result = self.ordered(
            lambda: cancel_party(party_id=self.party.pk, user=self.host),
            lambda: leave_party(party_id=self.party.pk, user=self.applicant),
        )
        self.assertEqual(result, "OK")
        self.member.refresh_from_db()
        self.party.refresh_from_db()
        self.assertIsNotNone(self.member.left_at)
        self.assertIsNotNone(self.party.cancelled_at)

    def test_leave_before_waiting_edit_allows_capacity_one(self):
        result = self.ordered(
            lambda: edit_party(party_id=self.party.pk, user=self.host, changes={"capacity": 1}),
            lambda: leave_party(party_id=self.party.pk, user=self.applicant),
        )
        self.assertEqual(result, "OK")
        self.party.refresh_from_db()
        self.assertEqual((self.party.capacity, self.snapshot()[0]["active_count"]), (1, 1))

    def test_edit_before_waiting_leave_cannot_shrink_below_active(self):
        def edit_first():
            with self.assertRaises(PartyError) as caught:
                edit_party(party_id=self.party.pk, user=self.host, changes={"capacity": 1})
            self.assertEqual(caught.exception.code, "CAPACITY_TOO_SMALL")

        result = self.ordered(
            lambda: leave_party(party_id=self.party.pk, user=self.applicant), edit_first
        )
        self.assertEqual(result, "OK")
        self.party.refresh_from_db()
        self.assertEqual((self.party.capacity, self.snapshot()[0]["active_count"]), (2, 1))
