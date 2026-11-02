"""US10-B-02 approval contract; PostgreSQL fixtures, no live TU provider."""

from datetime import timedelta
from unittest.mock import patch

from accounts.test_support import force_university_login
from django.contrib.sessions.models import Session
from django.db import DatabaseError, IntegrityError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import JoinRequest, Party, PartyMembership
from .services import decide_join_request
from .test_join_requests import JoinRequestFixture


class ApproveRequestApiTests(JoinRequestFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.pending = JoinRequest.objects.create(party=self.party, user=self.applicant)
        self.url = reverse("party-join-request-decision", args=[self.party.pk, self.pending.pk])
        self.client = Client(enforce_csrf_checks=True)
        self.login_as(self.host)

    def login_as(self, user):
        self.client.logout()
        if user is not None:
            force_university_login(self.client, user)
        self.token = self.client.get(reverse("accounts:csrf")).json()["data"]["csrf_token"]

    def snapshot(self):
        return {
            model.__name__: list(model.objects.order_by("pk").values())
            for model in (Party, JoinRequest, PartyMembership)
        }

    def approve(self, url=None):
        return self.client.post(
            url or self.url,
            data={"status": "Approved"},
            content_type="application/json",
            HTTP_X_CSRFTOKEN=self.token,
        )

    def assert_error(self, response, status, code):
        self.assertEqual(response.status_code, status)
        payload = response.json()
        self.assertEqual(set(payload), {"error"})
        self.assertEqual(payload["error"]["code"], code)
        self.assertIn("no-store", response["Cache-Control"])

    def assert_denied_without_writes(self, status, code, url=None):
        before = self.snapshot()
        self.assert_error(self.approve(url), status, code)
        self.assertEqual(self.snapshot(), before)

    def test_approval_adds_one_member_and_refreshes_pending_own_request_and_detail(self):
        before = timezone.now()
        response = self.approve()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"data": {"id": self.pending.pk, "status": "Approved"}})
        self.assertIn("no-store", response["Cache-Control"])
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.decided_by_id, self.host.pk)
        self.assertGreaterEqual(self.pending.decided_at, before)
        self.assertLessEqual(self.pending.decided_at, timezone.now())
        self.assertIsNone(
            PartyMembership.objects.get(party=self.party, user=self.applicant).left_at
        )
        detail = self.client.get(reverse("party-detail", args=[self.party.pk])).json()["data"]
        self.assertEqual(
            (detail["member_count"], detail["remaining_slots"], detail["state"]), (2, 0, "Full")
        )
        self.assertEqual(detail["capacity"], 2)
        listed = self.client.get(reverse("party-join-request-list", args=[self.party.pk]))
        self.assertEqual(listed.json(), {"data": []})
        self.login_as(self.applicant)
        own = self.client.get(self.mine_url).json()["data"]
        self.assertEqual((own["id"], own["status"]), (self.pending.pk, "Approved"))

    def test_reapproval_reuses_withdrawn_membership_and_preserves_join_history(self):
        membership = PartyMembership.objects.create(
            party=self.party, user=self.applicant, left_at=self.now - timedelta(hours=1)
        )
        joined_at = membership.joined_at
        self.assertEqual(self.approve().status_code, 200)
        membership.refresh_from_db()
        self.assertIsNone(membership.left_at)
        self.assertEqual(membership.joined_at, joined_at)
        self.assertEqual(self.party.memberships.count(), 2)

    def test_non_host_and_anonymous_cannot_approve(self):
        for user, status, code in (
            (self.applicant, 403, "FORBIDDEN"),
            (self.other, 403, "FORBIDDEN"),
            (None, 401, "AUTH_REQUIRED"),
        ):
            with self.subTest(user=user):
                self.login_as(user)
                self.assert_denied_without_writes(status, code)

    def test_missing_university_evidence_or_expired_session_cannot_approve(self):
        session = self.client.session
        session.pop("university_identity_id")
        session.save()
        self.assert_denied_without_writes(403, "FORBIDDEN")
        self.login_as(self.host)
        Session.objects.filter(session_key=self.client.session.session_key).update(
            expire_date=timezone.now() - timedelta(seconds=1)
        )
        self.assert_denied_without_writes(401, "AUTH_REQUIRED")

    def test_request_must_exist_and_belong_to_url_party(self):
        other_party = Party.objects.create(
            host=self.host,
            sport=self.party.sport,
            venue=self.party.venue,
            title="Other party",
            starts_at=self.party.starts_at,
            ends_at=self.party.ends_at,
            capacity=2,
        )
        for party_id, request_id in (
            (0, self.pending.pk),
            (self.party.pk, 0),
            (other_party.pk, self.pending.pk),
        ):
            with self.subTest(party_id=party_id, request_id=request_id):
                url = reverse("party-join-request-decision", args=[party_id, request_id])
                self.assert_denied_without_writes(404, "NOT_FOUND", url)

    def test_repeated_decision_preserves_first_result_and_membership(self):
        self.assertEqual(self.approve().status_code, 200)
        self.assert_denied_without_writes(409, "REQUEST_DECIDED")

    def test_rejected_request_cannot_be_approved_without_new_application(self):
        self.pending.status = JoinRequest.Status.REJECTED
        self.pending.decided_at = self.now
        self.pending.decided_by = self.host
        self.pending.save()
        self.assert_denied_without_writes(409, "REQUEST_DECIDED")

    def test_full_started_completed_and_cancelled_party_reject_approval(self):
        defaults = {
            "capacity": 2,
            "starts_at": self.party.starts_at,
            "ends_at": self.party.ends_at,
            "cancelled_at": None,
        }
        cases = (
            ({"capacity": 1}, "PARTY_FULL"),
            ({"starts_at": self.now - timedelta(seconds=1)}, "PARTY_STARTED"),
            (
                {
                    "starts_at": self.now - timedelta(hours=2),
                    "ends_at": self.now - timedelta(hours=1),
                },
                "PARTY_STARTED",
            ),
            ({"cancelled_at": self.now}, "PARTY_CANCELLED"),
        )
        for changes, code in cases:
            with self.subTest(changes=changes):
                Party.objects.filter(pk=self.party.pk).update(**(defaults | changes))
                self.assert_denied_without_writes(409, code)

    def test_exact_start_boundary_rejects_approval(self):
        with patch("parties.services.timezone.now", return_value=self.party.starts_at):
            self.assert_denied_without_writes(409, "PARTY_STARTED")

    def test_existing_active_member_cannot_be_approved_again(self):
        # A legacy/inconsistent Pending must not be accepted as a new membership.
        self.party.capacity = 3
        self.party.save(update_fields=["capacity"])
        PartyMembership.objects.create(party=self.party, user=self.applicant)
        self.assert_denied_without_writes(409, "ALREADY_MEMBER")

    def test_host_cannot_be_approved_even_without_host_membership(self):
        PartyMembership.objects.filter(party=self.party, user=self.host).delete()
        self.pending.user = self.host
        self.pending.save(update_fields=["user"])
        self.assert_denied_without_writes(409, "ALREADY_MEMBER")

    def test_invalid_payloads_are_400_not_server_errors(self):
        bodies = (
            "{",
            "[]",
            "null",
            "true",
            "{}",
            '{"status":"Pending"}',
            '{"status":[]}',
            '{"status":{}}',
            '{"status":null}',
            '{"status":true}',
            '{"status":"Approved","user_id":1}',
            '{"status":"Approved","host_id":1}',
            '{"status":"Approved","party_id":1}',
            '{"status":"Approved","decided_by":1}',
        )
        for body in bodies:
            with self.subTest(body=body):
                before = self.snapshot()
                response = self.client.post(
                    self.url,
                    data=body,
                    content_type="application/json",
                    HTTP_X_CSRFTOKEN=self.token,
                )
                self.assert_error(response, 400, "INVALID_INPUT")
                self.assertEqual(self.snapshot(), before)

    def test_wrong_content_type_and_methods_are_rejected(self):
        before = self.snapshot()
        response = self.client.post(
            self.url, data={"status": "Approved"}, HTTP_X_CSRFTOKEN=self.token
        )
        self.assert_error(response, 400, "INVALID_INPUT")
        for method in ("GET", "PUT", "PATCH", "DELETE", "OPTIONS"):
            with self.subTest(method=method):
                response = self.client.generic(method, self.url, HTTP_X_CSRFTOKEN=self.token)
                self.assert_error(response, 405, "METHOD_NOT_ALLOWED")
                self.assertEqual(response["Allow"], "POST")
                self.assertEqual(self.snapshot(), before)

    def test_csrf_missing_invalid_and_wrong_origin_do_not_write(self):
        before = self.snapshot()
        for headers in (
            {},
            {"HTTP_X_CSRFTOKEN": "invalid"},
            {"HTTP_X_CSRFTOKEN": self.token, "HTTP_ORIGIN": "https://untrusted.invalid"},
        ):
            with self.subTest(headers=headers):
                response = self.client.post(
                    self.url,
                    data={"status": "Approved"},
                    content_type="application/json",
                    **headers,
                )
                self.assert_error(response, 403, "CSRF_FAILED")
                self.assertEqual(self.snapshot(), before)

    def test_query_cannot_change_actor_target_or_decision(self):
        response = self.approve(
            f"{self.url}?user_id={self.other.pk}&host_id={self.other.pk}&request_id=0&status=Rejected"
        )
        self.assertEqual(response.status_code, 200)
        self.pending.refresh_from_db()
        self.assertEqual(
            (self.pending.status, self.pending.decided_by_id), ("Approved", self.host.pk)
        )
        self.assertTrue(self.party.memberships.filter(user=self.applicant).exists())
        self.assertFalse(self.party.memberships.filter(user=self.other).exists())

    def test_membership_write_failure_leaves_request_pending(self):
        before = self.snapshot()
        with patch(
            "parties.services.PartyMembership.objects.create",
            side_effect=DatabaseError("injected membership failure"),
        ):
            with self.assertRaises(DatabaseError):
                decide_join_request(
                    party_id=self.party.pk,
                    request_id=self.pending.pk,
                    user=self.host,
                    approved=True,
                )
        self.assertEqual(self.snapshot(), before)

    def test_decision_constraint_failure_rolls_back_new_or_reactivated_membership(self):
        original_save = JoinRequest.save

        def invalid_decision(instance, *args, **kwargs):
            # Trigger a real DB constraint error after the membership write.
            instance.decided_at = None
            return original_save(instance, *args, **kwargs)

        for withdrawn in (False, True):
            with self.subTest(withdrawn=withdrawn):
                if withdrawn:
                    PartyMembership.objects.create(
                        party=self.party, user=self.applicant, left_at=self.now
                    )
                before = self.snapshot()
                with patch.object(JoinRequest, "save", autospec=True, side_effect=invalid_decision):
                    with self.assertRaises(IntegrityError):
                        self.approve()
                self.assertEqual(self.snapshot(), before)
