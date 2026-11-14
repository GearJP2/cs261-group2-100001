"""Task60 DB query checks. Members endpoint/UAT acceptance belongs to Task66."""

from io import StringIO
from pathlib import Path

from accounts.models import UserProfile
from accounts.test_support import force_university_login
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import JoinRequest, Party, PartyMembership
from .services import active_memberships, count_active_members


@override_settings(DEBUG=True)
class ActiveMembershipQueryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.reference = timezone.now()
        call_command(
            "seed_sprint2",
            confirm_test_data=True,
            at=cls.reference.isoformat(),
            stdout=StringIO(),
        )
        cls.party = Party.objects.get(title="[S2-DATA] Open")
        cls.host = get_user_model().objects.get(username="s2data_h")
        cls.member = get_user_model().objects.get(username="s2data_m")
        cls.left = get_user_model().objects.get(username="s2data_left")

    def test_actual_members_not_requests_or_other_parties_determine_count(self):
        for party in Party.objects.all():
            with self.subTest(party=party.title):
                rows = list(active_memberships(party))
                self.assertEqual({row.user_id for row in rows}, {self.host.pk, self.member.pk})
                self.assertEqual(len(rows), count_active_members(party))
                self.assertEqual(len(rows), 2)
        self.assertTrue(self.party.join_requests.filter(status="Pending").exists())
        self.assertTrue(self.party.join_requests.filter(status="Rejected").exists())
        self.assertTrue(self.party.join_requests.filter(user=self.left, status="Approved").exists())
        other = Party.objects.get(title="[S2-DATA] Last slot")
        outsider = get_user_model().objects.get(username="s2data_x")
        PartyMembership.objects.create(party=other, user=outsider)
        self.assertNotIn(
            outsider.pk, active_memberships(self.party).values_list("user_id", flat=True)
        )
        self.assertEqual(count_active_members(other), 3)
        self.assertEqual(count_active_members(self.party), 2)

    def test_profile_is_optional_and_reading_all_profiles_needs_one_query(self):
        UserProfile.objects.filter(user=self.member).delete()
        for index in range(5):
            user = get_user_model().objects.create_user(username=f"query_member_{index}")
            UserProfile.objects.create(user=user, display_name=f"Member {index}")
            PartyMembership.objects.create(party=self.party, user=user)
        with self.assertNumQueries(1):
            rows = list(active_memberships(self.party))
            profiles = {row.user_id: getattr(row.user, "profile", None) for row in rows}
        self.assertEqual(len(rows), 7)
        self.assertIsNone(profiles[self.member.pk])
        self.assertEqual(profiles[self.host.pk].display_name, "S2-DATA H")
        with self.assertNumQueries(1):
            self.assertEqual(count_active_members(self.party), 7)

    def test_reads_preserve_memberships_requests_and_profiles(self):
        models = (PartyMembership, JoinRequest, UserProfile)
        before = [list(model.objects.order_by("pk").values()) for model in models]
        list(active_memberships(self.party))
        count_active_members(self.party)
        self.assertEqual(before, [list(model.objects.order_by("pk").values()) for model in models])
        history = self.party.memberships.get(user=self.left)
        self.assertIsNotNone(history.left_at)

    def test_soft_leave_changes_count_once_without_erasing_history(self):
        membership = self.party.memberships.get(user=self.member)
        original_id = membership.pk
        original_joined = membership.joined_at
        for _ in range(2):
            PartyMembership.objects.filter(pk=original_id).update(left_at=self.reference)
            self.assertEqual(count_active_members(self.party), 1)
            self.assertEqual(
                list(active_memberships(self.party).values_list("user_id", flat=True)),
                [self.host.pk],
            )
        membership.refresh_from_db()
        self.assertEqual(membership.joined_at, original_joined)
        self.assertEqual(membership.left_at, self.reference)
        self.assertTrue(
            self.party.join_requests.filter(user=self.member, status="Approved").exists()
        )

    def test_missing_or_departed_host_is_not_invented_by_read_query(self):
        host_row = self.party.memberships.get(user=self.host)
        host_row.left_at = self.reference
        host_row.save(update_fields=["left_at"])
        self.assertEqual(count_active_members(self.party), 1)
        self.assertEqual(
            list(active_memberships(self.party).values_list("user_id", flat=True)), [self.member.pk]
        )
        self.assertIsNotNone(self.party.memberships.get(pk=host_row.pk).left_at)
        self.party.memberships.all().delete()
        self.assertEqual(count_active_members(self.party), 0)
        self.assertEqual(list(active_memberships(self.party)), [])

    def test_existing_party_detail_and_list_counts_agree_with_query(self):
        force_university_login(self.client, self.host)
        detail = self.client.get(reverse("party-detail", args=[self.party.pk]))
        self.assertEqual(detail.status_code, 200)
        expected = count_active_members(self.party)
        self.assertEqual(detail.json()["data"]["member_count"], expected)
        response = self.client.get(reverse("party-create"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        party_data = next(row for row in payload if row["id"] == self.party.pk)
        self.assertEqual(party_data["member_count"], expected)
        self.assertEqual(party_data["remaining_slots"], self.party.capacity - expected)

    def test_sql_file_and_shared_query_agree_including_absent_profile(self):
        if connection.vendor != "postgresql":
            self.skipTest("SQL oracle uses PostgreSQL window functions")
        UserProfile.objects.filter(user=self.member).delete()
        sql = Path(__file__).resolve().parents[2] / "database/seeds/us6_active_members.sql"
        with connection.cursor() as cursor:
            cursor.execute(sql.read_text(encoding="utf-8"))
            sql_rows = cursor.fetchall()
        self.assertEqual(len(sql_rows), 12)
        for party in Party.objects.all():
            expected = list(active_memberships(party).values_list("user_id", flat=True))
            actual = [row[3] for row in sql_rows if row[0] == party.pk]
            self.assertEqual(actual, expected)
        self.assertTrue(all(row[7] == 2 for row in sql_rows))
        self.assertEqual({row[4] for row in sql_rows if row[3] == self.member.pk}, {"ผู้ใช้"})
