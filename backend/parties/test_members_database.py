"""Task66: independent SQL versus merged Members/Leave APIs on PostgreSQL."""

from io import StringIO
from pathlib import Path

from accounts.models import UserProfile
from accounts.test_support import force_university_login
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from .models import JoinRequest, Party, PartyMembership


@override_settings(DEBUG=True)
class MembersDatabaseIntegrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.reference = timezone.now()
        call_command(
            "seed_sprint2", confirm_test_data=True, at=cls.reference.isoformat(), stdout=StringIO()
        )
        cls.party = Party.objects.get(title="[S2-DATA] Open")
        cls.users = {
            key: get_user_model().objects.get(username=f"s2data_{key}")
            for key in ("h", "m", "a", "b", "left", "x")
        }

    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        force_university_login(self.client, self.users["h"])
        token = self.client.get("/api/v1/auth/csrf").json()["data"]["csrf_token"]
        self.client.defaults["HTTP_X_CSRFTOKEN"] = token

    def assert_members_match_sql(self, party):
        # Execute the independent SQL file, not the endpoint's helper/ORM query.
        sql = Path(__file__).resolve().parents[2] / "database/seeds/us6_active_members.sql"
        with connection.cursor() as cursor:
            cursor.execute(sql.read_text(encoding="utf-8"))
            rows = [row for row in cursor.fetchall() if row[0] == party.pk]
        response = self.client.get(f"/api/v1/parties/{party.pk}/members")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        actual = data["members"]
        expected_ids = [row[3] for row in rows]
        self.assertCountEqual([row["user_id"] for row in actual], expected_ids)
        self.assertEqual(len({row["user_id"] for row in actual}), len(actual))
        self.assertEqual(data["member_count"], len(rows))
        expected_roles = {row[3]: row[5] for row in rows}
        self.assertEqual({row["user_id"]: row["role"] for row in actual}, expected_roles)
        detail = self.client.get(f"/api/v1/parties/{party.pk}")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["data"]["member_count"], len(rows))
        return data

    def test_db66_a01_baseline_six_parties_excludes_requests_and_left_history(self):
        for party in Party.objects.order_by("pk"):
            with self.subTest(party=party.title):
                data = self.assert_members_match_sql(party)
                self.assertEqual(data["member_count"], 2)
        self.assertEqual(self.party.join_requests.get(user=self.users["a"]).status, "Pending")
        self.assertEqual(self.party.join_requests.get(user=self.users["b"]).status, "Rejected")
        self.assertIsNotNone(self.party.memberships.get(user=self.users["left"]).left_at)

    def test_db66_a02_approve_via_http_increases_sql_and_api_once(self):
        request = self.party.join_requests.get(user=self.users["a"])
        url = f"/api/v1/parties/{self.party.pk}/join-requests/{request.pk}/decision"
        response = self.client.post(url, {"status": "Approved"}, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.assert_members_match_sql(self.party)["member_count"], 3)
        self.assertEqual(
            self.client.post(
                url, {"status": "Approved"}, content_type="application/json"
            ).status_code,
            409,
        )
        self.assertEqual(self.assert_members_match_sql(self.party)["member_count"], 3)
        request.refresh_from_db()
        self.assertEqual(request.status, "Approved")

    def test_db66_a03_reject_via_http_does_not_create_membership(self):
        party = Party.objects.get(title="[S2-DATA] Last slot")
        request = party.join_requests.get(user=self.users["b"])
        response = self.client.post(
            f"/api/v1/parties/{party.pk}/join-requests/{request.pk}/decision",
            {"status": "Rejected"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.assert_members_match_sql(party)["member_count"], 2)
        self.assertFalse(party.memberships.filter(user=self.users["b"]).exists())
        request.refresh_from_db()
        self.assertEqual(request.status, "Rejected")

    def test_db66_a04_prepared_left_state_preserves_history_and_decrements_once(self):
        # This prepares DB state; it does NOT test a real US4 leave endpoint.
        membership = self.party.memberships.get(user=self.users["m"])
        original = (membership.pk, membership.joined_at)
        for _ in range(2):
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE parties_partymembership SET left_at=%s WHERE id=%s",
                    [self.reference, membership.pk],
                )
            self.assertEqual(self.assert_members_match_sql(self.party)["member_count"], 1)
        membership.refresh_from_db()
        self.assertEqual((membership.pk, membership.joined_at), original)
        self.assertEqual(membership.left_at, self.reference)
        self.assertEqual(self.party.join_requests.get(user=self.users["m"]).status, "Approved")

    def test_db66_a05_profile_missing_and_other_party_do_not_change_members(self):
        UserProfile.objects.filter(user=self.users["m"]).delete()
        other = Party.objects.get(title="[S2-DATA] Last slot")
        PartyMembership.objects.create(party=other, user=self.users["x"])
        data = self.assert_members_match_sql(self.party)
        member = next(row for row in data["members"] if row["user_id"] == self.users["m"].pk)
        self.assertEqual(member["display_name"], "ผู้ใช้")
        self.assertEqual(self.assert_members_match_sql(other)["member_count"], 3)

    def test_db66_a06_get_does_not_mutate_membership_request_or_profile(self):
        models = (PartyMembership, JoinRequest, UserProfile)
        before = [list(model.objects.order_by("pk").values()) for model in models]
        self.assert_members_match_sql(self.party)
        self.assertEqual(before, [list(model.objects.order_by("pk").values()) for model in models])

    def test_db66_a07_legacy_host_must_not_disagree_with_actual_sql_rows(self):
        # Regression: a Host may read but must not be synthesized as an active row.
        self.party.memberships.filter(user=self.users["h"]).update(left_at=self.reference)
        self.assert_members_match_sql(self.party)

    def test_db66_a08_real_leave_retry_matches_sql_and_preserves_history(self):
        member_client = Client(enforce_csrf_checks=True)
        force_university_login(member_client, self.users["m"])
        token = member_client.get("/api/v1/auth/csrf").json()["data"]["csrf_token"]
        membership = self.party.memberships.get(user=self.users["m"])
        original = (membership.pk, membership.joined_at)
        request_before = list(self.party.join_requests.order_by("pk").values())
        capacity = self.party.capacity
        first = None
        for attempt in range(2):
            response = member_client.post(
                f"/api/v1/parties/{self.party.pk}/leave",
                {},
                content_type="application/json",
                HTTP_X_CSRFTOKEN=token,
            )
            self.assertEqual(response.status_code, 200)
            if attempt == 0:
                first = response.json()
            self.assertEqual(response.json(), first)
            self.assertEqual(self.assert_members_match_sql(self.party)["member_count"], 1)
        membership.refresh_from_db()
        self.assertEqual((membership.pk, membership.joined_at), original)
        self.assertIsNotNone(membership.left_at)
        self.assertEqual(request_before, list(self.party.join_requests.order_by("pk").values()))
        self.party.refresh_from_db()
        self.assertEqual(self.party.capacity, capacity)
        self.assertEqual(
            member_client.get(f"/api/v1/parties/{self.party.pk}/members").status_code, 403
        )
        detail = member_client.get(f"/api/v1/parties/{self.party.pk}").json()["data"]
        self.assertEqual(
            (detail["is_member"], detail["member_count"], detail["remaining_slots"]),
            (False, 1, capacity - 1),
        )

    def test_db66_a09_host_without_membership_is_not_synthesized(self):
        self.party.memberships.filter(user=self.users["h"]).delete()
        data = self.assert_members_match_sql(self.party)
        self.assertEqual(data["member_count"], 1)
        self.assertNotIn(self.users["h"].pk, [row["user_id"] for row in data["members"]])
