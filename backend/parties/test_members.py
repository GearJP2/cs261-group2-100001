"""S2-US6-B-01: active member reads, using PostgreSQL and local university sessions."""

import json
from datetime import timedelta

from accounts.models import UserProfile
from accounts.test_support import force_university_login
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from venues.models import Sport, Venue

from .models import JoinRequest, Party, PartyMembership


def decoded_body(response):
    # JsonResponse escapes non-ASCII, so raw content can never contain Thai names.
    return json.dumps(response.json(), ensure_ascii=False)


class PartyMembersApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model()
        cls.now = timezone.now()
        cls.host = users.objects.create_user(
            "private-host-login", email="private-host@example.invalid"
        )
        cls.member = users.objects.create_user(
            "private-member-login", email="private-member@example.invalid"
        )
        cls.no_profile = users.objects.create_user(
            "private-no-profile-login", email="private-no-profile@example.invalid"
        )
        cls.left = users.objects.create_user("private-left-login")
        cls.pending = users.objects.create_user("private-pending-login")
        cls.rejected = users.objects.create_user("private-rejected-login")
        cls.outsider = users.objects.create_user("private-outsider-login")
        cls.other_member = users.objects.create_user("private-other-member-login")
        UserProfile.objects.create(user=cls.host, display_name="นามแฝงผู้จัด")
        UserProfile.objects.create(user=cls.member, display_name="นามแฝงสมาชิก", credit_score=987654)
        UserProfile.objects.create(user=cls.left, display_name="นามแฝงคนถอนตัว")
        UserProfile.objects.create(user=cls.pending, display_name="นามแฝงคนรออนุมัติ")
        UserProfile.objects.create(user=cls.rejected, display_name="นามแฝงคนถูกปฏิเสธ")
        UserProfile.objects.create(user=cls.other_member, display_name="นามแฝงสมาชิกปาร์ตี้อื่น")
        sport = Sport.objects.create(name="Badminton")
        venue = Venue.objects.create(name="Court", location_text="Campus")
        schedule = {
            "sport": sport,
            "venue": venue,
            "starts_at": cls.now + timedelta(days=1),
            "ends_at": cls.now + timedelta(days=1, hours=1),
            "capacity": 10,
        }
        cls.party = Party.objects.create(host=cls.host, title="Members", **schedule)
        cls.other_party = Party.objects.create(host=cls.outsider, title="Other", **schedule)
        # Insert the Host last so ordering cannot pass by relying on PK order alone.
        PartyMembership.objects.create(party=cls.party, user=cls.no_profile)
        cls.member_row = PartyMembership.objects.create(party=cls.party, user=cls.member)
        cls.host_row = PartyMembership.objects.create(party=cls.party, user=cls.host)
        cls.left_row = PartyMembership.objects.create(
            party=cls.party, user=cls.left, left_at=cls.now
        )
        PartyMembership.objects.create(party=cls.other_party, user=cls.other_member)
        JoinRequest.objects.create(party=cls.party, user=cls.pending)
        JoinRequest.objects.create(
            party=cls.party,
            user=cls.rejected,
            status=JoinRequest.Status.REJECTED,
            decided_at=cls.now,
            decided_by=cls.host,
        )

    def setUp(self):
        force_university_login(self.client, self.host)
        self.url = reverse("party-members", args=[self.party.pk])

    def assert_members(self, response, expected_user_ids):
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertIn("no-store", response["Cache-Control"])
        payload = response.json()
        self.assertEqual(set(payload), {"data"})
        data = payload["data"]
        self.assertEqual(set(data), {"members", "member_count"})
        self.assertEqual([row["user_id"] for row in data["members"]], expected_user_ids)
        self.assertEqual(data["member_count"], len(data["members"]))
        for row in data["members"]:
            self.assertEqual(set(row), {"user_id", "display_name", "role"})
        return data["members"]

    def assert_error(self, response, status, code):
        self.assertEqual(response.status_code, status)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertIn("no-store", response["Cache-Control"])
        payload = response.json()
        self.assertEqual(set(payload), {"error"})
        self.assertEqual(set(payload["error"]), {"code", "message"})
        self.assertEqual(payload["error"]["code"], code)
        return payload["error"]

    def assert_forbidden_without_leak(self, response):
        self.assert_error(response, 403, "FORBIDDEN")
        body = decoded_body(response)
        for key in ("data", "members", "member_count"):
            self.assertNotIn(key, body)
        for name in ("นามแฝงผู้จัด", "นามแฝงสมาชิก"):
            self.assertNotIn(name, body)

    def test_anonymous_denied_before_party_lookup(self):
        self.client.logout()
        for party_id in (self.party.pk, 0):
            with self.subTest(party_id=party_id):
                response = self.client.get(reverse("party-members", args=[party_id]))
                self.assert_error(response, 401, "AUTH_REQUIRED")

    def test_local_login_without_university_identity_is_forbidden(self):
        self.client.logout()
        self.client.force_login(self.host)
        self.assert_error(self.client.get(self.url), 403, "FORBIDDEN")

    def test_unsupported_methods_return_405(self):
        for method in ("post", "put", "patch", "delete"):
            with self.subTest(method=method):
                response = getattr(self.client, method)(self.url)
                self.assert_error(response, 405, "METHOD_NOT_ALLOWED")
                self.assertEqual(response["Allow"], "GET")

    def test_unknown_party_returns_404_with_shared_message(self):
        response = self.client.get(reverse("party-members", args=[0]))
        error = self.assert_error(response, 404, "NOT_FOUND")
        self.assertEqual(error["message"], "ไม่พบกิจกรรมที่ต้องการ")

    def test_unknown_party_is_404_even_for_non_member(self):
        force_university_login(self.client, self.outsider)
        response = self.client.get(reverse("party-members", args=[0]))
        self.assert_error(response, 404, "NOT_FOUND")

    def test_non_member_gets_403_without_leak(self):
        force_university_login(self.client, self.outsider)
        self.assert_forbidden_without_leak(self.client.get(self.url))

    def test_pending_and_rejected_get_403_without_leak(self):
        for user in (self.pending, self.rejected):
            with self.subTest(user=user.username):
                force_university_login(self.client, user)
                self.assert_forbidden_without_leak(self.client.get(self.url))

    def test_left_member_gets_403_without_leak(self):
        force_university_login(self.client, self.left)
        self.assert_forbidden_without_leak(self.client.get(self.url))

    def test_member_of_another_party_gets_403(self):
        force_university_login(self.client, self.other_member)
        self.assert_forbidden_without_leak(self.client.get(self.url))

    def test_staff_flags_do_not_grant_access(self):
        self.outsider.is_staff = True
        self.outsider.is_superuser = True
        self.outsider.save(update_fields=["is_staff", "is_superuser"])
        force_university_login(self.client, self.outsider)
        self.assert_forbidden_without_leak(self.client.get(self.url))

    def test_query_cannot_change_actor(self):
        force_university_login(self.client, self.outsider)
        response = self.client.get(self.url, {"user_id": self.host.pk, "host_id": self.host.pk})
        self.assert_forbidden_without_leak(response)

    def test_host_and_active_member_can_read(self):
        expected = [self.host.pk, self.no_profile.pk, self.member.pk]
        for user in (self.host, self.member):
            with self.subTest(user=user.username):
                force_university_login(self.client, user)
                self.assert_members(self.client.get(self.url), expected)

    def test_cancelled_party_follows_party_detail_policy(self):
        # party_detail keeps cancelled Parties readable, so history stays visible here too.
        Party.objects.filter(pk=self.party.pk).update(cancelled_at=self.now)
        detail = self.client.get(reverse("party-detail", args=[self.party.pk]))
        self.assertEqual(detail.status_code, 200)
        self.assert_members(
            self.client.get(self.url), [self.host.pk, self.no_profile.pk, self.member.pk]
        )
        force_university_login(self.client, self.outsider)
        self.assert_forbidden_without_leak(self.client.get(self.url))

    def test_forbidden_keys_and_values_do_not_leak(self):
        session_key = self.client.session.session_key
        response = self.client.get(self.url)
        rows = self.assert_members(response, [self.host.pk, self.no_profile.pk, self.member.pk])
        self.assertEqual(rows[2]["display_name"], "นามแฝงสมาชิก")
        body = response.content.decode()
        for user in (self.host, self.member, self.no_profile):
            identities = user.university_identities.values_list("subject", flat=True)
            for secret in (user.username, user.email, user.password, *identities):
                if secret:
                    self.assertNotIn(secret, body)
        for secret in (session_key, "987654", "left_at", "email", "username", "token"):
            self.assertNotIn(secret, body)

    def test_missing_profile_uses_fallback_without_writing(self):
        response = self.client.get(self.url)
        rows = self.assert_members(response, [self.host.pk, self.no_profile.pk, self.member.pk])
        self.assertEqual(rows[1]["display_name"], "ผู้ใช้")
        self.assertNotIn(self.no_profile.username, response.content.decode())
        self.assertFalse(UserProfile.objects.filter(user=self.no_profile).exists())

    def test_host_without_profile_matches_party_detail_fallback(self):
        UserProfile.objects.filter(user=self.host).delete()
        rows = self.client.get(self.url).json()["data"]["members"]
        detail = self.client.get(reverse("party-detail", args=[self.party.pk])).json()["data"]
        self.assertEqual(rows[0]["display_name"], "ผู้จัดกิจกรรม")
        self.assertEqual(rows[0]["display_name"], detail["host"]["display_name"])

    def test_pending_and_rejected_requesters_are_not_listed(self):
        response = self.client.get(self.url)
        rows = self.assert_members(response, [self.host.pk, self.no_profile.pk, self.member.pk])
        listed = {row["user_id"] for row in rows}
        self.assertFalse(listed & {self.pending.pk, self.rejected.pk})
        self.assertNotIn("นามแฝงคนรออนุมัติ", decoded_body(response))
        self.assertNotIn("นามแฝงคนถูกปฏิเสธ", decoded_body(response))

    def test_roles_and_count_match_the_list(self):
        rows = self.assert_members(
            self.client.get(self.url), [self.host.pk, self.no_profile.pk, self.member.pk]
        )
        self.assertEqual([row["role"] for row in rows], ["Host", "Member", "Member"])

    def test_host_first_then_join_time_then_row_id(self):
        # Join order is the reverse of PK order for the two non-Host members.
        PartyMembership.objects.filter(pk=self.member_row.pk).update(
            joined_at=self.now - timedelta(hours=2)
        )
        PartyMembership.objects.filter(party=self.party, user=self.no_profile).update(
            joined_at=self.now - timedelta(hours=1)
        )
        expected = [self.host.pk, self.member.pk, self.no_profile.pk]
        self.assert_members(self.client.get(self.url), expected)
        PartyMembership.objects.filter(party=self.party).update(joined_at=self.now)
        expected = [self.host.pk, self.no_profile.pk, self.member.pk]
        self.assert_members(self.client.get(self.url), expected)

    def test_legacy_party_without_host_row_lists_host_without_writing(self):
        self.host_row.delete()
        rows = self.assert_members(
            self.client.get(self.url), [self.host.pk, self.no_profile.pk, self.member.pk]
        )
        self.assertEqual(rows[0]["role"], "Host")
        self.assertEqual(rows[0]["display_name"], "นามแฝงผู้จัด")
        self.assertFalse(PartyMembership.objects.filter(party=self.party, user=self.host).exists())

    def test_host_with_left_row_stays_listed_once_as_host(self):
        # The Host-leave policy belongs to S2-US4-D-01; the Party still has this Host.
        PartyMembership.objects.filter(pk=self.host_row.pk).update(left_at=self.now)
        rows = self.assert_members(
            self.client.get(self.url), [self.host.pk, self.no_profile.pk, self.member.pk]
        )
        self.assertEqual(rows[0]["role"], "Host")

    def test_it_us6_db_01_lists_only_this_partys_active_memberships(self):
        response = self.client.get(self.url)
        self.assert_members(response, [self.host.pk, self.no_profile.pk, self.member.pk])
        self.assertNotIn("นามแฝงสมาชิกปาร์ตี้อื่น", decoded_body(response))

    def test_it_us6_db_01_query_count_does_not_grow_with_members(self):
        # Viewing as a member also runs can_view_members' membership query.
        force_university_login(self.client, self.member)
        with self.assertNumQueries(6):
            self.assert_members(
                self.client.get(self.url), [self.host.pk, self.no_profile.pk, self.member.pk]
            )
        users = get_user_model()
        for index in range(6):
            user = users.objects.create_user(f"private-extra-login-{index}")
            if index % 2:
                UserProfile.objects.create(user=user, display_name=f"สมาชิกเพิ่ม {index}")
            PartyMembership.objects.create(party=self.party, user=user)
        with self.assertNumQueries(6):
            response = self.client.get(self.url)
        self.assertEqual(response.json()["data"]["member_count"], 9)

    def test_it_us6_db_03_left_member_is_hidden_but_history_is_retained(self):
        response = self.client.get(self.url)
        rows = self.assert_members(response, [self.host.pk, self.no_profile.pk, self.member.pk])
        self.assertNotIn(self.left.pk, {row["user_id"] for row in rows})
        self.assertNotIn("นามแฝงคนถอนตัว", decoded_body(response))
        self.left_row.refresh_from_db()
        self.assertEqual(self.left_row.left_at, self.now)
