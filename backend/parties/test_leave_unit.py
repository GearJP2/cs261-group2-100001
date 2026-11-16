"""Task74 unit tests: stub identity/ORM/clock; no HTTP server or database.

Service tests unwrap atomic because transaction behavior is covered separately
by test_leave/test_leave_database on PostgreSQL. SimpleTestCase forbids DB I/O.
"""

import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import RequestFactory, SimpleTestCase

from .services import PartyError, leave_party
from .views import leave_party_api


class LeaveHandlerUnitTests(SimpleTestCase):
    def setUp(self):
        self.actor = SimpleNamespace(pk=20, is_authenticated=True, is_active=True)
        self.instant = datetime(2030, 11, 20, 9, tzinfo=timezone.utc)

    def call(self, body="{}", *, actor=None, session=None):
        request = RequestFactory().post(
            "/api/v1/parties/10/leave", data=body, content_type="application/json"
        )
        request.user = self.actor if actor is None else actor
        request.session = {"university_identity_id": 30} if session is None else session
        return leave_party_api(request, 10)

    def test_ut01_anonymous_never_calls_identity_or_leave(self):
        with (
            patch("accounts.decorators.UniversityIdentity.objects.filter") as identity,
            patch("parties.views.leave_party") as service,
        ):
            response = self.call(actor=SimpleNamespace(is_authenticated=False))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(json.loads(response.content)["error"]["code"], "AUTH_REQUIRED")
        identity.assert_not_called()
        service.assert_not_called()

    def test_ut01_unverified_and_inactive_never_call_leave(self):
        with (
            patch("accounts.decorators.UniversityIdentity.objects.filter") as identity,
            patch("parties.views.leave_party") as service,
        ):
            identity.return_value.first.return_value = None
            response = self.call()
            self.assertEqual(response.status_code, 403)
            self.assertEqual(json.loads(response.content)["error"]["code"], "FORBIDDEN")
            response = self.call(session={})
            self.assertEqual(response.status_code, 403)
            response = self.call(actor=SimpleNamespace(is_authenticated=True, is_active=False))
            self.assertEqual(json.loads(response.content)["error"]["code"], "ACCOUNT_INACTIVE")
            service.assert_not_called()

    def test_ut01_client_selected_actor_is_rejected_before_service(self):
        with (
            patch("accounts.decorators.UniversityIdentity.objects.filter") as identity,
            patch("parties.views.leave_party") as service,
        ):
            identity.return_value.first.return_value = SimpleNamespace(pk=30)
            for body in ['{"user_id":99}', '{"membership_id":99}', '{"host_id":99}']:
                with self.subTest(body=body):
                    response = self.call(body)
                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(json.loads(response.content)["error"]["code"], "INVALID_INPUT")
            service.assert_not_called()

    def test_ut02_passes_only_session_actor_and_path_to_service(self):
        with (
            patch("accounts.decorators.UniversityIdentity.objects.filter") as identity,
            patch("parties.views.leave_party") as service,
        ):
            identity.return_value.first.return_value = SimpleNamespace(pk=30)
            service.return_value = SimpleNamespace(party_id=10, left_at=self.instant)
            response = self.call()
            service.assert_called_once_with(party_id=10, user=self.actor)
            identity.assert_called_once_with(
                pk=30,
                user=self.actor,
                provider_key="tu",
                student_verified_at__isnull=False,
                eligibility_checked_at__isnull=False,
            )
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)["data"]
        self.assertEqual(set(payload), {"party_id", "is_member", "left_at"})
        self.assertEqual((payload["party_id"], payload["is_member"]), (10, False))
        self.assertEqual(datetime.fromisoformat(payload["left_at"]), self.instant)


class LeaveServiceUnitTests(SimpleTestCase):
    def setUp(self):
        self.now = datetime(2030, 11, 20, 9, tzinfo=timezone.utc)
        self.actor = SimpleNamespace(pk=20)
        self.party = SimpleNamespace(
            pk=10, host_id=1, starts_at=self.now + timedelta(hours=1), cancelled_at=None
        )
        self.membership = Mock(left_at=None)
        self.party_manager = self.enterContext(patch("parties.services.Party.objects"))
        self.member_manager = self.enterContext(patch("parties.services.PartyMembership.objects"))
        self.clock = self.enterContext(
            patch("parties.services.timezone.now", return_value=self.now)
        )
        self.party_manager.select_for_update.return_value.get.return_value = self.party
        self.member_query = self.member_manager.select_for_update.return_value.filter
        self.member_query.return_value.first.return_value = self.membership

    def leave(self):
        # Exercise business logic only; atomic/row locking require DB integration.
        return leave_party.__wrapped__(party_id=10, user=self.actor)

    def assert_denied(self, code, status):
        with self.assertRaises(PartyError) as caught:
            self.leave()
        self.assertEqual((caught.exception.code, caught.exception.status), (code, status))
        self.assertIsNone(self.membership.left_at)
        self.membership.save.assert_not_called()

    def test_ut02_active_member_before_start_is_soft_left_once(self):
        self.assertIs(self.leave(), self.membership)
        self.member_query.assert_called_once_with(party=self.party, user=self.actor)
        self.clock.assert_called_once_with()
        self.assertEqual(self.membership.left_at, self.now)
        self.membership.save.assert_called_once_with(update_fields=["left_at"])
        self.party_manager.select_for_update.return_value.get.assert_called_once_with(pk=10)

    def test_ut03_left_member_is_not_written_again_even_after_state_change(self):
        previous = self.now - timedelta(days=1)
        self.membership.left_at = previous
        self.party.cancelled_at = self.now
        self.party.starts_at = self.now - timedelta(hours=2)
        self.assertIs(self.leave(), self.membership)
        self.assertEqual(self.membership.left_at, previous)
        self.membership.save.assert_not_called()
        self.clock.assert_not_called()

    def test_ut04_host_is_rejected_before_membership_or_time(self):
        self.party.host_id = self.actor.pk
        self.party.cancelled_at = self.now
        self.assert_denied("HOST_CANNOT_LEAVE", 403)
        self.member_manager.select_for_update.assert_not_called()
        self.clock.assert_not_called()

    def test_ut01_nonmember_cannot_mutate_or_select_another_membership(self):
        self.member_query.return_value.first.return_value = None
        self.assert_denied("NOT_MEMBER", 403)
        self.member_query.assert_called_once_with(party=self.party, user=self.actor)
        self.clock.assert_not_called()

    def test_ut05_exact_start_and_after_start_are_rejected(self):
        for instant in [
            self.party.starts_at,
            self.party.starts_at + timedelta(microseconds=1),
            self.party.starts_at + timedelta(hours=2),
        ]:
            with self.subTest(instant=instant):
                self.clock.return_value = instant
                self.assert_denied("PARTY_STARTED", 409)

    def test_ut05_one_microsecond_before_start_is_allowed(self):
        self.clock.return_value = self.party.starts_at - timedelta(microseconds=1)
        self.leave()
        self.assertEqual(self.membership.left_at, self.clock.return_value)
        self.membership.save.assert_called_once_with(update_fields=["left_at"])

    def test_ut05_cancelled_precedes_time_and_never_writes(self):
        self.party.cancelled_at = self.now
        self.party.starts_at = self.now - timedelta(hours=2)
        self.assert_denied("PARTY_CANCELLED", 409)
        self.clock.assert_not_called()
