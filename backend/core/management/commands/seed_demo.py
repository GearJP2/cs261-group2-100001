"""Repeatable, synthetic BASE-03 data for the local development database."""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from accounts.models import UserProfile, UserSportInterest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from parties.models import JoinRequest, Party, PartyMembership
from venues.models import Sport, Venue, VenueOpeningHour, VenueSport

PREFIX = "[BASE-03]"
MARKER = "Synthetic BASE-03 fixture; rerunning seed_demo resets this party."
ROLES = ("h", "a", "b", "m", "x", "inactive")


class Command(BaseCommand):
    help = "Create/reset BASE-03 demo data (DEBUG=true only; no real student identities)."
    prefix = PREFIX
    marker = MARKER
    username_prefix = "base03"
    roles = ROLES

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("seed_demo requires DEBUG=true and a local development database.")
        with transaction.atomic():
            self.seed()

    def seed(self, now=None):
        now = now or timezone.now()
        local = now.astimezone(ZoneInfo("Asia/Bangkok"))
        tomorrow = local.date() + timedelta(days=1)
        future = datetime.combine(tomorrow, time(10), tzinfo=local.tzinfo)
        users = {}
        for role in self.roles:
            username = f"{self.username_prefix}_{role}"
            user, created = get_user_model().objects.get_or_create(username=username)
            # Refuse to take over an existing account that was not created by this command.
            email = f"{username}@example.invalid"
            if not created and (user.email != email or user.is_staff or user.is_superuser):
                raise CommandError(f"Reserved demo username collision: {user.username}")
            user.email = email
            user.is_active = role != "inactive"
            user.set_unusable_password()
            user.save()
            UserProfile.objects.update_or_create(
                user=user,
                defaults={
                    "display_name": f"{self.prefix.strip('[]')} {role.upper()}",
                    "credit_score": None,
                },
            )
            users[role] = user

        sport, _ = Sport.objects.get_or_create(name=f"{self.prefix} Badminton")
        for role in ("h", "a", "b", "m"):
            UserSportInterest.objects.get_or_create(user=users[role], sport=sport)

        venues = {}
        for key, active in (("Open", True), ("Closed", True), ("Inactive", False)):
            name = f"{self.prefix} {key} venue"
            venue, created = Venue.objects.get_or_create(
                name=name,
                defaults={"location_text": self.marker, "is_active": active},
            )
            if not created and venue.location_text != self.marker:
                raise CommandError(f"Reserved demo venue collision: {name}")
            venue.is_active = active
            venue.save(update_fields=["is_active"])
            VenueSport.objects.get_or_create(venue=venue, sport=sport)
            venue.opening_hours.all().delete()
            if key != "Closed":
                VenueOpeningHour.objects.bulk_create(
                    [
                        VenueOpeningHour(
                            venue=venue, weekday=day, opens_at=time.min, closes_at=time.max
                        )
                        for day in range(7)
                    ]
                )
            venues[key] = venue

        scenarios = [
            ("Open", future, future + timedelta(hours=1), 4, None),
            ("Last slot", future, future + timedelta(hours=1), 3, None),
            ("Full", future, future + timedelta(hours=1), 2, None),
            (
                "InProgress",
                datetime.combine(local.date(), time.min, tzinfo=local.tzinfo),
                datetime.combine(local.date(), time.max, tzinfo=local.tzinfo),
                4,
                None,
            ),
            (
                "Completed",
                future - timedelta(days=2),
                future - timedelta(days=2) + timedelta(hours=1),
                4,
                None,
            ),
            ("Cancelled", future, future + timedelta(hours=1), 4, now),
        ]
        for key, start, end, capacity, cancelled in scenarios:
            title = f"{self.prefix} {key}"
            party = Party.objects.filter(title=title).first()
            if party and (party.description != self.marker or party.host_id != users["h"].pk):
                raise CommandError(f"Reserved demo party collision: {title}")
            party, _ = Party.objects.update_or_create(
                title=title,
                defaults={
                    "host": users["h"],
                    "sport": sport,
                    "venue": venues["Open"],
                    "description": self.marker,
                    "starts_at": start,
                    "ends_at": end,
                    "capacity": capacity,
                    "cancelled_at": cancelled,
                },
            )
            # Reset only the six explicitly named demo Parties, including test interactions.
            party.join_requests.all().delete()
            party.memberships.all().delete()
            joined = min(now, start) - timedelta(hours=1)
            for role in ("h", "m"):
                membership = PartyMembership.objects.create(party=party, user=users[role])
                PartyMembership.objects.filter(pk=membership.pk).update(joined_at=joined)
            request_time = min(now, start) - timedelta(hours=2)
            approved = JoinRequest.objects.create(
                party=party,
                user=users["m"],
                status=JoinRequest.Status.APPROVED,
                decided_at=joined,
                decided_by=users["h"],
            )
            JoinRequest.objects.filter(pk=approved.pk).update(created_at=request_time)
            if key == "Last slot":
                for role in ("a", "b"):
                    JoinRequest.objects.create(party=party, user=users[role])
            elif key == "Open":
                JoinRequest.objects.create(party=party, user=users["a"])
                rejected = JoinRequest.objects.create(
                    party=party,
                    user=users["b"],
                    status=JoinRequest.Status.REJECTED,
                    decided_at=now,
                    decided_by=users["h"],
                )
                JoinRequest.objects.filter(pk=rejected.pk).update(created_at=request_time)
            self.stdout.write(f"{key}: party_id={party.pk}, active=2, remaining={capacity - 2}")
        self.stdout.write(
            self.style.SUCCESS(
                f"{self.prefix} ready: {len(self.roles)} users, 1 sport, 3 venues, 6 parties. "
                "Demo users have unusable passwords; no university login is simulated."
            )
        )
