"""Task50: host-only Pending reads, using PostgreSQL and local university sessions."""

import json
from datetime import timedelta

from accounts.models import UniversityIdentity, UserProfile
from accounts.test_support import force_university_login
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from venues.models import Sport, Venue

from .models import JoinRequest, Party, PartyMembership
from .services import get_party_state
from .views import join_requests


class PendingRequestApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model()
        cls.host = users.objects.create_user("pending-host")
        cls.other_host = users.objects.create_user("other-host")
        cls.applicant = users.objects.create_user(
            "private-applicant-login", email="private-applicant@example.invalid"
        )
        cls.second = users.objects.create_user("private-second-login")
        cls.no_profile = users.objects.create_user("private-no-profile-login")
        cls.member = users.objects.create_user("member")
        cls.rejected = users.objects.create_user("rejected")
        UserProfile.objects.create(user=cls.applicant, display_name="ผู้สมัครคนแรก")
        UserProfile.objects.create(user=cls.second, display_name="ผู้สมัครคนที่สอง")
        cls.now = timezone.now()
        sport = Sport.objects.create(name="Badminton")
        venue = Venue.objects.create(name="Court", location_text="Campus")
        cls.party = Party.objects.create(
            host=cls.host,
            sport=sport,
            venue=venue,
            title="Pending review",
            starts_at=cls.now + timedelta(days=1),
            ends_at=cls.now + timedelta(days=1, hours=1),
            capacity=4,
        )
        cls.other_party = Party.objects.create(
            host=cls.other_host,
            sport=sport,
            venue=venue,
            title="Another host's party",
            starts_at=cls.party.starts_at,
            ends_at=cls.party.ends_at,
            capacity=4,
        )
        PartyMembership.objects.create(party=cls.party, user=cls.host)
        PartyMembership.objects.create(party=cls.party, user=cls.member)
        PartyMembership.objects.create(party=cls.other_party, user=cls.other_host)
        # Deliberately separate request/user IDs and insertion/PK order.
        cls.first_request = JoinRequest.objects.create(pk=1003, party=cls.party, user=cls.applicant)
        cls.second_request = JoinRequest.objects.create(pk=1001, party=cls.party, user=cls.second)
        cls.third_request = JoinRequest.objects.create(
            pk=1002, party=cls.party, user=cls.no_profile
        )
        cls.pending_ids = [cls.first_request.pk, cls.second_request.pk, cls.third_request.pk]
        for offset, request_id in enumerate(cls.pending_ids):
            JoinRequest.objects.filter(pk=request_id).update(
                created_at=cls.now - timedelta(minutes=3 - offset)
            )
        for user, status in (
            (cls.member, JoinRequest.Status.APPROVED),
            (cls.rejected, JoinRequest.Status.REJECTED),
        ):
            JoinRequest.objects.create(
                party=cls.party,
                user=user,
                status=status,
                decided_at=cls.now,
                decided_by=cls.host,
            )
        cls.other_request = JoinRequest.objects.create(party=cls.other_party, user=cls.applicant)

    def setUp(self):
        self.identity = force_university_login(self.client, self.host)
        self.url = reverse("party-join-request-list", args=[self.party.pk])

    def domain_snapshot(self):
        return {
            model.__name__: list(model.objects.order_by("pk").values())
            for model in (Party, JoinRequest, PartyMembership)
        }

    def read(self, *, client=None, url=None, data=None):
        before = self.domain_snapshot()
        response = (client or self.client).get(url or self.url, data=data)
        self.assertEqual(self.domain_snapshot(), before)
        return response

    def assert_pending(self, response, expected_ids=None):
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertIn("no-store", response["Cache-Control"])
        payload = response.json()
        self.assertEqual(set(payload), {"data"})
        self.assertIsInstance(payload["data"], list)
        self.assertEqual(
            [row["id"] for row in payload["data"]],
            self.pending_ids if expected_ids is None else expected_ids,
        )
        for row in payload["data"]:
            self.assertEqual(set(row), {"id", "display_name", "created_at"})
        return payload["data"]

    def assert_error(self, response, status, code):
        self.assertEqual(response.status_code, status)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertIn("no-store", response["Cache-Control"])
        payload = json.loads(response.content)
        self.assertEqual(set(payload), {"error"})
        self.assertEqual(set(payload["error"]), {"code", "message"})
        self.assertEqual(payload["error"]["code"], code)
        self.assertNotIn("Location", response)

    def test_host_reads_only_own_pending_with_exact_public_fields(self):
        # PEND-01/02: decided requests and another Party's Pending stay private.
        self.assertEqual(self.url, f"/api/v1/parties/{self.party.pk}/join-requests/pending")
        rows = self.assert_pending(self.read())
        self.assertEqual(rows[0]["display_name"], "ผู้สมัครคนแรก")
        self.assertNotEqual(rows[0]["id"], self.applicant.pk)

    def test_no_pending_returns_empty_array_even_when_decided_requests_exist(self):
        # PEND-03: retain Approved/Rejected records, remove Pending from this fixture.
        JoinRequest.objects.filter(party=self.party, status=JoinRequest.Status.PENDING).delete()
        self.assert_pending(self.read(), expected_ids=[])

    def test_query_cannot_change_actor_party_or_status(self):
        # PEND-08: ignored client-selected actors/filters do not broaden the query.
        self.assert_pending(
            self.read(
                data={
                    "user_id": self.other_host.pk,
                    "host_id": self.other_host.pk,
                    "party_id": self.other_party.pk,
                    "status": "Approved",
                }
            )
        )

    def test_missing_profile_has_safe_fallback_without_private_identifiers(self):
        # PEND-10: no automatic profile creation or username/email fallback.
        response = self.read()
        rows = self.assert_pending(response)
        self.assertEqual(rows[2]["display_name"], "ผู้ใช้")
        for user in (self.applicant, self.second, self.no_profile):
            for secret in (user.username, user.email, user.password):
                if secret:
                    self.assertNotIn(secret, response.content.decode())
        self.assertFalse(UserProfile.objects.filter(user=self.no_profile).exists())

    def test_oldest_first_and_equal_timestamps_use_request_id(self):
        # PEND-11: insertion order differs from PK order so ties need a stable key.
        self.assert_pending(self.read())
        JoinRequest.objects.filter(pk__in=self.pending_ids).update(created_at=self.now)
        self.assert_pending(self.read(), expected_ids=sorted(self.pending_ids))

    def test_created_at_has_bangkok_offset_without_changing_instant(self):
        # PEND-12: check both the timezone offset and the underlying timestamp.
        rows = self.assert_pending(self.read())
        for row in rows:
            timestamp = parse_datetime(row["created_at"])
            self.assertIsNotNone(timestamp)
            self.assertEqual(timestamp.utcoffset(), timedelta(hours=7))
            self.assertEqual(timestamp, JoinRequest.objects.get(pk=row["id"]).created_at)

    def test_refresh_removes_decided_request_and_responses_are_not_cached(self):
        # PEND-16: fixture mutation is not proof that the decision API was exercised.
        self.assert_pending(self.read())
        JoinRequest.objects.filter(pk=self.first_request.pk).update(
            status=JoinRequest.Status.REJECTED, decided_at=self.now, decided_by=self.host
        )
        self.assert_pending(self.read(), expected_ids=self.pending_ids[1:])

    def test_repeated_reads_preserve_requests_memberships_and_slots(self):
        # PEND-18: compare every domain row, including decision and update timestamps.
        before = self.domain_snapshot()
        self.assert_pending(self.read())
        self.assert_pending(self.read())
        self.assertEqual(self.domain_snapshot(), before)
        detail = self.read(url=reverse("party-detail", args=[self.party.pk])).json()["data"]
        self.assertEqual(detail["member_count"], 2)
        self.assertEqual(detail["remaining_slots"], 2)

    def test_non_hosts_cannot_read_even_if_member_applicant_or_staff(self):
        # PEND-04: membership/administrative flags are not ownership of this Party.
        PartyMembership.objects.create(party=self.party, user=self.second, left_at=self.now)
        self.other_host.is_staff = True
        self.other_host.is_superuser = True
        self.other_host.save(update_fields=["is_staff", "is_superuser"])
        for user in (self.other_host, self.applicant, self.member, self.second):
            with self.subTest(user=user.username):
                force_university_login(self.client, user)
                self.assert_error(self.read(), 403, "FORBIDDEN")

    def test_host_authorization_does_not_depend_on_membership_row(self):
        PartyMembership.objects.filter(party=self.party, user=self.host).delete()
        self.assert_pending(self.read())

    def test_anonymous_denied_before_party_lookup(self):
        # PEND-05: both existing and nonexistent Party IDs are protected.
        self.client.logout()
        for party_id in (self.party.pk, 0):
            with self.subTest(party_id=party_id):
                url = reverse("party-join-request-list", args=[party_id])
                self.assert_error(self.read(url=url), 401, "AUTH_REQUIRED")

    def test_missing_invalid_or_other_users_identity_is_forbidden(self):
        # PEND-06: even a valid identity belonging to another user cannot be reused.
        other_identity = UniversityIdentity.objects.create(
            user=self.other_host,
            provider_key="tu",
            subject="other-host-identity",
            student_verified_at=self.now,
            eligibility_checked_at=self.now,
        )
        for identity_id in (None, 0, -1, True, str(self.identity.pk), other_identity.pk):
            with self.subTest(identity_id=identity_id):
                session = self.client.session
                if identity_id is None:
                    session.pop("university_identity_id", None)
                else:
                    session["university_identity_id"] = identity_id
                session.save()
                self.assert_error(self.read(), 403, "FORBIDDEN")

    def test_unverified_or_wrong_provider_identity_is_forbidden(self):
        # PEND-06: changing evidence in the DB takes effect on the next request.
        valid = {
            "provider_key": "tu",
            "student_verified_at": self.now,
            "eligibility_checked_at": self.now,
        }
        for changes in (
            {"provider_key": "other"},
            {"student_verified_at": None},
            {"eligibility_checked_at": None},
        ):
            with self.subTest(changes=changes):
                UniversityIdentity.objects.filter(pk=self.identity.pk).update(**(valid | changes))
                self.assert_error(self.read(), 403, "FORBIDDEN")

    def test_missing_party_and_unmatched_routes_return_404(self):
        # PEND-07 and routing boundaries: only a matched route promises JSON.
        self.assert_error(
            self.read(url=reverse("party-join-request-list", args=[0])), 404, "NOT_FOUND"
        )
        for party_id in ("abc", "-1"):
            with self.subTest(party_id=party_id):
                response = self.read(url=f"/api/v1/parties/{party_id}/join-requests/pending")
                self.assertEqual(response.status_code, 404)

    def test_other_host_cannot_impersonate_owner_with_query(self):
        # PEND-09: host/user IDs from the client never establish ownership.
        force_university_login(self.client, self.other_host)
        response = self.read(data={"host_id": self.host.pk, "user_id": self.host.pk})
        self.assert_error(response, 403, "FORBIDDEN")

    def test_expired_session_cannot_read_previously_visible_requests(self):
        # PEND-13: expire the actual server session instead of calling force_logout.
        self.assert_pending(self.read())
        Session.objects.filter(session_key=self.client.session.session_key).update(
            expire_date=timezone.now() - timedelta(seconds=1)
        )
        self.assert_error(self.read(), 401, "AUTH_REQUIRED")

    def test_real_logout_revokes_copied_cookie_for_pending_reads(self):
        # PEND-13: exercise the application's CSRF-protected logout endpoint.
        browser = Client(enforce_csrf_checks=True)
        force_university_login(browser, self.host)
        self.assert_pending(self.read(client=browser))
        old_cookie = browser.cookies[settings.SESSION_COOKIE_NAME].value
        token = browser.get(reverse("accounts:csrf")).json()["data"]["csrf_token"]
        before = self.domain_snapshot()
        response = browser.post(reverse("accounts:logout"), HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.domain_snapshot(), before)
        self.assertFalse(Session.objects.filter(session_key=old_cookie).exists())
        stale = Client(enforce_csrf_checks=True)
        stale.cookies[settings.SESSION_COOKIE_NAME] = old_cookie
        self.assert_error(self.read(client=browser), 401, "AUTH_REQUIRED")
        self.assert_error(self.read(client=stale), 401, "AUTH_REQUIRED")

    def test_inactive_host_session_is_anonymous_under_model_backend(self):
        # PEND-14: HTTP behavior differs from the direct inactive-guard seam below.
        self.assert_pending(self.read())
        self.host.is_active = False
        self.host.save(update_fields=["is_active"])
        self.assert_error(self.read(), 401, "AUTH_REQUIRED")

    def test_authenticated_inactive_guard_denies_without_database_query(self):
        # PEND-14: direct guard branch, not proof of an inactive HTTP session.
        request = RequestFactory().get(self.url)
        request.user = self.host
        request.user.is_active = False
        with self.assertNumQueries(0):
            response = join_requests(request, party_id=self.party.pk)
        self.assert_error(response, 403, "ACCOUNT_INACTIVE")

    def test_unsupported_methods_and_csrf_failures_do_not_write(self):
        # PEND-15: real CSRF checks distinguish middleware rejection from view 405.
        browser = Client(enforce_csrf_checks=True)
        force_university_login(browser, self.host)
        self.assert_pending(self.read(client=browser))  # GET needs no CSRF token.
        before = self.domain_snapshot()
        self.assert_error(browser.post(self.url), 403, "CSRF_FAILED")
        self.assertEqual(self.domain_snapshot(), before)
        token = browser.get(reverse("accounts:csrf")).json()["data"]["csrf_token"]
        for method in ("head", "options", "post", "put", "patch", "delete"):
            with self.subTest(method=method):
                response = browser.generic(
                    method.upper(),
                    self.url,
                    data="{}",
                    content_type="application/json",
                    HTTP_X_CSRFTOKEN=token,
                )
                self.assertEqual(response.status_code, 405)
                self.assertEqual(response["Allow"], "GET")
                if method == "head":
                    self.assertEqual(response.content, b"")
                    self.assertIn("no-store", response["Cache-Control"])
                else:
                    self.assert_error(response, 405, "METHOD_NOT_ALLOWED")
                self.assertEqual(self.domain_snapshot(), before)

    def test_host_can_read_pending_in_every_party_state(self):
        # PEND-17: reads keep history visible; the decision API enforces write rules.
        future = self.now + timedelta(days=1)
        defaults = {
            "capacity": 4,
            "starts_at": future,
            "ends_at": future + timedelta(hours=1),
            "cancelled_at": None,
        }
        cases = {
            "Open": {},
            "Full": {"capacity": 2},
            "InProgress": {
                "starts_at": self.now - timedelta(hours=1),
                "ends_at": self.now + timedelta(hours=1),
            },
            "Completed": {
                "starts_at": self.now - timedelta(hours=2),
                "ends_at": self.now - timedelta(hours=1),
            },
            "Cancelled": {"cancelled_at": self.now},
        }
        for state, changes in cases.items():
            with self.subTest(state=state):
                Party.objects.filter(pk=self.party.pk).update(**(defaults | changes))
                self.party.refresh_from_db()
                self.assertEqual(get_party_state(self.party), state)
                self.assert_pending(self.read())
