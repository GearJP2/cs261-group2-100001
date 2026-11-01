from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
from zoneinfo import ZoneInfo

from accounts.models import UniversityIdentity
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import TestCase, override_settings
from parties.models import Party, PartyMembership
from parties.services import get_party_state
from venues.models import Venue

from .management.commands.seed_sprint2 import MARKER, PREFIX


@override_settings(DEBUG=True)
class SeedSprint2Tests(TestCase):
    reference = datetime(2026, 11, 2, 8, tzinfo=timezone.utc)

    def seed(self, **kwargs):
        call_command(
            "seed_sprint2",
            confirm_test_data=True,
            at=self.reference.isoformat(),
            stdout=StringIO(),
            **kwargs,
        )

    def party(self, key):
        return Party.objects.get(title=f"{PREFIX} {key}")

    def test_fixture_roles_states_and_search_combinations(self):
        self.seed()
        self.assertEqual(get_user_model().objects.count(), 7)
        self.assertEqual(UniversityIdentity.objects.count(), 0)
        self.assertEqual(Venue.objects.count(), 4)
        self.assertEqual(Party.objects.count(), 6)
        self.assertEqual(
            set(Party.objects.values_list("sport__name", flat=True)),
            {f"{PREFIX} Badminton", f"{PREFIX} Tennis"},
        )
        for name, state in (
            ("Open", "Open"),
            ("Last slot", "Open"),
            ("Full", "Full"),
            ("InProgress", "InProgress"),
            ("Completed", "Completed"),
            ("Cancelled", "Cancelled"),
        ):
            party = self.party(name)
            self.assertEqual(get_party_state(party, now=self.reference), state)
            self.assertEqual(party.memberships.filter(left_at__isnull=True).count(), 2)
            self.assertEqual(party.memberships.filter(left_at__isnull=False).count(), 1)
            history = party.memberships.get(user__username="s2data_left")
            self.assertLess(history.joined_at, history.left_at)
            self.assertTrue(
                party.join_requests.filter(user=history.user, status="Approved").exists()
            )
        self.assertEqual(self.party("Last slot").join_requests.filter(status="Pending").count(), 2)
        self.assertEqual(self.party("Open").join_requests.filter(status="Rejected").count(), 1)
        self.assertFalse(PartyMembership.objects.filter(user__username="s2data_x").exists())
        self.assertFalse(Venue.objects.get(name=f"{PREFIX} Closed venue").opening_hours.exists())
        for user in get_user_model().objects.all():
            self.assertFalse(user.has_usable_password())
            self.assertFalse(user.is_staff or user.is_superuser)

    def test_rerun_resets_only_its_fixtures_and_preserves_stable_ids(self):
        call_command("seed_demo", stdout=StringIO())
        base_ids = list(
            Party.objects.filter(title__startswith="[BASE-03]").values_list("id", flat=True)
        )
        self.seed()
        ids = dict(Party.objects.filter(description=MARKER).values_list("title", "id"))
        venue_ids = list(Venue.objects.order_by("id").values_list("id", flat=True))
        party = self.party("Last slot")
        party.memberships.filter(user__username="s2data_m").update(left_at=self.reference)
        party.join_requests.filter(user__username="s2data_a").update(
            status="Rejected", decided_at=self.reference, decided_by=party.host
        )
        self.seed()
        self.assertEqual(
            dict(Party.objects.filter(description=MARKER).values_list("title", "id")), ids
        )
        self.assertEqual(list(Venue.objects.order_by("id").values_list("id", flat=True)), venue_ids)
        self.assertEqual(
            list(Party.objects.filter(title__startswith="[BASE-03]").values_list("id", flat=True)),
            base_ids,
        )
        self.assertEqual(party.memberships.filter(left_at__isnull=True).count(), 2)
        self.assertEqual(party.join_requests.filter(status="Pending").count(), 2)
        self.assertEqual(party.memberships.count(), 3)

    def test_search_time_boundaries_are_reproducible(self):
        self.seed()
        party = self.party("Open")
        bangkok = party.starts_at.astimezone(ZoneInfo("Asia/Bangkok"))
        self.assertEqual(bangkok.hour, 10)
        self.assertEqual(bangkok.utcoffset(), timedelta(hours=7))
        for point, expected in (
            (party.starts_at - timedelta(microseconds=1), "Open"),
            (party.starts_at, "InProgress"),
            (party.ends_at, "Completed"),
        ):
            self.assertEqual(get_party_state(party, now=point), expected)

    def test_requires_confirmation_and_aware_timestamp(self):
        for options in (
            {},
            {"confirm_test_data": True, "at": "2026-11-02T10:00:00"},
            {"confirm_test_data": True, "at": "invalid"},
        ):
            with self.assertRaises(CommandError):
                call_command("seed_sprint2", stdout=StringIO(), **options)
        self.assertFalse(Party.objects.exists())

    @override_settings(DEBUG=False)
    def test_refuses_non_debug_database(self):
        with self.assertRaisesMessage(CommandError, "DEBUG=true"):
            self.seed()

    def test_late_collision_rolls_back_all_changes(self):
        Venue.objects.create(name=f"{PREFIX} Alternate venue", location_text="not seed owned")
        with self.assertRaisesMessage(CommandError, "collision"):
            self.seed()
        self.assertEqual(Venue.objects.count(), 1)
        self.assertFalse(Party.objects.exists())
        self.assertFalse(get_user_model().objects.exists())

    def test_postgres_snapshot_matches_expected_counts_without_join_multiplication(self):
        if connection.vendor != "postgresql":
            self.skipTest("Snapshot uses PostgreSQL FILTER/timezone syntax")
        self.seed()
        sql = Path(__file__).resolve().parents[2] / "database/seeds/sprint2_snapshot.sql"
        with connection.cursor() as cursor:
            cursor.execute(sql.read_text(encoding="utf-8"))
            rows = cursor.fetchall()
        self.assertEqual(len(rows), 6)
        for row in rows:
            self.assertEqual(row[8:10], (2, 1))
            self.assertEqual(row[12], 2)  # Active M and historical left both approved.
        last = next(row for row in rows if row[1] == f"{PREFIX} Last slot")
        self.assertEqual(last[10:14], (1, 2, 2, 0))
