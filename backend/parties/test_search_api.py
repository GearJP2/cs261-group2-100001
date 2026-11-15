"""Task79 HTTP/session and pagination integration tests on PostgreSQL."""

from datetime import timedelta
from unittest.mock import patch

from accounts.test_support import force_university_login
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from venues.models import Venue

from .models import Party, PartyMembership
from .test_join_requests import JoinRequestFixture


class SearchAPITests(JoinRequestFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.url = reverse("party-create")
        self.client = Client(enforce_csrf_checks=True)
        force_university_login(self.client, self.applicant)
        self.party.venue.venue_type = Venue.Type.INDOOR
        self.party.venue.save(update_fields=["venue_type"])

    def test_defaults_allowlist_and_detail_shape_without_csrf(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])
        payload = response.json()
        self.assertEqual(set(payload), {"data", "page", "page_size", "total"})
        self.assertEqual((payload["page"], payload["page_size"], payload["total"]), (1, 20, 1))
        detail = self.client.get(reverse("party-detail", args=[self.party.pk])).json()["data"]
        self.assertEqual(payload["data"], [detail])
        self.assertEqual(
            set(detail),
            {
                "id",
                "title",
                "description",
                "host",
                "sport_id",
                "venue_id",
                "starts_at",
                "ends_at",
                "capacity",
                "member_count",
                "remaining_slots",
                "state",
                "is_host",
                "is_member",
            },
        )
        self.assertEqual(detail["host"], {"id": self.host.pk, "display_name": "ผู้จัดกิจกรรม"})

    def test_http_combined_filters_and_state_do_not_mutate(self):
        before = list(PartyMembership.objects.values())
        filters = {
            "q": "after",
            "sport_id": self.party.sport_id,
            "venue_id": self.party.venue_id,
            "venue_type": "Indoor",
            "starts_from": self.party.starts_at.isoformat(),
            "starts_to": self.party.ends_at.isoformat(),
        }
        response = self.client.get(self.url, filters)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([p["id"] for p in response.json()["data"]], [self.party.pk])
        filters["venue_type"] = "Outdoor"
        self.assertEqual(self.client.get(self.url, filters).json()["total"], 0)
        self.assertEqual(list(PartyMembership.objects.values()), before)
        PartyMembership.objects.create(party=self.party, user=self.other)
        self.assertEqual(self.client.get(self.url).json()["data"], [])
        full = self.client.get(self.url, {"state": "Full"}).json()
        self.assertEqual(full["total"], 1)
        self.assertEqual(full["data"][0]["state"], "Full")

    def test_pagination_total_tie_order_and_out_of_range(self):
        parties = Party.objects.bulk_create(
            [
                Party(
                    host=self.host,
                    sport=self.party.sport,
                    venue=self.party.venue,
                    title=f"Party {i}",
                    starts_at=self.party.starts_at,
                    ends_at=self.party.ends_at,
                    capacity=2,
                )
                for i in range(24)
            ]
        )
        PartyMembership.objects.bulk_create(
            [PartyMembership(party=party, user=self.host) for party in parties]
        )
        expected = [self.party.pk] + [party.pk for party in parties]
        self.assertEqual(len(self.client.get(self.url).json()["data"]), 20)
        observed = []
        for page in [1, 2, 3]:
            payload = self.client.get(self.url, {"page": page, "page_size": 10}).json()
            self.assertEqual(
                (payload["page"], payload["page_size"], payload["total"]), (page, 10, 25)
            )
            observed.extend(p["id"] for p in payload["data"])
        self.assertEqual(observed, expected)
        for page in [4, 10**40]:
            payload = self.client.get(self.url, {"page": str(page), "page_size": 10}).json()
            self.assertEqual(payload, {"data": [], "page": page, "page_size": 10, "total": 25})

    def test_invalid_queries_are_errors_not_empty_results(self):
        for raw, field in [
            ("page=0", "page"),
            ("page_size=101", "page_size"),
            ("sport_id=x", "sport_id"),
            ("venue_type=indoor", "venue_type"),
            ("state=open", "state"),
            ("unexpected=x", "unexpected"),
            ("q=a&q=b", "q"),
            ("q=%00", "q"),
            ("starts_from=2030-01-01", "starts_from"),
        ]:
            with self.subTest(raw=raw):
                response = self.client.get(f"{self.url}?{raw}")
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()["error"]["code"], "INVALID_INPUT")
                self.assertIn(field, response.json()["error"]["fields"])
                self.assertIn("no-store", response["Cache-Control"])

    def test_guard_runs_before_query_validation(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url, {"page": "bad"}).status_code, 401)
        self.client.force_login(self.applicant)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_unknown_ids_return_empty_even_outside_database_integer_range(self):
        for field in ["sport_id", "venue_id"]:
            response = self.client.get(self.url, {field: str(10**40)})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["data"], [])

    def test_state_filter_and_serialization_share_one_now(self):
        boundary = self.party.starts_at
        # A second clock read would cross the start and report a different state.
        with patch(
            "parties.views.timezone",
            wraps=timezone,
        ) as clock:
            clock.now.side_effect = [boundary - timedelta(microseconds=1), boundary]
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"][0]["state"], "Open")
        self.assertEqual(clock.now.call_count, 1)
