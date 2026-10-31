"""Task50: host-only Pending reads, using PostgreSQL and local university sessions."""

from datetime import timedelta

from accounts.models import UserProfile
from accounts.test_support import force_university_login
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from venues.models import Sport, Venue

from .models import JoinRequest, Party, PartyMembership


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
