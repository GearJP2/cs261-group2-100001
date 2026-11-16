"""PostgreSQL query semantics for Task79; HTTP/pagination are separate steps."""

from datetime import timedelta

from django.http import QueryDict
from django.test import TestCase
from venues.models import Sport, Venue, VenueSport

from .models import JoinRequest, Party, PartyMembership
from .search import parse_search_query, search_parties
from .services import get_party_state
from .test_join_requests import JoinRequestFixture


class SearchFilterTests(JoinRequestFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.party.venue.venue_type = Venue.Type.INDOOR
        self.party.venue.save(update_fields=["venue_type"])

    def make_party(self, **changes):
        values = {
            "host": self.host,
            "sport": self.party.sport,
            "venue": self.party.venue,
            "title": "Evening Badminton",
            "starts_at": self.party.starts_at,
            "ends_at": self.party.ends_at,
            "capacity": 3,
        }
        values.update(changes)
        party = Party.objects.create(**values)
        PartyMembership.objects.create(party=party, user=self.host)
        return party

    def search(self, **params):
        query = QueryDict("", mutable=True)
        query.update(params)
        return search_parties(parse_search_query(query), now=self.now)

    def ids(self, **params):
        return list(self.search(**params).values_list("pk", flat=True))

    def test_combined_filters_are_and_and_sport_is_not_venue_type(self):
        other_sport = Sport.objects.create(name="Tennis")
        outdoor = Venue.objects.create(
            name="Outdoor court", location_text="Campus", venue_type=Venue.Type.OUTDOOR
        )
        VenueSport.objects.create(venue=self.party.venue, sport=self.party.sport)
        VenueSport.objects.create(venue=self.party.venue, sport=other_sport)
        self.make_party(sport=other_sport)
        self.make_party(venue=outdoor)
        target = self.make_party()
        result = list(
            self.search(
                q="badMINTON",
                sport_id=str(self.party.sport_id),
                venue_id=str(self.party.venue_id),
                venue_type="Indoor",
            )
        )
        self.assertEqual([p.pk for p in result], [target.pk])
        self.assertEqual(result[0].active_member_count, 1)
        self.assertEqual(self.ids(sport_id=str(other_sport.pk), venue_id=str(outdoor.pk)), [])
        self.assertEqual(self.ids(sport_id="999999999"), [])

    def test_unknown_type_and_inactive_venue_are_not_hidden_by_default(self):
        unclassified = Venue.objects.create(name="Unknown", location_text="Campus", is_active=False)
        target = self.make_party(venue=unclassified)
        self.assertIn(target.pk, self.ids())
        self.assertNotIn(target.pk, self.ids(venue_type="Indoor"))
        self.assertNotIn(target.pk, self.ids(venue_type="Outdoor"))

    def test_starts_within_inclusive_lower_exclusive_upper_not_overlap(self):
        start = self.party.starts_at
        end = start + timedelta(hours=2)
        before = self.make_party(starts_at=start - timedelta(microseconds=1), ends_at=end)
        inside = self.make_party(starts_at=end - timedelta(microseconds=1), ends_at=end)
        after = self.make_party(starts_at=end, ends_at=end + timedelta(hours=1))
        ids = self.ids(starts_from=start.isoformat(), starts_to=end.isoformat())
        self.assertEqual(ids, [self.party.pk, inside.pk])
        self.assertIn(before.pk, self.ids(starts_to=start.isoformat()))
        self.assertNotIn(before.pk, self.ids(starts_from=start.isoformat()))
        self.assertIn(after.pk, self.ids(starts_from=end.isoformat()))

    def test_all_states_match_detail_precedence_at_one_instant(self):
        self.make_party(capacity=1)
        self.make_party(starts_at=self.now, ends_at=self.now + timedelta(hours=1))
        self.make_party(starts_at=self.now - timedelta(hours=1), ends_at=self.now)
        self.make_party(
            starts_at=self.now - timedelta(hours=2),
            ends_at=self.now - timedelta(hours=1),
            cancelled_at=self.now,
        )
        rows = list(self.search(state="all"))
        self.assertEqual(
            {p.search_state for p in rows}, {"Open", "Full", "InProgress", "Completed", "Cancelled"}
        )
        for row in rows:
            expected = get_party_state(row, now=self.now, member_count=row.active_member_count)
            self.assertEqual(row.search_state, expected)
            self.assertIn(row.pk, self.ids(state=expected))
        self.assertTrue(all(p.search_state == "Open" for p in self.search()))

    def test_pending_rejected_and_left_do_not_inflate_active_count(self):
        for user, status in [
            (self.applicant, JoinRequest.Status.PENDING),
            (self.other, JoinRequest.Status.REJECTED),
        ]:
            JoinRequest.objects.create(
                party=self.party,
                user=user,
                status=status,
                decided_at=self.now if status == "Rejected" else None,
            )
        PartyMembership.objects.create(party=self.party, user=self.other, left_at=self.now)
        row = self.search().get(pk=self.party.pk)
        self.assertEqual(row.active_member_count, 1)
        PartyMembership.objects.create(party=self.party, user=self.applicant)
        self.assertNotIn(self.party.pk, self.ids())
        self.assertIn(self.party.pk, self.ids(state="Full"))

    def test_text_matches_only_title_and_combines_with_state(self):
        self.party.description = "needle"
        self.party.save(update_fields=["description"])
        target = self.make_party(title="NEEDLE here", capacity=1)
        self.assertEqual(self.ids(q=" needle ", state="all"), [target.pk])
        self.assertEqual(self.ids(q="needle"), [])

    def test_ties_have_stable_id_order_and_search_does_not_write(self):
        second = self.make_party()
        before = list(Party.objects.order_by("pk").values())
        memberships = list(PartyMembership.objects.order_by("pk").values())
        self.assertEqual(self.ids(), [self.party.pk, second.pk])
        self.assertEqual(list(Party.objects.order_by("pk").values()), before)
        self.assertEqual(list(PartyMembership.objects.order_by("pk").values()), memberships)
