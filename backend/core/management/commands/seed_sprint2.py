"""Isolated Sprint 2 fixtures; reuse the existing seed's collision and reset rules."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import CommandError
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from parties.models import JoinRequest, Party, PartyMembership
from venues.models import Sport, Venue, VenueOpeningHour, VenueSport

from .seed_demo import Command as DemoCommand

PREFIX = "[S2-DATA]"
MARKER = "Synthetic S2-DATA fixture; rerunning seed_sprint2 resets this party."


class Command(DemoCommand):
    help = "Reset synthetic Sprint 2 fixtures on a test database (DEBUG=true only)."
    prefix = PREFIX
    marker = MARKER
    username_prefix = "s2data"
    roles = (*DemoCommand.roles, "left")

    def add_arguments(self, parser):
        parser.add_argument(
            "--at", help="Aware ISO datetime for reproducible fixture times; default: now."
        )
        parser.add_argument(
            "--confirm-test-data", action="store_true", help="Confirm this is a disposable test DB."
        )

    def handle(self, *args, **options):
        if not options["confirm_test_data"]:
            raise CommandError("Confirm the test database with --confirm-test-data.")
        raw = options.get("at")
        try:
            self.reference = parse_datetime(raw) if raw else timezone.now()
        except ValueError:
            self.reference = None
        if self.reference is None or timezone.is_naive(self.reference):
            raise CommandError("--at must be an ISO datetime with a timezone offset.")
        super().handle(*args, **options)

    def seed(self):
        super().seed(now=self.reference)
        users = {
            role: get_user_model().objects.get(username=f"s2data_{role}") for role in self.roles
        }
        # Keep historical membership without counting the departed user as active.
        for party in Party.objects.filter(description=MARKER, host=users["h"]):
            joined = min(self.reference, party.starts_at) - timedelta(hours=3)
            left = joined + timedelta(hours=1)
            membership = PartyMembership.objects.create(
                party=party, user=users["left"], left_at=left
            )
            PartyMembership.objects.filter(pk=membership.pk).update(joined_at=joined)
            request = JoinRequest.objects.create(
                party=party,
                user=users["left"],
                status=JoinRequest.Status.APPROVED,
                decided_at=joined,
                decided_by=users["h"],
            )
            JoinRequest.objects.filter(pk=request.pk).update(created_at=joined - timedelta(hours=1))

        # A second sport/venue combination supports AND-filter and negative-match cases.
        tennis, _ = Sport.objects.get_or_create(name=f"{PREFIX} Tennis")
        party = Party.objects.get(title=f"{PREFIX} Last slot", description=MARKER)
        venue = party.venue
        alternate, created = Venue.objects.get_or_create(
            name=f"{PREFIX} Alternate venue",
            defaults={"location_text": MARKER, "is_active": True},
        )
        if not created and alternate.location_text != MARKER:
            raise CommandError("Reserved demo venue collision: Alternate venue")
        alternate.is_active = True
        alternate.save(update_fields=["is_active"])
        alternate.opening_hours.all().delete()
        VenueOpeningHour.objects.bulk_create(
            [
                VenueOpeningHour(
                    venue=alternate,
                    weekday=hour.weekday,
                    opens_at=hour.opens_at,
                    closes_at=hour.closes_at,
                )
                for hour in venue.opening_hours.all()
            ]
        )
        VenueSport.objects.get_or_create(venue=alternate, sport=tennis)
        party.venue = alternate
        party.sport = tennis
        party.save(update_fields=["sport", "venue"])
        self.stdout.write(
            self.style.SUCCESS(
                f"S2-DATA ready at {self.reference.isoformat()}: 7 users, 2 sports, "
                "4 venues, 6 parties; 2 active + 1 left per party. "
                "Indoor/outdoor and US14 review data are deferred pending schema/policy."
            )
        )
