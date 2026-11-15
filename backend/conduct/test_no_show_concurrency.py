"""No-show races on real PostgreSQL connections, including the observed Party lock."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from queue import Queue
from threading import Barrier, Event
from time import monotonic
from unittest.mock import patch

from accounts.test_support import force_university_login
from django.db import close_old_connections, connection, connections, transaction
from django.test import Client, TransactionTestCase, override_settings, skipUnlessDBFeature
from django.urls import reverse
from django.utils import timezone
from parties.models import Party
from parties.services import PartyError

from .models import ConductCreditEvent, NoShowReport
from .policy import CREDIT_BASE, NO_SHOW_DEDUCTION, REPORT_WINDOW_DAYS
from .services import submit_no_show_report
from .test_no_show import NoShowFixture


@override_settings(NO_SHOW_ENABLED=True)
@skipUnlessDBFeature("has_select_for_update")
class NoShowConcurrencyTests(NoShowFixture, TransactionTestCase):
    def api_worker(self, reporter, barrier):
        close_old_connections()
        try:
            client = Client(enforce_csrf_checks=True)
            force_university_login(client, reporter)
            token = client.get(reverse("accounts:csrf")).json()["data"]["csrf_token"]
            with connection.cursor() as cursor:
                cursor.execute("SET lock_timeout = '5s'")
            barrier.wait(timeout=10)
            response = client.post(
                self.no_show_url(),
                {"reported_id": self.member.pk},
                content_type="application/json",
                HTTP_X_CSRFTOKEN=token,
            )
            return response.status_code, response.json()
        finally:
            connections.close_all()

    def race(self, reporters):
        barrier = Barrier(len(reporters))
        with ThreadPoolExecutor(max_workers=len(reporters)) as executor:
            futures = [
                executor.submit(self.api_worker, reporter, barrier) for reporter in reporters
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
                submit_no_show_report(
                    party_id=self.party.pk, reporter=self.host, reported_id=self.member.pk
                )
                return 201, None
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
        self.fail("Report worker did not wait for this transaction's Party lock")

    def test_same_report_submitted_concurrently_is_stored_once(self):
        """IT-US14-NS-53"""
        results = self.race([self.host, self.host])
        self.assertEqual(sorted(status for status, _ in results), [201, 409])
        self.assertEqual(
            next(body["error"]["code"] for status, body in results if status == 409),
            "REPORT_EXISTS",
        )
        self.assertEqual(NoShowReport.objects.count(), 1)

    def test_reporters_racing_over_the_threshold_deduct_once(self):
        """IT-US14-NS-54"""
        results = self.race([self.host, self.peer])
        self.assertEqual([status for status, _ in results], [201, 201])
        self.assertEqual(ConductCreditEvent.objects.count(), 1)
        self.assertEqual(self.credit(), CREDIT_BASE + NO_SHOW_DEDUCTION)

    def test_many_reporters_crossing_the_threshold_at_once_deduct_once(self):
        """IT-US14-NS-58"""
        self.party, others = self.crowded_party(5)
        results = self.race([self.host, *others])
        self.assertEqual([status for status, _ in results], [201] * 6)
        self.assertEqual(NoShowReport.objects.count(), 6)
        self.assertEqual(ConductCreditEvent.objects.count(), 1)
        self.assertEqual(ConductCreditEvent.objects.get().delta, NO_SHOW_DEDUCTION)
        self.assertEqual(self.credit(), CREDIT_BASE + NO_SHOW_DEDUCTION)

    def test_window_is_read_after_the_party_lock(self):
        """IT-US14-NS-55: a request waiting on the lock may cross the window's end."""
        now = timezone.now()
        self.move_times(self.party, now - timedelta(hours=2), now - timedelta(hours=1))
        closed = self.party.ends_at + timedelta(days=REPORT_WINDOW_DAYS, microseconds=1)
        pids = Queue()
        with ThreadPoolExecutor(max_workers=1) as executor:
            with patch("conduct.services.timezone.now", return_value=closed) as clock:
                with transaction.atomic():
                    Party.objects.select_for_update().get(pk=self.party.pk)
                    future = executor.submit(self.service_worker, pids)
                    self.wait_for_party_lock(pids.get(timeout=5))
                    clock.assert_not_called()
                self.assertEqual(future.result(timeout=10), (409, "REPORT_WINDOW_CLOSED"))
        self.assert_nothing_stored()
