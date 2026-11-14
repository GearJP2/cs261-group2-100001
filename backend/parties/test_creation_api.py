import json
from datetime import time, timedelta

from accounts.models import UniversityIdentity, UserProfile
from accounts.test_support import force_university_login
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone
from venues.models import Sport, Venue, VenueOpeningHour, VenueSport

from .models import Party, PartyMembership
from .views import create_party_api


class PartyCreationHandlerTests(TestCase):
    """RequestFactory handler tests; full HTTP integration is tested separately."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="api-host")
        UserProfile.objects.create(user=self.user, display_name="Host")
        self.sport = Sport.objects.create(name="Badminton")
        self.venue = Venue.objects.create(name="Court", location_text="Gym")
        VenueSport.objects.create(venue=self.venue, sport=self.sport)
        VenueOpeningHour.objects.create(
            venue=self.venue,
            weekday=0,
            opens_at=time(9),
            closes_at=time(18),
        )
        self.payload = dict(
            title="Practice",
            sport_id=self.sport.pk,
            venue_id=self.venue.pk,
            starts_at="2030-01-07T09:00:00+07:00",
            ends_at="2030-01-07T10:00:00+07:00",
            capacity=6,
        )
        self.url = "/api/v1/parties"
        self.factory = RequestFactory()

    def request(self, body, content_type="application/json", method="post", query=None):
        if method == "get":
            request = self.factory.get(self.url, data=query or {})
        else:
            request = getattr(self.factory, method)(self.url, data=body, content_type=content_type)
        request.user = self.user
        identity, _ = UniversityIdentity.objects.get_or_create(
            user=request.user,
            provider_key="tu",
            subject=str(request.user.pk),
            defaults={
                "student_verified_at": timezone.now(),
                "eligibility_checked_at": timezone.now(),
            },
        )
        request.session = {"university_identity_id": identity.pk}
        response = create_party_api(request)
        response.json = lambda: json.loads(response.content)
        return response

    def post(self, payload):
        return self.request(json.dumps(payload))

    def test_success_matches_get_contract_and_uses_session_host(self):
        response = self.post(self.payload)
        self.assertEqual(response.status_code, 201)
        data = response.json()["data"]
        self.assertEqual(data["host"], {"id": self.user.pk, "display_name": "Host"})
        self.assertEqual(data["member_count"], 1)
        self.assertEqual(data["remaining_slots"], 5)
        self.assertTrue(data["is_host"])
        self.assertTrue(data["is_member"])
        party = Party.objects.get()
        self.assertEqual(party.description, "")
        self.assertEqual(PartyMembership.objects.get().user_id, self.user.pk)
        force_university_login(self.client, self.user)
        detail = self.client.get(reverse("party-detail", args=[party.pk]))
        self.assertEqual(data, detail.json()["data"])

    def test_bad_payloads_and_readonly_fields_never_write(self):
        for payload in (
            [],
            None,
            {},
            self.payload | {"host_id": self.user.pk},
            self.payload | {"cancelled_at": None},
            self.payload | {"capacity": True},
            self.payload | {"starts_at": "2030-01-07T09:00:00"},
            self.payload | {"starts_at": "2030-02-31T09:00:00+07:00"},
            self.payload | {"starts_at": 123},
            self.payload | {"title": " "},
            self.payload | {"description": None},
        ):
            with self.subTest(payload=payload):
                self.assertEqual(self.post(payload).status_code, 400)
        for body, content_type in (("{", "application/json"), ("x", "text/plain")):
            self.assertEqual(
                self.request(body, content_type).status_code,
                400,
            )
        self.assertFalse(Party.objects.exists())

    def test_schedule_and_missing_venue_errors(self):
        response = self.post(self.payload | {"ends_at": "2030-01-07T19:00:00+07:00"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "VENUE_CLOSED")
        self.assertEqual(self.post(self.payload | {"venue_id": 999999}).status_code, 404)
        self.assertFalse(Party.objects.exists())

    def test_list_only_returns_open_parties_with_the_existing_detail_contract(self):
        created = self.post(self.payload).json()["data"]
        response = self.request({}, method="get")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"data": [created]})

    def test_search_filters_before_pagination_includes_matches_after_first_50(self):
        start = timezone.now() + timedelta(days=2)
        Party.objects.bulk_create(
            [
                Party(
                    host=self.user,
                    sport=self.sport,
                    venue=self.venue,
                    title="Ordinary party",
                    starts_at=start + timedelta(minutes=index),
                    ends_at=start + timedelta(minutes=index, hours=1),
                    capacity=2,
                )
                for index in range(50)
            ]
            + [
                Party(
                    host=self.user,
                    sport=self.sport,
                    venue=self.venue,
                    title="Needle after first fifty",
                    starts_at=start + timedelta(minutes=50),
                    ends_at=start + timedelta(minutes=50, hours=1),
                    capacity=2,
                )
            ]
        )

        response = self.request(
            {},
            method="get",
            query={"q": "Needle", "page": "1", "page_size": "1"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["data"][0]["title"],
            "Needle after first fifty",
        )
        self.assertEqual(
            {key: response.json()[key] for key in ("page", "page_size", "total")},
            {"page": 1, "page_size": 1, "total": 1},
        )

    def test_search_paginates_filtered_results_and_returns_total(self):
        start = timezone.now() + timedelta(days=2)
        Party.objects.bulk_create(
            [
                Party(
                    host=self.user,
                    sport=self.sport,
                    venue=self.venue,
                    title=f"Search result {index}",
                    starts_at=start + timedelta(minutes=index),
                    ends_at=start + timedelta(minutes=index, hours=1),
                    capacity=2,
                )
                for index in range(3)
            ]
        )

        response = self.request(
            {},
            method="get",
            query={"q": "Search result", "page": "2", "page_size": "2"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 3)
        self.assertEqual(response.json()["page"], 2)
        self.assertEqual(response.json()["page_size"], 2)
        self.assertEqual(
            [party["title"] for party in response.json()["data"]],
            ["Search result 2"],
        )

    def test_search_rejects_invalid_pagination(self):
        response = self.request(
            {},
            method="get",
            query={"page": "0", "page_size": "101"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "INVALID_INPUT")

    def test_wrong_method_is_json_405(self):
        response = self.request({}, method="put")
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response["Allow"], "GET, POST")
        self.assertEqual(response.json()["error"]["code"], "METHOD_NOT_ALLOWED")
