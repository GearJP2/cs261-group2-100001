"""Task52: reject through the real API/DB, preserving membership and reapplication."""

from datetime import timedelta
from unittest.mock import patch

from accounts.test_support import force_university_login
from django.conf import settings
from django.contrib.sessions.models import Session
from django.db import IntegrityError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import JoinRequest, Party, PartyMembership
from .test_join_requests import JoinRequestFixture


class RejectRequestApiTests(JoinRequestFixture, TestCase):
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

    def post(self, url=None, data=None):
        return self.client.post(
            url or self.url,
            data={"status": "Rejected"} if data is None else data,
            content_type="application/json",
            HTTP_X_CSRFTOKEN=self.token,
        )

    def snapshot(self):
        return {
            model.__name__: list(model.objects.order_by("pk").values())
            for model in (Party, JoinRequest, PartyMembership)
        }

    def assert_error(self, response, status, code):
        self.assertEqual(response.status_code, status)
        self.assertEqual(set(response.json()), {"error"})
        self.assertEqual(response.json()["error"]["code"], code)
        self.assertIn("no-store", response["Cache-Control"])

    def assert_denied(self, status, code, url=None):
        before = self.snapshot()
        self.assert_error(self.post(url), status, code)
        self.assertEqual(self.snapshot(), before)

    def detail(self):
        return self.client.get(reverse("party-detail", args=[self.party.pk])).json()["data"]

    def test_reject_records_decision_and_refreshes_reads_without_changing_members(self):
        other = JoinRequest.objects.create(party=self.party, user=self.other)
        before = self.snapshot()
        detail = self.detail()
        members_url = reverse("party-members", args=[self.party.pk])
        members = self.client.get(members_url).json()
        decided_at = timezone.now()
        response = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"data": {"id": self.pending.pk, "status": "Rejected"}})
        self.assertIn("no-store", response["Cache-Control"])
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.decided_by_id, self.host.pk)
        self.assertGreaterEqual(self.pending.decided_at, decided_at)
        self.assertLessEqual(self.pending.decided_at, timezone.now())
        self.assertEqual(self.pending.created_at, before["JoinRequest"][0]["created_at"])
        after = self.snapshot()
        self.assertEqual(after["Party"], before["Party"])
        self.assertEqual(after["PartyMembership"], before["PartyMembership"])
        self.assertEqual(after["JoinRequest"][1], before["JoinRequest"][1])
        self.assertEqual(self.detail(), detail)
        self.assertEqual(self.client.get(members_url).json(), members)
        pending = self.client.get(reverse("party-join-request-list", args=[self.party.pk]))
        self.assertEqual([row["id"] for row in pending.json()["data"]], [other.pk])
        self.login_as(self.applicant)
        own = self.client.get(self.mine_url).json()["data"]
        self.assertEqual((own["id"], own["status"]), (self.pending.pk, "Rejected"))

    def test_full_party_can_reject_without_freeing_a_slot(self):
        PartyMembership.objects.create(party=self.party, user=self.other)
        before = self.snapshot()
        detail = self.detail()
        self.assertEqual(
            (detail["member_count"], detail["remaining_slots"], detail["state"]), (2, 0, "Full")
        )
        self.assertEqual(self.post().status_code, 200)
        self.assertEqual(self.detail(), detail)
        self.assertEqual(self.snapshot()["PartyMembership"], before["PartyMembership"])
        self.login_as(self.applicant)
        rejected = self.snapshot()
        self.assert_error(self.post(self.create_url, {}), 409, "PARTY_FULL")
        self.assertEqual(self.snapshot(), rejected)

    def test_reject_preserves_withdrawn_membership_history(self):
        PartyMembership.objects.create(party=self.party, user=self.applicant, left_at=self.now)
        memberships = self.membership_snapshot()
        self.assertEqual(self.post().status_code, 200)
        self.assertEqual(self.membership_snapshot(), memberships)
        self.login_as(self.applicant)
        self.assertEqual(self.post(self.create_url, {}).status_code, 201)
        self.assertEqual(self.membership_snapshot(), memberships)

    def test_rejected_applicant_can_reapply_and_then_be_approved(self):
        self.assertEqual(self.post().status_code, 200)
        self.pending.refresh_from_db()
        rejected_at = self.pending.decided_at
        memberships = self.membership_snapshot()
        self.login_as(self.applicant)
        response = self.post(self.create_url, {})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["data"]["id"], self.pending.pk)
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, "Pending")
        self.assertGreaterEqual(self.pending.created_at, rejected_at)
        self.assertIsNone(self.pending.decided_at)
        self.assertIsNone(self.pending.decided_by_id)
        self.assertEqual(self.membership_snapshot(), memberships)
        self.assertEqual(JoinRequest.objects.count(), 1)
        before = self.snapshot()
        self.assert_error(self.post(self.create_url, {}), 409, "REQUEST_EXISTS")
        self.assertEqual(self.snapshot(), before)
        self.login_as(self.host)
        pending = self.client.get(reverse("party-join-request-list", args=[self.party.pk]))
        self.assertEqual([row["id"] for row in pending.json()["data"]], [self.pending.pk])
        self.assertEqual(self.post(data={"status": "Approved"}).status_code, 200)
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, "Approved")
        self.assertTrue(self.party.memberships.filter(user=self.applicant, left_at=None).exists())
        self.assertEqual(self.detail()["remaining_slots"], 0)

    def test_non_host_roles_and_anonymous_cannot_reject(self):
        for user, status, code in (
            (self.applicant, 403, "FORBIDDEN"),
            (self.other, 403, "FORBIDDEN"),
            (None, 401, "AUTH_REQUIRED"),
        ):
            with self.subTest(user=user):
                self.login_as(user)
                self.assert_denied(status, code)
        self.other.is_staff = self.other.is_superuser = True
        self.other.save(update_fields=["is_staff", "is_superuser"])
        PartyMembership.objects.create(party=self.party, user=self.other)
        self.login_as(self.other)
        self.assert_denied(403, "FORBIDDEN")

    def test_unverified_and_expired_sessions_cannot_reject(self):
        session = self.client.session
        session.pop("university_identity_id")
        session.save()
        self.assert_denied(403, "FORBIDDEN")
        self.login_as(self.host)
        Session.objects.filter(session_key=self.client.session.session_key).update(
            expire_date=timezone.now() - timedelta(seconds=1)
        )
        self.assert_denied(401, "AUTH_REQUIRED")

    def test_logout_revokes_old_cookie_for_reject(self):
        old_cookie = self.client.cookies[settings.SESSION_COOKIE_NAME].value
        token = self.token
        csrf_cookie = self.client.cookies[settings.CSRF_COOKIE_NAME].value
        self.assertEqual(self.post(reverse("accounts:logout"), {}).status_code, 200)
        self.assertFalse(Session.objects.filter(session_key=old_cookie).exists())
        self.client = Client(enforce_csrf_checks=True)
        self.client.cookies[settings.SESSION_COOKIE_NAME] = old_cookie
        self.client.cookies[settings.CSRF_COOKIE_NAME] = csrf_cookie
        self.token = token
        self.assert_denied(401, "AUTH_REQUIRED")

    def test_missing_or_wrong_party_request_cannot_be_rejected(self):
        another_party = Party.objects.create(
            host=self.host,
            sport=self.party.sport,
            venue=self.party.venue,
            title="Other",
            starts_at=self.party.starts_at,
            ends_at=self.party.ends_at,
            capacity=2,
        )
        for party_id, request_id in (
            (0, self.pending.pk),
            (self.party.pk, 0),
            (another_party.pk, self.pending.pk),
        ):
            with self.subTest(party_id=party_id, request_id=request_id):
                self.assert_denied(
                    404,
                    "NOT_FOUND",
                    reverse("party-join-request-decision", args=[party_id, request_id]),
                )

    def test_repeated_reject_and_approve_preserve_rejection(self):
        self.assertEqual(self.post().status_code, 200)
        before = self.snapshot()
        for status in ("Rejected", "Approved"):
            with self.subTest(status=status):
                self.assert_error(self.post(data={"status": status}), 409, "REQUEST_DECIDED")
                self.assertEqual(self.snapshot(), before)

    def test_reject_cannot_overturn_approval_or_remove_member(self):
        self.assertEqual(self.post(data={"status": "Approved"}).status_code, 200)
        self.assert_denied(409, "REQUEST_DECIDED")
        self.assertTrue(self.party.memberships.filter(user=self.applicant, left_at=None).exists())

    def test_cancelled_started_completed_and_exact_start_deny_reject(self):
        defaults = {
            "cancelled_at": None,
            "starts_at": self.party.starts_at,
            "ends_at": self.party.ends_at,
        }
        for changes, code in (
            ({"cancelled_at": self.now}, "PARTY_CANCELLED"),
            ({"starts_at": self.now - timedelta(seconds=1)}, "PARTY_STARTED"),
            (
                {
                    "starts_at": self.now - timedelta(hours=2),
                    "ends_at": self.now - timedelta(hours=1),
                },
                "PARTY_STARTED",
            ),
        ):
            with self.subTest(code=code, changes=changes):
                Party.objects.filter(pk=self.party.pk).update(**(defaults | changes))
                self.assert_denied(409, code)
        Party.objects.filter(pk=self.party.pk).update(**defaults)
        with patch("parties.services.timezone.now", return_value=self.party.starts_at):
            self.assert_denied(409, "PARTY_STARTED")

    def test_extra_body_fields_cannot_override_actor_or_target(self):
        for field in ("user_id", "host_id", "party_id", "request_id", "decided_by"):
            with self.subTest(field=field):
                before = self.snapshot()
                self.assert_error(
                    self.post(data={"status": "Rejected", field: self.other.pk}),
                    400,
                    "INVALID_INPUT",
                )
                self.assertEqual(self.snapshot(), before)
        url = f"{self.url}?host_id={self.other.pk}&user_id={self.other.pk}&request_id=0&status=Approved"
        self.assertEqual(self.post(url).status_code, 200)
        self.pending.refresh_from_db()
        self.assertEqual(
            (self.pending.status, self.pending.decided_by_id), ("Rejected", self.host.pk)
        )
        self.assertEqual(self.party.memberships.count(), 1)

    def test_reject_requires_csrf_and_post(self):
        before = self.snapshot()
        for headers in (
            {},
            {"HTTP_X_CSRFTOKEN": "invalid"},
            {"HTTP_X_CSRFTOKEN": self.token, "HTTP_ORIGIN": "https://untrusted.invalid"},
        ):
            with self.subTest(headers=headers):
                response = self.client.post(
                    self.url,
                    data={"status": "Rejected"},
                    content_type="application/json",
                    **headers,
                )
                self.assert_error(response, 403, "CSRF_FAILED")
                self.assertEqual(self.snapshot(), before)
        for method in ("GET", "PUT", "PATCH", "DELETE", "OPTIONS"):
            with self.subTest(method=method):
                response = self.client.generic(method, self.url, HTTP_X_CSRFTOKEN=self.token)
                self.assert_error(response, 405, "METHOD_NOT_ALLOWED")
                self.assertEqual(response["Allow"], "POST")
                self.assertEqual(self.snapshot(), before)

    def test_failure_after_decision_write_rolls_back_all_domain_data(self):
        original_save = JoinRequest.save

        def save_then_violate_constraint(instance, *args, **kwargs):
            original_save(instance, *args, **kwargs)
            # The decision really reached SQL before the second write fails.
            self.assertEqual(JoinRequest.objects.get(pk=instance.pk).status, "Rejected")
            JoinRequest.objects.filter(pk=instance.pk).update(decided_at=None)

        before = self.snapshot()
        with patch.object(
            JoinRequest, "save", autospec=True, side_effect=save_then_violate_constraint
        ):
            with self.assertRaises(IntegrityError):
                self.post()
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.post().status_code, 200)
