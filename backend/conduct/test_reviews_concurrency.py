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
from .test_review_database import ReviewDatabaseFixture


@skipUnlessDBFeature("has_select_for_update")
class ReviewConcurrencyTests(ReviewDatabaseFixture, TransactionTestCase):
    def api_worker(self, reviewer, reviewee, rating, barrier, pids, observations):
        close_old_connections()
        try:
            client = Client(enforce_csrf_checks=True)
            force_university_login(client, reviewer)
            token = client.get(reverse("accounts:csrf")).json()["data"]["csrf_token"]
            pid = None

            def observe_lock(execute, sql, params, many, context):
                nonlocal pid
                if 'FROM "parties_party"' in sql and "FOR UPDATE" in sql:
                    # Django may reconnect at request start: observe the actual lock connection.
                    with context["connection"].cursor() as cursor:
                        cursor.execute("SET lock_timeout = '5s'")
                        cursor.execute("SELECT pg_backend_pid()")
                        pid = cursor.fetchone()[0]
                    pids.put(pid)
                return execute(sql, params, many, context)

            barrier.wait(timeout=10)
            with connection.execute_wrapper(observe_lock):
                response = client.post(
                    self.url(),
                    self.payload(reviewee, rating=rating),
                    content_type="application/json",
                    HTTP_X_CSRFTOKEN=token,
                )
            observations.put(
                {
                    "pid": pid,
                    "reviewer_id": reviewer.pk,
                    "reviewee_id": reviewee.pk,
                    "rating": rating,
                    "http_status": response.status_code,
                    "response": response.json(),
                }
            )
            return response.status_code, response.json()
        finally:
            connections.close_all()

    def race(self, submissions):
        before = self.sql_snapshot()
        barrier = Barrier(len(submissions) + 1)
        pids, observations = Queue(), Queue()
        with ThreadPoolExecutor(max_workers=len(submissions)) as executor:
            with transaction.atomic():
                Party.objects.select_for_update().get(pk=self.party.pk)
                futures = [
                    executor.submit(
                        self.api_worker, reviewer, reviewee, rating, barrier, pids, observations
                    )
                    for reviewer, reviewee, rating in submissions
                ]
                barrier.wait(timeout=10)
                workers = [pids.get(timeout=5) for _ in submissions]
                self.assertEqual(len(set(workers)), len(submissions))
                blocking = [self.wait_for_party_lock(pid, workers) for pid in workers]
                self.assertTrue(
                    any(row["observer_pid"] in row["blocking_pids"] for row in blocking)
                )
            results = [future.result(timeout=15) for future in futures]
        self.evidence(
            sql_before=before,
            blocked_workers=blocking,
            submissions=[observations.get_nowait() for _ in submissions],
            sql_after=self.sql_snapshot(),
        )
        return results

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

    def wait_for_party_lock(self, pid, workers=()):
        deadline = monotonic() + 4
        while monotonic() < deadline:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid(), pg_blocking_pids(%s)", [pid])
                observer, blockers = cursor.fetchone()
                if observer in blockers or set(workers).intersection(blockers):
                    return {"waiting_pid": pid, "blocking_pids": blockers, "observer_pid": observer}
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
