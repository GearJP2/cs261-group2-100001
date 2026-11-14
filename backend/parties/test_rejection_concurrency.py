"""Task52: HTTP decisions waiting on observed PostgreSQL Party locks."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from queue import Queue
from threading import Event
from time import monotonic

from accounts.test_support import force_university_login
from django.db import close_old_connections, connection, connections, transaction
from django.test import Client, TransactionTestCase, skipUnlessDBFeature
from django.urls import reverse
from django.utils import timezone

from .models import JoinRequest, Party
from .services import cancel_party, decide_join_request
from .test_join_requests import JoinRequestFixture


@skipUnlessDBFeature("has_select_for_update")
class RejectRequestConcurrencyTests(JoinRequestFixture, TransactionTestCase):
    def setUp(self):
        super().setUp()
        self.pending = JoinRequest.objects.create(party=self.party, user=self.applicant)
        # Provision identity before starting the workers; only decisions should race.
        force_university_login(self.client, self.host)
        self.memberships_before = self.membership_snapshot()

    def api_worker(self, status, pids):
        close_old_connections()
        try:
            client = Client(enforce_csrf_checks=True)
            force_university_login(client, self.host)
            token = client.get(reverse("accounts:csrf")).json()["data"]["csrf_token"]

            def observe_lock(execute, sql, params, many, context):
                if 'FROM "parties_party"' in sql and "FOR UPDATE" in sql:
                    # HTTP signals can reconnect, so inspect the actual lock connection.
                    with context["connection"].cursor() as cursor:
                        cursor.execute("SET lock_timeout = '5s'")
                        cursor.execute("SELECT pg_backend_pid()")
                        pids.put(cursor.fetchone()[0])
                return execute(sql, params, many, context)

            with connection.execute_wrapper(observe_lock):
                response = client.post(
                    reverse("party-join-request-decision", args=[self.party.pk, self.pending.pk]),
                    data={"status": status},
                    content_type="application/json",
                    HTTP_X_CSRFTOKEN=token,
                )
            return response.status_code, response.json()
        finally:
            connections.close_all()

    def wait_for_lock(self, pid, workers):
        deadline = monotonic() + 4
        while monotonic() < deadline:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid(), pg_blocking_pids(%s)", [pid])
                observer, blockers = cursor.fetchone()
            if observer in blockers or set(workers).intersection(blockers):
                return
            Event().wait(0.01)
        self.fail("Decision did not wait for the held Party lock")

    def decisions_behind_lock(self, statuses, change=None):
        pids = Queue()
        with ThreadPoolExecutor(max_workers=len(statuses)) as executor:
            with transaction.atomic():
                Party.objects.select_for_update().get(pk=self.party.pk)
                futures = [executor.submit(self.api_worker, status, pids) for status in statuses]
                workers = [pids.get(timeout=5) for _ in statuses]
                self.assertEqual(len(set(workers)), len(statuses))
                for pid in workers:
                    self.wait_for_lock(pid, workers)
                if change is not None:
                    change()
            return [future.result(timeout=10) for future in futures]

    def assert_pending_unchanged(self, before):
        self.assertEqual(JoinRequest.objects.values().get(pk=self.pending.pk), before)
        self.assertEqual(self.membership_snapshot(), self.memberships_before)

    def assert_rejected(self):
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, "Rejected")
        self.assertEqual(self.pending.decided_by_id, self.host.pk)
        self.assertIsNotNone(self.pending.decided_at)
        self.assertEqual(self.membership_snapshot(), self.memberships_before)

    def test_two_rejects_decide_once_without_changing_members_or_slots(self):
        before_party = Party.objects.values().get(pk=self.party.pk)
        results = self.decisions_behind_lock(["Rejected", "Rejected"])
        self.assertEqual(sorted(status for status, _ in results), [200, 409])
        self.assertEqual(
            next(body for status, body in results if status == 200),
            {"data": {"id": self.pending.pk, "status": "Rejected"}},
        )
        self.assertEqual(
            next(body["error"]["code"] for status, body in results if status == 409),
            "REQUEST_DECIDED",
        )
        self.assert_rejected()
        self.assertEqual(Party.objects.values().get(pk=self.party.pk), before_party)
        detail = self.client.get(reverse("party-detail", args=[self.party.pk])).json()["data"]
        self.assertEqual((detail["member_count"], detail["remaining_slots"]), (1, 1))

    def test_rejection_committed_first_prevents_waiting_approval(self):
        committed = {}

        def reject():
            decide_join_request(
                party_id=self.party.pk, request_id=self.pending.pk, user=self.host, approved=False
            )
            committed.update(JoinRequest.objects.values().get(pk=self.pending.pk))

        [(status, body)] = self.decisions_behind_lock(["Approved"], reject)
        self.assertEqual((status, body["error"]["code"]), (409, "REQUEST_DECIDED"))
        self.assertEqual(JoinRequest.objects.values().get(pk=self.pending.pk), committed)
        self.assert_rejected()

    def test_cancellation_committed_first_prevents_waiting_rejection(self):
        before = JoinRequest.objects.values().get(pk=self.pending.pk)
        [(status, body)] = self.decisions_behind_lock(
            ["Rejected"], lambda: cancel_party(party_id=self.party.pk, user=self.host)
        )
        self.assertEqual((status, body["error"]["code"]), (409, "PARTY_CANCELLED"))
        self.assert_pending_unchanged(before)

    def test_new_start_time_is_rechecked_after_waiting_for_lock(self):
        before = JoinRequest.objects.values().get(pk=self.pending.pk)

        def move_start_into_past():
            Party.objects.filter(pk=self.party.pk).update(
                starts_at=timezone.now() - timedelta(seconds=1)
            )

        [(status, body)] = self.decisions_behind_lock(["Rejected"], move_start_into_past)
        self.assertEqual((status, body["error"]["code"]), (409, "PARTY_STARTED"))
        self.assert_pending_unchanged(before)

    def test_party_becoming_full_while_waiting_still_allows_reject(self):
        [(status, body)] = self.decisions_behind_lock(
            ["Rejected"], lambda: Party.objects.filter(pk=self.party.pk).update(capacity=1)
        )
        self.assertEqual(status, 200)
        self.assertEqual(body, {"data": {"id": self.pending.pk, "status": "Rejected"}})
        self.assert_rejected()
        detail = self.client.get(reverse("party-detail", args=[self.party.pk])).json()["data"]
        self.assertEqual(
            (detail["member_count"], detail["remaining_slots"], detail["state"]), (1, 0, "Full")
        )
