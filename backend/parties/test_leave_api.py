"""Task70 HTTP contract tests using local verified university session fixtures."""

from unittest.mock import patch

from accounts.test_support import force_university_login
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import PartyMembership
from .test_join_requests import JoinRequestFixture


class LeavePartyAPITests(JoinRequestFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.member = PartyMembership.objects.create(party=self.party, user=self.applicant)
        self.url = reverse("party-leave", args=[self.party.pk])
        self.client = Client(enforce_csrf_checks=True)
        force_university_login(self.client, self.applicant)
        self.token = self.client.get(reverse("accounts:csrf")).json()["data"]["csrf_token"]

    def send(self, body="{}", *, url=None, method="post", **kwargs):
        return getattr(self.client, method)(
            url or self.url,
            data=body,
            content_type=kwargs.pop("content_type", "application/json"),
            HTTP_X_CSRFTOKEN=self.token,
            **kwargs,
        )

    def assert_error(self, response, status, code):
        self.assertEqual(response.status_code, status)
        self.assertEqual(response.json()["error"]["code"], code)
        self.member.refresh_from_db()
        self.assertIsNone(self.member.left_at)
        self.assertIn("no-store", response["Cache-Control"])

    def test_success_retry_and_detail_members_permissions(self):
        before = self.membership_snapshot()
        with patch("parties.services.timezone.now", return_value=self.now):
            response = self.send()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "data": {
                    "party_id": self.party.pk,
                    "is_member": False,
                    "left_at": timezone.localtime(self.now).isoformat(),
                }
            },
        )
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(self.send().json(), response.json())
        after = self.membership_snapshot()
        self.assertEqual(len(after), len(before))
        for old, new in zip(before, after, strict=True):
            self.assertEqual(
                {k: v for k, v in old.items() if k != "left_at"},
                {k: v for k, v in new.items() if k != "left_at"},
            )
        detail = self.client.get(reverse("party-detail", args=[self.party.pk])).json()["data"]
        self.assertEqual(
            (
                detail["is_member"],
                detail["member_count"],
                detail["remaining_slots"],
                detail["state"],
            ),
            (False, 1, 1, "Open"),
        )
        self.assertEqual(
            self.client.get(reverse("party-members", args=[self.party.pk])).status_code, 403
        )

    def test_empty_body_is_accepted(self):
        self.assertEqual(self.send("").status_code, 200)

    def test_invalid_bodies_and_client_selected_actor_never_mutate(self):
        for body, content_type in [
            ("{", "application/json"),
            ("[]", "application/json"),
            ("null", "application/json"),
            ("true", "application/json"),
            ('{"user_id":1}', "application/json"),
            ('{"membership_id":1}', "application/json"),
            ('{"left_at":null}', "application/json"),
            ("{}", "text/plain"),
            (b"\xff", "application/json"),
        ]:
            with self.subTest(body=body):
                self.assert_error(self.send(body, content_type=content_type), 400, "INVALID_INPUT")

    def test_host_nonmember_missing_and_closed_party_errors(self):
        for user, code in [(self.host, "HOST_CANNOT_LEAVE"), (self.other, "NOT_MEMBER")]:
            force_university_login(self.client, user)
            self.assert_error(self.send(), 403, code)
        force_university_login(self.client, self.applicant)
        self.assert_error(
            self.send(url=reverse("party-leave", args=[self.party.pk + 999])), 404, "NOT_FOUND"
        )
        with patch("parties.services.timezone.now", return_value=self.party.starts_at):
            self.assert_error(self.send(), 409, "PARTY_STARTED")
        self.party.cancelled_at = self.now
        self.party.save(update_fields=["cancelled_at"])
        self.assert_error(self.send(), 409, "PARTY_CANCELLED")

    def test_anonymous_and_unverified_session_are_rejected(self):
        self.client.logout()
        self.token = self.client.get(reverse("accounts:csrf")).json()["data"]["csrf_token"]
        self.assert_error(self.send(), 401, "AUTH_REQUIRED")
        self.client.force_login(self.applicant)
        self.token = self.client.get(reverse("accounts:csrf")).json()["data"]["csrf_token"]
        self.assert_error(self.send(), 403, "FORBIDDEN")

    def test_csrf_missing_invalid_and_untrusted_origin(self):
        for headers in [
            {},
            {"HTTP_X_CSRFTOKEN": "bad"},
            {"HTTP_X_CSRFTOKEN": self.token, "HTTP_ORIGIN": "https://untrusted.invalid"},
        ]:
            with self.subTest(headers=headers):
                response = self.client.post(
                    self.url, data="{}", content_type="application/json", **headers
                )
                self.assert_error(response, 403, "CSRF_FAILED")

    def test_other_methods_return_post_allow(self):
        for method in ["get", "head", "options", "put", "patch", "delete"]:
            with self.subTest(method=method):
                response = self.send(body={} if method in {"get", "head"} else "{}", method=method)
                self.assertEqual(response.status_code, 405)
                self.assertEqual(response["Allow"], "POST")
                if method != "head":
                    self.assertEqual(response.json()["error"]["code"], "METHOD_NOT_ALLOWED")
        self.member.refresh_from_db()
        self.assertIsNone(self.member.left_at)
