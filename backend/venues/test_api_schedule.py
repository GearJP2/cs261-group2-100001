from datetime import datetime, time

from accounts.models import UniversityIdentity
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from .models import Sport, Venue, VenueOpeningHour, VenueSport
from .services import ScheduleValidationError, validate_party_schedule


class VenueApiScheduleTests(TestCase):
    def setUp(self):
        self.sport = Sport.objects.create(name="Badminton")
        self.other = Sport.objects.create(name="Football")
        self.venue = Venue.objects.create(name="Court", location_text="เวลา: MOCK")
        VenueSport.objects.create(venue=self.venue, sport=self.sport)
        for opens, closes in ((9, 12), (13, 18)):
            VenueOpeningHour.objects.create(
                venue=self.venue, weekday=0, opens_at=time(opens), closes_at=time(closes)
            )
        self.user = get_user_model().objects.create_user("venue-reader")
        self.client.force_login(self.user)
        identity = UniversityIdentity.objects.create(
            user=self.user,
            provider_key="tu",
            subject="venue-reader",
            student_verified_at=timezone.now(),
            eligibility_checked_at=timezone.now(),
        )
        session = self.client.session
        session["university_identity_id"] = identity.pk
        session.save()

    def validate(
        self, start="2026-10-19T09:00:00+07:00", end="2026-10-19T12:00:00+07:00", **kwargs
    ):
        return validate_party_schedule(
            kwargs.get("sport_id", self.sport.pk),
            kwargs.get("venue_id", self.venue.pk),
            datetime.fromisoformat(start),
            datetime.fromisoformat(end),
        )

    def test_api_contract_filter_pagination_and_hours(self):
        inactive = Venue.objects.create(name="Hidden", location_text="", is_active=False)
        VenueSport.objects.create(venue=inactive, sport=self.sport)
        self.assertEqual(
            self.client.get("/api/v1/sports").json()["data"],
            [
                {"id": self.sport.pk, "name": "Badminton"},
                {"id": self.other.pk, "name": "Football"},
            ],
        )
        url = f"/api/v1/venues?sport_id={self.sport.pk}&page_size=1"
        self.assertEqual(
            self.client.get(url).json(),
            {
                "data": [
                    {
                        "id": self.venue.pk,
                        "name": "Court",
                        "location_text": "เวลา: MOCK",
                        "venue_type": None,
                    }
                ],
                "page": 1,
                "page_size": 1,
                "total": 1,
            },
        )
        self.venue.venue_type = Venue.Type.INDOOR
        self.venue.save(update_fields=["venue_type"])
        self.assertEqual(self.client.get(url).json()["data"][0]["venue_type"], "Indoor")
        self.assertEqual(self.client.get(url + "&page=2").json()["data"], [])
        self.assertEqual(
            self.client.get(f"/api/v1/venues?sport_id={self.other.pk}").json()["total"], 0
        )
        response = self.client.get(f"/api/v1/venues/{self.venue.pk}/opening-hours")
        self.assertEqual(
            response.json()["data"],
            {
                "venue_id": self.venue.pk,
                "timezone": "Asia/Bangkok",
                "intervals": [
                    {"weekday": 0, "opens_at": "09:00:00", "closes_at": "12:00:00"},
                    {"weekday": 0, "opens_at": "13:00:00", "closes_at": "18:00:00"},
                ],
            },
        )
        self.assertIn("no-store", response["Cache-Control"])
        for venue_id in (inactive.pk, 999999999999999999999999):
            self.assertEqual(
                self.client.get(f"/api/v1/venues/{venue_id}/opening-hours").status_code, 404
            )

    def test_query_validation(self):
        for query in (
            "",
            "sport_id=0",
            "sport_id=-1",
            "sport_id=x",
            "sport_id=1&sport_id=2",
            "sport_id=1&page=0",
            "sport_id=1&page_size=101",
            "sport_id=1&page=1.5",
            "sport_id=" + "9" * 100,
        ):
            with self.subTest(query=query):
                self.assertEqual(self.client.get("/api/v1/venues?" + query).status_code, 400)

    def test_access_and_methods(self):
        urls = [
            "/api/v1/sports",
            f"/api/v1/venues?sport_id={self.sport.pk}",
            f"/api/v1/venues/{self.venue.pk}/opening-hours",
        ]
        for url in urls:
            self.assertEqual(self.client.post(url)["Allow"], "GET")
        session = self.client.session
        del session["university_identity_id"]
        session.save()
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 403)
        self.client.logout()
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 401)

    def test_boundaries_and_timezone_conversion(self):
        self.assertIsNone(self.validate())
        self.assertIsNone(self.validate("2026-10-19T02:00:00Z", "2026-10-19T05:00:00Z"))
        self.assertIsNone(self.validate("2026-10-18T23:00:00-03:00", "2026-10-19T02:00:00-03:00"))

    def test_invalid_ranges_and_closed_intervals(self):
        cases = [
            ("2026-10-19T09:00:00", "2026-10-19T10:00:00", "INVALID_TIME_RANGE"),
            ("2026-10-19T10:00:00+07:00", "2026-10-19T09:00:00+07:00", "INVALID_TIME_RANGE"),
            ("2026-10-19T09:00:00+07:00", "2026-10-19T09:00:00+07:00", "INVALID_TIME_RANGE"),
            ("2026-10-19T17:00:00+07:00", "2026-10-20T09:00:00+07:00", "INVALID_TIME_RANGE"),
            ("2026-10-20T09:00:00+07:00", "2026-10-20T10:00:00+07:00", "VENUE_CLOSED"),
            ("2026-10-19T08:59:59+07:00", "2026-10-19T10:00:00+07:00", "VENUE_CLOSED"),
            ("2026-10-19T17:00:00+07:00", "2026-10-19T18:00:00.000001+07:00", "VENUE_CLOSED"),
            ("2026-10-19T11:00:00+07:00", "2026-10-19T14:00:00+07:00", "VENUE_CLOSED"),
        ]
        for start, end, code in cases:
            with (
                self.subTest(start=start, end=end),
                self.assertRaises(ScheduleValidationError) as ctx,
            ):
                self.validate(start, end)
            self.assertEqual(ctx.exception.code, code)

    def test_mapping_active_venue_and_input_types(self):
        for kwargs, code in (
            ({"sport_id": self.other.pk}, "INVALID_INPUT"),
            ({"sport_id": True}, "INVALID_INPUT"),
            ({"venue_id": "1"}, "INVALID_INPUT"),
            ({"venue_id": 999999}, "NOT_FOUND"),
        ):
            with self.assertRaises(ScheduleValidationError) as ctx:
                self.validate(**kwargs)
            self.assertEqual(ctx.exception.code, code)
        self.venue.is_active = False
        self.venue.save()
        with self.assertRaises(ScheduleValidationError) as ctx:
            self.validate()
        self.assertEqual(ctx.exception.status, 404)

    def test_overlapping_configuration_is_rejected(self):
        VenueOpeningHour.objects.create(
            venue=self.venue, weekday=0, opens_at=time(11), closes_at=time(14)
        )
        with self.assertRaises(ScheduleValidationError) as ctx:
            self.validate()
        self.assertEqual(ctx.exception.code, "INVALID_OPENING_HOURS")

    def test_adjacent_intervals_cannot_be_combined(self):
        self.venue.opening_hours.filter(opens_at=time(13)).update(opens_at=time(12))
        with self.assertRaises(ScheduleValidationError) as ctx:
            self.validate("2026-10-19T11:00:00+07:00", "2026-10-19T14:00:00+07:00")
        self.assertEqual(ctx.exception.code, "VENUE_CLOSED")

    def test_empty_hours_and_missing_sport(self):
        self.venue.opening_hours.all().delete()
        self.assertEqual(
            self.client.get(f"/api/v1/venues/{self.venue.pk}/opening-hours").json()["data"][
                "intervals"
            ],
            [],
        )
        with self.assertRaises(ScheduleValidationError) as ctx:
            self.validate()
        self.assertEqual(ctx.exception.code, "VENUE_CLOSED")
        with self.assertRaises(ScheduleValidationError) as ctx:
            self.validate(sport_id=999999)
        self.assertEqual(ctx.exception.code, "INVALID_INPUT")
