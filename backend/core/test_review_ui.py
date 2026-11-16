from datetime import timedelta

from accounts.test_support import force_university_login
from conduct.models import PartyReview
from conduct.services import submit_review
from conduct.test_reviews import ReviewFixture
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .templatetags.review_ui import review_history


class ReviewHistoryUITests(ReviewFixture, TestCase):
    def test_history_uses_eligible_completed_parties_only(self):
        self.assertEqual([p.pk for p in review_history(self.member)["history"]], [self.party.pk])
        self.assertEqual(review_history(self.outsider)["history"], [])
        self.party.memberships.filter(user=self.member).update(
            left_at=self.party.ends_at - timedelta(microseconds=1)
        )
        self.assertEqual(review_history(self.member)["history"], [])
        self.party.memberships.filter(user=self.member).update(left_at=self.party.ends_at)
        self.assertEqual(len(review_history(self.member)["history"]), 1)
        self.party.cancelled_at = timezone.now()
        self.party.save()
        self.assertEqual(review_history(self.member)["history"], [])

    def test_reviewed_status_is_scoped_to_reviewer_and_party(self):
        submit_review(
            party_id=self.party.pk,
            reviewer=self.host,
            reviewee_id=self.member.pk,
            rating=4,
            comment="ดี",
        )
        target = next(
            t
            for t in review_history(self.host)["history"][0].review_targets
            if t["id"] == self.member.pk
        )
        self.assertTrue(target["reviewed"])
        target = next(
            t
            for t in review_history(self.peer)["history"][0].review_targets
            if t["id"] == self.member.pk
        )
        self.assertFalse(target["reviewed"])
        second = self.make_party()
        self.complete(second)
        target = next(
            t
            for p in review_history(self.host)["history"]
            if p.pk == second.pk
            for t in p.review_targets
            if t["id"] == self.member.pk
        )
        self.assertFalse(target["reviewed"])

    def test_page_escapes_names_and_includes_real_ids(self):
        self.member.profile.display_name = '<img src=x onerror="alert(1)">'
        self.member.profile.save()
        force_university_login(self.client, self.host)
        response = self.client.get(reverse("my-parties-page"))
        self.assertContains(response, f'data-party-id="{self.party.pk}"')
        self.assertContains(response, "&lt;img src=x onerror=")
        self.assertNotContains(response, "<img src=x onerror=")
        targets = review_history(self.host)["history"][0].review_targets
        self.assertNotIn(self.host.pk, [t["id"] for t in targets])

    def test_real_submission_then_reload_marks_only_saved_review(self):
        client = Client(enforce_csrf_checks=True)
        force_university_login(client, self.host)
        token = client.get(reverse("accounts:csrf")).json()["data"]["csrf_token"]
        payload = self.payload(self.member, rating=5)
        response = client.post(
            self.url(), payload, content_type="application/json", HTTP_X_CSRFTOKEN=token
        )
        self.assertEqual(response.status_code, 201)
        target = next(
            t
            for t in review_history(self.host)["history"][0].review_targets
            if t["id"] == self.member.pk
        )
        self.assertTrue(target["reviewed"])
        self.assertEqual(PartyReview.objects.filter(reviewer=self.host).count(), 1)
