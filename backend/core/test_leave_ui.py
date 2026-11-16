from datetime import timedelta

from accounts.test_support import force_university_login
from django.test import Client, TestCase
from django.urls import reverse
from parties.models import JoinRequest, PartyMembership
from parties.test_join_requests import JoinRequestFixture

from .templatetags.leave_ui import joined_parties


class JoinedPartyUITests(JoinRequestFixture, TestCase):
    def test_host_created_party_links_to_detail(self):
        force_university_login(self.client, self.host)

        response = self.client.get(reverse("my-parties-page"))

        self.assertContains(
            response,
            f'href="{reverse("party-detail-page", args=[self.party.pk])}">ดูรายละเอียด</a>',
        )

    def test_pending_user_sees_real_party_with_disabled_leave(self):
        JoinRequest.objects.create(party=self.party, user=self.applicant)
        self.assertEqual(joined_parties(self.other)["joined"], [])
        result = joined_parties(self.applicant)["joined"]
        self.assertEqual([p.pk for p in result], [self.party.pk])
        self.assertIn("รออนุมัติ", result[0].ui_leave_reason)
        force_university_login(self.client, self.applicant)
        response = self.client.get(reverse("my-parties-page"))
        self.assertContains(response, f'data-leave-party="{self.party.pk}" disabled')
        self.assertContains(
            response,
            f'href="{reverse("party-detail-page", args=[self.party.pk])}">ดูรายละเอียด</a>',
        )

    def test_active_member_can_open_party_detail_from_joined_card(self):
        PartyMembership.objects.create(party=self.party, user=self.applicant)
        force_university_login(self.client, self.applicant)

        response = self.client.get(reverse("my-parties-page"))

        self.assertContains(
            response,
            f'href="{reverse("party-detail-page", args=[self.party.pk])}">ดูรายละเอียด</a>',
        )

    def test_active_member_can_leave_and_restricted_states_cannot(self):
        PartyMembership.objects.create(party=self.party, user=self.applicant)
        self.assertEqual(joined_parties(self.applicant)["joined"][0].ui_leave_reason, "")
        self.assertIn("ผู้จัด", joined_parties(self.host)["joined"][0].ui_leave_reason)
        self.party.starts_at = self.now - timedelta(seconds=1)
        self.party.save()
        self.assertIn("เริ่มหรือจบ", joined_parties(self.applicant)["joined"][0].ui_leave_reason)
        self.party.cancelled_at = self.now
        self.party.save()
        self.assertIn("ยกเลิก", joined_parties(self.applicant)["joined"][0].ui_leave_reason)

    def test_real_leave_updates_membership_detail_and_joined_page(self):
        member = PartyMembership.objects.create(party=self.party, user=self.applicant)
        client = Client(enforce_csrf_checks=True)
        force_university_login(client, self.applicant)
        token = client.get(reverse("accounts:csrf")).json()["data"]["csrf_token"]
        response = client.post(
            reverse("party-leave", args=[self.party.pk]),
            {},
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 200)
        member.refresh_from_db()
        self.assertIsNotNone(member.left_at)
        self.assertEqual(joined_parties(self.applicant)["joined"], [])
        detail = client.get(reverse("party-detail", args=[self.party.pk])).json()["data"]
        self.assertEqual((detail["member_count"], detail["remaining_slots"]), (1, 1))
        response = client.get(reverse("my-parties-page"))
        self.assertNotContains(response, f'data-joined-party="{self.party.pk}"')

    def test_history_and_private_data_are_not_fabricated(self):
        PartyMembership.objects.create(party=self.party, user=self.applicant)
        force_university_login(self.client, self.applicant)
        response = self.client.get(reverse("my-parties-page"))
        self.assertContains(response, 'data-myparty-tab="history"')
        self.assertNotContains(response, "mockLeavePartyRequest")
        self.assertContains(response, self.party.title)
