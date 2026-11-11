"""Approval races on real PostgreSQL connections, including observed Party locks."""

from concurrent.futures import ThreadPoolExecutor
from datetime import time, timedelta
from queue import Queue
from threading import Barrier, Event
from time import monotonic
from unittest.mock import patch

from accounts.test_support import force_university_login
from django.db import close_old_connections, connection, connections, transaction
from django.test import Client, TransactionTestCase, skipUnlessDBFeature
from django.urls import reverse
from django.utils import timezone
from venues.models import VenueOpeningHour, VenueSport

from .models import JoinRequest, Party
from .services import PartyError, cancel_party, decide_join_request, edit_party
from .test_join_requests import JoinRequestFixture


@skipUnlessDBFeature("has_select_for_update")
class ApprovalConcurrencyTests(JoinRequestFixture, TransactionTestCase):
    def setUp(self):
        super().setUp()
        self.party.starts_at = (timezone.localtime(self.now) + timedelta(days=2)).replace(
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
        self.first = JoinRequest.objects.create(party=self.party, user=self.applicant)
        self.second = JoinRequest.objects.create(party=self.party, user=self.other)
        # Create the identity before worker setup so the race concerns decisions.
        force_university_login(self.client, self.host)

    def api_worker(self, request_id, status, barrier):
        close_old_connections()
        try:
            client = Client(enforce_csrf_checks=True)
            force_university_login(client, self.host)
            token = client.get(reverse("accounts:csrf")).json()["data"]["csrf_token"]
            with connection.cursor() as cursor:
                cursor.execute("SET lock_timeout = '5s'")
            barrier.wait(timeout=10)
            response = client.post(
                reverse("party-join-request-decision", args=[self.party.pk, request_id]),
                data={"status": status},
                content_type="application/json",
                HTTP_X_CSRFTOKEN=token,
            )
            return response.status_code, response.json()
        finally:
            connections.close_all()

    def race(self, decisions):
        barrier = Barrier(len(decisions))
        with ThreadPoolExecutor(max_workers=len(decisions)) as executor:
            futures = [
                executor.submit(self.api_worker, request_id, status, barrier)
                for request_id, status in decisions
            ]
            return [future.result(timeout=15) for future in futures]

    def service_worker(self, pids):
        close_old_connections()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET lock_timeout = '5s'")
                cursor.execute("SELECT pg_backend_pid()")
                pids.put(cursor.fetchone()[0])
            try:
                result = decide_join_request(
                    party_id=self.party.pk, request_id=self.first.pk, user=self.host, approved=True
                )
                return 200, result.status
            except PartyError as error:
                return error.status, error.code
        finally:
            connections.close_all()

    def wait_for_party_lock(self, pid):
        deadline = monotonic() + 4
        while monotonic() < deadline:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid() = ANY(pg_blocking_pids(%s))", [pid])
                if cursor.fetchone()[0]:
                    return
            Event().wait(0.01)
        self.fail("Approval worker did not wait for this transaction's Party lock")

    def assert_untouched_requests(self):
        for request in (self.first, self.second):
            request.refresh_from_db()
            self.assertEqual(request.status, "Pending")
            self.assertIsNone(request.decided_at)
            self.assertIsNone(request.decided_by_id)
        self.assertEqual(
            set(self.party.memberships.values_list("user_id", flat=True)), {self.host.pk}
        )

    def test_two_approvals_for_last_slot_add_only_one_member(self):
        results = self.race([(self.first.pk, "Approved"), (self.second.pk, "Approved")])
        self.assertEqual(sorted(status for status, _ in results), [200, 409])
        winner = next(body["data"]["id"] for status, body in results if status == 200)
        self.assertEqual(
            next(body["error"]["code"] for status, body in results if status == 409), "PARTY_FULL"
        )
        for request in (self.first, self.second):
            request.refresh_from_db()
            if request.pk == winner:
                self.assertEqual(request.status, "Approved")
                self.assertEqual(request.decided_by_id, self.host.pk)
                self.assertIsNotNone(request.decided_at)
                self.assertTrue(
                    self.party.memberships.filter(user=request.user, left_at=None).exists()
                )
            else:
                self.assertEqual(request.status, "Pending")
                self.assertIsNone(request.decided_at)
                self.assertIsNone(request.decided_by_id)
                self.assertFalse(self.party.memberships.filter(user=request.user).exists())
        self.assertEqual(self.party.memberships.filter(left_at=None).count(), 2)
        detail = self.client.get(reverse("party-detail", args=[self.party.pk])).json()["data"]
        self.assertEqual((detail["remaining_slots"], detail["state"]), (0, "Full"))

    def test_same_request_approved_concurrently_is_decided_once(self):
        results = self.race([(self.first.pk, "Approved"), (self.first.pk, "Approved")])
        self.assertEqual(sorted(status for status, _ in results), [200, 409])
        self.assertEqual(
            next(body["error"]["code"] for status, body in results if status == 409),
            "REQUEST_DECIDED",
        )
        self.first.refresh_from_db()
        self.assertEqual(self.first.status, "Approved")
        self.assertEqual(self.first.decided_by_id, self.host.pk)
        self.assertEqual(
            self.party.memberships.filter(user=self.applicant, left_at=None).count(), 1
        )
        self.assertEqual(self.party.memberships.count(), 2)

    def test_approve_racing_reject_has_one_consistent_decision(self):
        # Regression of the shared decision endpoint, not full B-03 acceptance.
        results = self.race([(self.first.pk, "Approved"), (self.first.pk, "Rejected")])
        self.assertEqual(sorted(status for status, _ in results), [200, 409])
        winner = next(body["data"]["status"] for status, body in results if status == 200)
        self.assertEqual(
            next(body["error"]["code"] for status, body in results if status == 409),
            "REQUEST_DECIDED",
        )
        self.first.refresh_from_db()
        self.assertEqual(self.first.status, winner)
        self.assertEqual(self.first.decided_by_id, self.host.pk)
        self.assertIsNotNone(self.first.decided_at)
        self.assertEqual(
            self.party.memberships.filter(user=self.applicant, left_at=None).count(),
            1 if winner == "Approved" else 0,
        )

    def test_cancel_committed_while_approval_waits_blocks_approval(self):
        pids = Queue()
        with ThreadPoolExecutor(max_workers=1) as executor:
            with transaction.atomic():
                Party.objects.select_for_update().get(pk=self.party.pk)
                future = executor.submit(self.service_worker, pids)
                self.wait_for_party_lock(pids.get(timeout=5))
                cancel_party(party_id=self.party.pk, user=self.host)
            self.assertEqual(future.result(timeout=10), (409, "PARTY_CANCELLED"))
        self.assert_untouched_requests()

    def test_capacity_edit_committed_while_approval_waits_is_rechecked(self):
        pids = Queue()
        with ThreadPoolExecutor(max_workers=1) as executor:
            with transaction.atomic():
                Party.objects.select_for_update().get(pk=self.party.pk)
                future = executor.submit(self.service_worker, pids)
                self.wait_for_party_lock(pids.get(timeout=5))
                edit_party(party_id=self.party.pk, user=self.host, changes={"capacity": 1})
            self.assertEqual(future.result(timeout=10), (409, "PARTY_FULL"))
        self.assert_untouched_requests()

    def test_clock_is_read_after_party_lock_at_exact_start(self):
        pids = Queue()
        with ThreadPoolExecutor(max_workers=1) as executor:
            with patch("parties.services.timezone.now", return_value=self.party.starts_at) as clock:
                with transaction.atomic():
                    Party.objects.select_for_update().get(pk=self.party.pk)
                    future = executor.submit(self.service_worker, pids)
                    self.wait_for_party_lock(pids.get(timeout=5))
                    clock.assert_not_called()
                self.assertEqual(future.result(timeout=10), (409, "PARTY_STARTED"))
        self.assert_untouched_requests()
