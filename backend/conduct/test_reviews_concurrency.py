"""Review races on real PostgreSQL connections, including the observed Party lock."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from queue import Queue
from threading import Barrier, Event
from time import monotonic
from unittest.mock import patch

from accounts.test_support import force_university_login
from django.db import close_old_connections, connection, connections, transaction
from django.test import Client, TransactionTestCase, skipUnlessDBFeature
from django.urls import reverse
from django.utils import timezone
from parties.models import Party
from parties.services import PartyError

from .models import PartyReview
from .services import submit_review
from .test_reviews import ReviewFixture


@skipUnlessDBFeature("has_select_for_update")
class ReviewConcurrencyTests(ReviewFixture, TransactionTestCase):
    def api_worker(self, reviewer, reviewee, rating, barrier):
        close_old_connections()
        try:
            client = Client(enforce_csrf_checks=True)
            force_university_login(client, reviewer)
            token = client.get(reverse("accounts:csrf")).json()["data"]["csrf_token"]
            with connection.cursor() as cursor:
                cursor.execute("SET lock_timeout = '5s'")
            barrier.wait(timeout=10)
            response = client.post(
                self.url(),
                self.payload(reviewee, rating=rating),
                content_type="application/json",
                HTTP_X_CSRFTOKEN=token,
            )
            return response.status_code, response.json()
        finally:
            connections.close_all()

    def race(self, submissions):
        barrier = Barrier(len(submissions))
        with ThreadPoolExecutor(max_workers=len(submissions)) as executor:
            futures = [
                executor.submit(self.api_worker, reviewer, reviewee, rating, barrier)
                for reviewer, reviewee, rating in submissions
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
                submit_review(
                    party_id=self.party.pk,
                    reviewer=self.host,
                    reviewee_id=self.member.pk,
                    rating=4,
                    comment="ดีมาก",
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
        self.fail("Review worker did not wait for this transaction's Party lock")

    def test_same_review_submitted_concurrently_is_stored_once(self):
        """IT-US14-DB-41"""
        results = self.race([(self.host, self.member, 4), (self.host, self.member, 4)])
        self.assertEqual(sorted(status for status, _ in results), [201, 409])
        self.assertEqual(
            next(body["error"]["code"] for status, body in results if status == 409),
            "REVIEW_EXISTS",
        )
        self.assertEqual(PartyReview.objects.count(), 1)
        self.assertEqual(self.cache(self.member), (4, 1))

    def test_different_reviewers_do_not_lose_rating_cache_updates(self):
        """IT-US14-DB-42"""
        results = self.race([(self.host, self.member, 5), (self.peer, self.member, 2)])
        self.assertEqual([status for status, _ in results], [201, 201])
        self.assertEqual(PartyReview.objects.count(), 2)
        self.assertEqual(self.cache(self.member), (7, 2))

    def test_state_is_read_after_the_party_lock_at_the_exact_end(self):
        """IT-US14-DB-43: a request waiting on the lock may cross ends_at."""
        now = timezone.now()
        self.move_times(self.party, now - timedelta(hours=1), now + timedelta(hours=1))
        pids = Queue()
        with ThreadPoolExecutor(max_workers=1) as executor:
            with patch("conduct.services.timezone.now", return_value=self.party.ends_at) as clock:
                with transaction.atomic():
                    Party.objects.select_for_update().get(pk=self.party.pk)
                    future = executor.submit(self.service_worker, pids)
                    self.wait_for_party_lock(pids.get(timeout=5))
                    clock.assert_not_called()
                self.assertEqual(future.result(timeout=10), (201, None))
        self.assertEqual(self.cache(self.member), (4, 1))
