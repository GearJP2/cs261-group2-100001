"""US3 API and PostgreSQL concurrency tests; sessions are local test fixtures."""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from queue import Queue
from threading import Barrier, Event
from time import monotonic
from unittest.mock import patch

from accounts.test_support import force_university_login
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.db import close_old_connections, connection, connections, transaction
from django.test import Client, TestCase, TransactionTestCase, skipUnlessDBFeature
from django.urls import reverse
from django.utils import timezone
from venues.models import Sport, Venue

from .models import JoinRequest, Party, PartyMembership
from .services import count_active_members, submit_join_request


class JoinRequestFixture:
    def setUp(self):
        super().setUp()
        users = get_user_model()
        self.host = users.objects.create_user("host")
        self.applicant = users.objects.create_user("applicant")
        self.other = users.objects.create_user("other")
        self.now = timezone.now()
        self.party = Party.objects.create(
            host=self.host,
            sport=Sport.objects.create(name="Badminton"),
            venue=Venue.objects.create(name="Court", location_text="Campus"),
            title="After class",
            starts_at=self.now + timedelta(days=1),
            ends_at=self.now + timedelta(days=1, hours=1),
            capacity=2,
        )
        PartyMembership.objects.create(party=self.party, user=self.host)
        self.create_url = reverse("party-join-request-create", args=[self.party.pk])
        self.mine_url = reverse("party-join-request-me", args=[self.party.pk])

    def membership_snapshot(self):
        return list(self.party.memberships.order_by("pk").values())

    def decision_sql_snapshot(self):
        sql = Path(__file__).resolve().parents[2] / "database/seeds/us10_decision_snapshot.sql"
        with connection.cursor() as cursor:
            cursor.execute(
                sql.read_text(encoding="utf-8").replace(":party_id", "%s"), [self.party.pk]
            )
            names = [column[0] for column in cursor.description]
            return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]

    def emit_decision_evidence(self, case, **observed):
        print(
            "DB57_EVIDENCE "
            + json.dumps(
                {"case": case, "at": timezone.localtime().isoformat(), **observed},
                default=str,
                ensure_ascii=True,
            )
        )

    def assert_membership_and_slots_unchanged(self, memberships, capacity):
        self.assertEqual(self.membership_snapshot(), memberships)
        self.party.refresh_from_db()
        self.assertEqual(self.party.capacity, capacity)
        active_count = sum(row["left_at"] is None for row in memberships)
        self.assertEqual(count_active_members(self.party), active_count)
        client = Client()
        force_university_login(client, self.applicant)
        response = client.get(reverse("party-detail", args=[self.party.pk]))
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["member_count"], active_count)
        self.assertEqual(data["remaining_slots"], capacity - active_count)


class JoinRequestApiTests(JoinRequestFixture, TestCase):
    def setUp(self):
        super().setUp()
        force_university_login(self.client, self.applicant)

    def post_request(self, **kwargs):
        return self.client.post(
            self.create_url, data="{}", content_type="application/json", **kwargs
        )

    def assert_error(self, response, status, code):
        self.assertEqual(response.status_code, status)
        self.assertEqual(set(response.json()), {"error"})
        self.assertEqual(set(response.json()["error"]), {"code", "message"})
        self.assertEqual(response.json()["error"]["code"], code)

    def test_create_pending_and_read_own_request_without_consuming_capacity(self):
        memberships = list(PartyMembership.objects.values())
        response = self.post_request()
        self.assertEqual(response.status_code, 201)
        join_request = JoinRequest.objects.get(party=self.party, user=self.applicant)
        self.assertEqual(
            response.json(),
            {
                "data": {
                    "id": join_request.pk,
                    "party_id": self.party.pk,
                    "status": "Pending",
                    "created_at": timezone.localtime(join_request.created_at).isoformat(),
                }
            },
        )
        self.assertIsNone(join_request.decided_at)
        self.assertIsNone(join_request.decided_by_id)
        self.assertEqual(list(PartyMembership.objects.values()), memberships)
        self.party.refresh_from_db()
        self.assertEqual(self.party.capacity, 2)
        detail = self.client.get(reverse("party-detail", args=[self.party.pk])).json()["data"]
        self.assertEqual((detail["member_count"], detail["remaining_slots"]), (1, 1))
        self.assertFalse(detail["is_member"])
        data = response.json()["data"]
        data.pop("party_id")
        self.assertEqual(self.client.get(self.mine_url).json(), {"data": data})
        self.assertIn("no-store", response["Cache-Control"])

    def test_get_returns_null_and_cannot_read_another_users_request(self):
        other = JoinRequest.objects.create(party=self.party, user=self.other)
        response = self.client.get(
            self.mine_url, {"user_id": self.other.pk, "request_id": other.pk}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"data": None})
        self.assertEqual(JoinRequest.objects.count(), 1)

    def test_get_is_scoped_to_party_and_readable_after_cancellation(self):
        self.post_request()
        other_party = Party.objects.create(
            host=self.host,
            sport=self.party.sport,
            venue=self.party.venue,
            title="Other",
            starts_at=self.party.starts_at,
            ends_at=self.party.ends_at,
            capacity=2,
        )
        self.assertEqual(
            self.client.get(reverse("party-join-request-me", args=[other_party.pk])).json(),
            {"data": None},
        )
        self.party.cancelled_at = self.now
        self.party.save(update_fields=["cancelled_at"])
        self.assertEqual(self.client.get(self.mine_url).json()["data"]["status"], "Pending")

    def test_duplicate_pending_is_conflict_without_changing_request(self):
        self.post_request()
        before = JoinRequest.objects.values().get()
        self.assert_error(self.post_request(), 409, "REQUEST_EXISTS")
        self.assertEqual(JoinRequest.objects.values().get(), before)

    def test_rejected_request_is_reopened_in_same_row(self):
        request = JoinRequest.objects.create(
            party=self.party,
            user=self.applicant,
            status="Rejected",
            decided_at=self.now,
            decided_by=self.host,
        )
        old_created_at = self.now - timedelta(days=1)
        JoinRequest.objects.filter(pk=request.pk).update(created_at=old_created_at)
        response = self.post_request()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["data"]["id"], request.pk)
        request.refresh_from_db()
        self.assertEqual(request.status, "Pending")
        self.assertGreater(request.created_at, old_created_at)
        self.assertIsNone(request.decided_at)
        self.assertIsNone(request.decided_by_id)
        self.assertEqual(JoinRequest.objects.count(), 1)
        self.assertEqual(count_active_members(self.party), 1)

    def test_approved_former_member_can_reapply_without_reactivating_membership(self):
        membership = PartyMembership.objects.create(
            party=self.party, user=self.applicant, left_at=self.now
        )
        request = JoinRequest.objects.create(
            party=self.party,
            user=self.applicant,
            status="Approved",
            decided_at=self.now,
            decided_by=self.host,
        )
        self.assertEqual(self.post_request().status_code, 201)
        request.refresh_from_db()
        membership.refresh_from_db()
        self.assertEqual(request.status, "Pending")
        self.assertIsNone(request.decided_at)
        self.assertIsNone(request.decided_by_id)
        self.assertEqual(membership.left_at, self.now)
        self.assertEqual(count_active_members(self.party), 1)
        self.assertEqual(JoinRequest.objects.count(), 1)

    def test_approved_without_withdrawn_membership_is_not_reopened(self):
        JoinRequest.objects.create(
            party=self.party,
            user=self.applicant,
            status="Approved",
            decided_at=self.now,
            decided_by=self.host,
        )
        self.assert_error(self.post_request(), 409, "REQUEST_DECIDED")
        self.assertEqual(JoinRequest.objects.get().status, "Approved")

    def test_rejected_request_cannot_reopen_after_party_cancellation(self):
        JoinRequest.objects.create(
            party=self.party,
            user=self.applicant,
            status="Rejected",
            decided_at=self.now,
            decided_by=self.host,
        )
        before = JoinRequest.objects.values().get()
        self.party.cancelled_at = self.now
        self.party.save(update_fields=["cancelled_at"])
        self.assert_error(self.post_request(), 409, "PARTY_CANCELLED")
        self.assertEqual(JoinRequest.objects.values().get(), before)

    def test_closed_party_states_reject_new_requests(self):
        memberships = self.membership_snapshot()
        starts_at, ends_at = self.party.starts_at, self.party.ends_at
        for fields, code in (
            ({"cancelled_at": self.now}, "PARTY_CANCELLED"),
            ({"starts_at": self.now}, "PARTY_STARTED"),
            ({"starts_at": self.now - timedelta(hours=1), "ends_at": self.now}, "PARTY_STARTED"),
            ({"capacity": 1}, "PARTY_FULL"),
        ):
            with self.subTest(code=code):
                Party.objects.filter(pk=self.party.pk).update(
                    cancelled_at=None,
                    starts_at=starts_at,
                    ends_at=ends_at,
                    capacity=2,
                )
                Party.objects.filter(pk=self.party.pk).update(**fields)
                self.assert_error(self.post_request(), 409, code)
                self.assertFalse(JoinRequest.objects.exists())
                self.assert_membership_and_slots_unchanged(memberships, fields.get("capacity", 2))
        self.assertFalse(JoinRequest.objects.exists())

    def test_exact_start_boundary_rejects_request(self):
        with patch("parties.services.timezone.now", return_value=self.party.starts_at):
            self.assert_error(self.post_request(), 409, "PARTY_STARTED")
        self.assertFalse(JoinRequest.objects.exists())

    def test_host_is_rejected_even_when_host_membership_is_missing(self):
        self.party.memberships.all().delete()
        force_university_login(self.client, self.host)
        self.assert_error(self.post_request(), 409, "ALREADY_MEMBER")
        self.assertFalse(JoinRequest.objects.exists())

    def test_host_with_active_membership_is_rejected_without_writing(self):
        memberships = self.membership_snapshot()
        force_university_login(self.client, self.host)
        self.assert_error(self.post_request(), 409, "ALREADY_MEMBER")
        self.assertFalse(JoinRequest.objects.exists())
        self.assert_membership_and_slots_unchanged(memberships, 2)

    def test_active_member_is_rejected(self):
        self.party.capacity = 3
        self.party.save(update_fields=["capacity"])
        PartyMembership.objects.create(party=self.party, user=self.applicant)
        memberships = self.membership_snapshot()
        self.assert_error(self.post_request(), 409, "ALREADY_MEMBER")
        self.assertFalse(JoinRequest.objects.exists())
        self.assert_membership_and_slots_unchanged(memberships, 3)

    def test_unknown_party_returns_json_404_for_both_endpoints(self):
        self.create_url = reverse("party-join-request-create", args=[self.party.pk + 1])
        self.assert_error(self.post_request(), 404, "NOT_FOUND")
        self.assert_error(
            self.client.get(reverse("party-join-request-me", args=[self.party.pk + 1])),
            404,
            "NOT_FOUND",
        )

    def test_anonymous_and_revoked_sessions_cannot_read_or_create(self):
        memberships = self.membership_snapshot()
        self.client.logout()
        self.assert_error(self.post_request(), 401, "AUTH_REQUIRED")
        self.assert_error(self.client.get(self.mine_url), 401, "AUTH_REQUIRED")
        force_university_login(self.client, self.applicant)
        self.applicant.is_active = False
        self.applicant.save(update_fields=["is_active"])
        # ModelBackend rejects inactive users when resolving an existing session.
        self.assert_error(self.post_request(), 401, "AUTH_REQUIRED")
        self.assert_error(self.client.get(self.mine_url), 401, "AUTH_REQUIRED")
        self.assertFalse(JoinRequest.objects.exists())
        self.assertEqual(self.membership_snapshot(), memberships)

    def test_logout_endpoint_revokes_copied_session_for_both_endpoints(self):
        client = Client(enforce_csrf_checks=True)
        force_university_login(client, self.applicant)
        self.assertEqual(client.get(self.mine_url).status_code, 200)
        token = client.cookies["csrftoken"].value
        old_session = client.cookies[settings.SESSION_COOKIE_NAME].value
        response = client.post(
            reverse("accounts:logout"),
            data="{}",
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Session.objects.filter(session_key=old_session).exists())
        # Another tab/client retaining the old cookie must also lose access.
        stale_client = Client(enforce_csrf_checks=True)
        stale_client.cookies[settings.SESSION_COOKIE_NAME] = old_session
        stale_client.cookies["csrftoken"] = token
        memberships = self.membership_snapshot()
        for browser in (client, stale_client):
            with self.subTest(stale=browser is stale_client):
                self.assert_error(browser.get(self.mine_url), 401, "AUTH_REQUIRED")
                self.assert_error(
                    browser.post(
                        self.create_url,
                        data="{}",
                        content_type="application/json",
                        HTTP_X_CSRFTOKEN=token,
                    ),
                    401,
                    "AUTH_REQUIRED",
                )
        self.assertFalse(JoinRequest.objects.exists())
        self.assertEqual(self.membership_snapshot(), memberships)

    def test_expired_session_cannot_read_or_create(self):
        session_key = self.client.cookies[settings.SESSION_COOKIE_NAME].value
        Session.objects.filter(session_key=session_key).update(
            expire_date=timezone.now() - timedelta(seconds=1)
        )
        memberships = self.membership_snapshot()
        self.assert_error(self.post_request(), 401, "AUTH_REQUIRED")
        self.assert_error(self.client.get(self.mine_url), 401, "AUTH_REQUIRED")
        self.assertFalse(JoinRequest.objects.exists())
        self.assertEqual(self.membership_snapshot(), memberships)

    def test_body_cannot_create_request_for_an_existing_other_user(self):
        memberships = self.membership_snapshot()
        response = self.client.post(
            self.create_url,
            data={"user_id": self.other.pk},
            content_type="application/json",
        )
        self.assert_error(response, 400, "INVALID_INPUT")
        self.assertFalse(JoinRequest.objects.exists())
        self.assert_membership_and_slots_unchanged(memberships, 2)

    def test_invalid_body_and_client_selected_fields_are_rejected(self):
        for body, content_type in (
            ('{"user_id": 999}', "application/json"),
            ('{"host_id": 999}', "application/json"),
            ('{"status": "Approved"}', "application/json"),
            ('{"party_id": 999}', "application/json"),
            ('{"extra": true}', "application/json"),
            ("[]", "application/json"),
            ("null", "application/json"),
            ("false", "application/json"),
            ("{", "application/json"),
            (b"\xff", "application/json"),
            ("{}", "text/plain"),
        ):
            with self.subTest(body=body):
                response = self.client.post(self.create_url, data=body, content_type=content_type)
                self.assert_error(response, 400, "INVALID_INPUT")
        self.assertFalse(JoinRequest.objects.exists())

    def test_query_cannot_change_actor_and_empty_body_is_supported(self):
        response = self.client.post(
            f"{self.create_url}?user_id={self.other.pk}&host_id={self.host.pk}",
            data=b"",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(JoinRequest.objects.get().user_id, self.applicant.pk)

    def test_wrong_methods_return_json_405_without_writing(self):
        for url, method, allowed in (
            (self.create_url, "get", "POST"),
            (self.create_url, "patch", "POST"),
            (self.mine_url, "post", "GET"),
            (self.mine_url, "delete", "GET"),
        ):
            with self.subTest(method=method, url=url):
                response = getattr(self.client, method)(url)
                self.assert_error(response, 405, "METHOD_NOT_ALLOWED")
                self.assertEqual(response["Allow"], allowed)
        self.assertFalse(JoinRequest.objects.exists())

    def test_csrf_cookie_from_get_enables_post_and_bad_tokens_or_origins_are_rejected(self):
        client = Client(enforce_csrf_checks=True)
        force_university_login(client, self.applicant)
        self.assert_error(
            client.post(self.create_url, data="{}", content_type="application/json"),
            403,
            "CSRF_FAILED",
        )
        response = client.get(self.mine_url)
        self.assertEqual(response.json(), {"data": None})
        token = client.cookies["csrftoken"].value
        self.assert_error(
            client.post(
                self.create_url,
                data="{}",
                content_type="application/json",
                HTTP_X_CSRFTOKEN="invalid",
            ),
            403,
            "CSRF_FAILED",
        )
        self.assert_error(
            client.post(
                self.create_url,
                data="{}",
                content_type="application/json",
                HTTP_X_CSRFTOKEN=token,
                HTTP_ORIGIN="https://untrusted.invalid",
            ),
            403,
            "CSRF_FAILED",
        )
        self.assertFalse(JoinRequest.objects.exists())
        response = client.post(
            self.create_url, data="{}", content_type="application/json", HTTP_X_CSRFTOKEN=token
        )
        self.assertEqual(response.status_code, 201)

    def test_non_api_csrf_failures_keep_django_html_response(self):
        response = Client(enforce_csrf_checks=True).post("/admin/login/", data={})
        self.assertEqual(response.status_code, 403)
        self.assertIn("text/html", response["Content-Type"])


@skipUnlessDBFeature("has_select_for_update")
class JoinRequestConcurrencyTests(JoinRequestFixture, TransactionTestCase):
    def post_on_connection(self, user_id, barrier=None, pid_queue=None):
        close_old_connections()
        try:
            client = Client()
            force_university_login(client, get_user_model().objects.get(pk=user_id))
            with connection.cursor() as cursor:
                cursor.execute("SET lock_timeout = '5s'")
                cursor.execute("SELECT pg_backend_pid()")
                pid = cursor.fetchone()[0]
            if barrier is not None:
                barrier.wait(timeout=10)
            if pid_queue is not None:
                pid_queue.put(pid)
            response = client.post(self.create_url, data="{}", content_type="application/json")
            return response.status_code, response.json()
        finally:
            connections.close_all()

    def simultaneous_posts(self, user_ids):
        barrier = Barrier(len(user_ids))
        with ThreadPoolExecutor(max_workers=len(user_ids)) as executor:
            futures = [
                executor.submit(self.post_on_connection, user_id, barrier) for user_id in user_ids
            ]
            return [future.result(timeout=15) for future in futures]

    def wait_until_blocked(self, pid):
        # Observe a real PostgreSQL row-lock wait instead of relying on a sleep/race.
        deadline = monotonic() + 4
        while monotonic() < deadline:
            with connection.cursor() as cursor:
                cursor.execute("SELECT cardinality(pg_blocking_pids(%s)) > 0", [pid])
                if cursor.fetchone()[0]:
                    return
            Event().wait(0.01)
        self.fail("Worker did not wait for the Party lock")

    def test_same_user_concurrent_posts_create_exactly_one_pending(self):
        memberships = self.membership_snapshot()
        results = self.simultaneous_posts([self.applicant.pk, self.applicant.pk])
        self.assertEqual(sorted(status for status, _ in results), [201, 409])
        self.assertEqual(
            next(body for status, body in results if status == 409)["error"]["code"],
            "REQUEST_EXISTS",
        )
        self.assertEqual(JoinRequest.objects.count(), 1)
        self.assertEqual(JoinRequest.objects.get().status, "Pending")
        request = JoinRequest.objects.get()
        self.assertEqual((request.party_id, request.user_id), (self.party.pk, self.applicant.pk))
        self.assertIsNone(request.decided_at)
        self.assertIsNone(request.decided_by_id)
        self.assertEqual(
            next(body for status, body in results if status == 201)["data"]["id"], request.pk
        )
        self.assert_membership_and_slots_unchanged(memberships, 2)

    def test_different_users_can_both_request_the_last_slot(self):
        memberships = self.membership_snapshot()
        results = self.simultaneous_posts([self.applicant.pk, self.other.pk])
        self.assertEqual([status for status, _ in results], [201, 201])
        self.assertEqual(JoinRequest.objects.filter(status="Pending").count(), 2)
        self.assertEqual(
            set(JoinRequest.objects.values_list("party_id", "user_id")),
            {(self.party.pk, self.applicant.pk), (self.party.pk, self.other.pk)},
        )
        self.assertEqual(
            {body["data"]["id"] for _, body in results},
            set(JoinRequest.objects.values_list("pk", flat=True)),
        )
        for request in JoinRequest.objects.all():
            self.assertIsNone(request.decided_at)
            self.assertIsNone(request.decided_by_id)
            client = Client()
            force_university_login(client, request.user)
            response = client.get(self.mine_url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["data"]["id"], request.pk)
        self.assert_membership_and_slots_unchanged(memberships, 2)

    def test_concurrent_reapplications_reuse_one_row_only_once(self):
        request = JoinRequest.objects.create(
            party=self.party,
            user=self.applicant,
            status="Rejected",
            decided_at=self.now,
            decided_by=self.host,
        )
        results = self.simultaneous_posts([self.applicant.pk, self.applicant.pk])
        self.assertEqual(sorted(status for status, _ in results), [201, 409])
        self.assertEqual(JoinRequest.objects.get().pk, request.pk)
        request.refresh_from_db()
        self.assertEqual(request.status, "Pending")
        self.assertIsNone(request.decided_at)
        self.assertIsNone(request.decided_by_id)

    def test_cancellation_committed_first_blocks_pending_creation(self):
        pids = Queue()
        with ThreadPoolExecutor(max_workers=1) as executor:
            with transaction.atomic():
                party = Party.objects.select_for_update().get(pk=self.party.pk)
                future = executor.submit(self.post_on_connection, self.applicant.pk, None, pids)
                self.wait_until_blocked(pids.get(timeout=5))
                party.cancelled_at = timezone.now()
                party.save(update_fields=["cancelled_at"])
            status, body = future.result(timeout=10)
        self.assertEqual(status, 409)
        self.assertEqual(body["error"]["code"], "PARTY_CANCELLED")
        self.assertFalse(JoinRequest.objects.exists())

    def test_changed_start_time_is_rechecked_after_waiting_for_party_lock(self):
        pids = Queue()
        with ThreadPoolExecutor(max_workers=1) as executor:
            with transaction.atomic():
                party = Party.objects.select_for_update().get(pk=self.party.pk)
                future = executor.submit(self.post_on_connection, self.applicant.pk, None, pids)
                self.wait_until_blocked(pids.get(timeout=5))
                party.starts_at = timezone.now() - timedelta(seconds=1)
                party.save(update_fields=["starts_at"])
            status, body = future.result(timeout=10)
        self.assertEqual((status, body["error"]["code"]), (409, "PARTY_STARTED"))
        self.assertFalse(JoinRequest.objects.exists())

    def test_request_committed_before_cancellation_keeps_pending_history(self):
        pids = Queue()

        def cancel_on_connection():
            close_old_connections()
            try:
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute("SET LOCAL lock_timeout = '5s'")
                        cursor.execute("SELECT pg_backend_pid()")
                        pids.put(cursor.fetchone()[0])
                    party = Party.objects.select_for_update().get(pk=self.party.pk)
                    party.cancelled_at = timezone.now()
                    party.save(update_fields=["cancelled_at"])
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=1) as executor:
            with transaction.atomic():
                request = submit_join_request(party_id=self.party.pk, user=self.applicant)
                future = executor.submit(cancel_on_connection)
                self.wait_until_blocked(pids.get(timeout=5))
            future.result(timeout=10)
        request.refresh_from_db()
        self.party.refresh_from_db()
        self.assertEqual(request.status, "Pending")
        self.assertIsNotNone(self.party.cancelled_at)
        self.assertEqual(count_active_members(self.party), 1)


class JoinRequestDecisionTests(JoinRequestFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.request = JoinRequest.objects.create(party=self.party, user=self.applicant)
        force_university_login(self.client, self.host)

    def test_host_can_list_and_approve_pending_request(self):
        listed = self.client.get(reverse("party-join-request-list", args=[self.party.pk]))
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()["data"][0]["id"], self.request.pk)
        response = self.client.post(
            reverse("party-join-request-decision", args=[self.party.pk, self.request.pk]),
            data='{"status":"Approved"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, JoinRequest.Status.APPROVED)
        self.assertEqual(self.request.decided_by, self.host)
        self.assertTrue(
            PartyMembership.objects.filter(
                party=self.party, user=self.applicant, left_at__isnull=True
            ).exists()
        )

    def test_only_host_can_decide_and_full_party_stays_pending(self):
        force_university_login(self.client, self.other)
        url = reverse("party-join-request-decision", args=[self.party.pk, self.request.pk])
        self.assertEqual(
            self.client.post(
                url, data='{"status":"Rejected"}', content_type="application/json"
            ).status_code,
            403,
        )
        force_university_login(self.client, self.host)
        self.party.capacity = 1
        self.party.save(update_fields=["capacity"])
        response = self.client.post(
            url, data='{"status":"Approved"}', content_type="application/json"
        )
        self.assertEqual(response.status_code, 409)
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, JoinRequest.Status.PENDING)
