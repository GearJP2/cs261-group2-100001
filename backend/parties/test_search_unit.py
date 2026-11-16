"""Task83 filter-builder units with an in-memory repository, no SQL/HTTP.

The stub evaluates Django expression objects for simple fixture rows. Active
counts are fixture inputs here: SQL count correctness belongs to integration.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from django.db.models import F, Q
from django.http import QueryDict
from django.test import SimpleTestCase

from .search import parse_search_query, search_parties
from .services import get_party_state


def matches(row, lookup, expected):
    parts = lookup.split("__")
    operator = parts.pop() if parts[-1] in {"gte", "lte", "lt", "isnull", "icontains"} else "exact"
    actual = row
    for part in parts:
        actual = getattr(actual, part)
    if isinstance(expected, F):
        expected = getattr(row, expected.name)
    if operator == "isnull":
        return (actual is None) == expected
    if operator == "icontains":
        return expected.casefold() in actual.casefold()
    if operator == "gte":
        return actual >= expected
    if operator == "lte":
        return actual <= expected
    if operator == "lt":
        return actual < expected
    return actual == expected


def evaluate_condition(row, condition):
    outcomes = [
        evaluate_condition(row, child) if isinstance(child, Q) else matches(row, *child)
        for child in condition.children
    ]
    result = all(outcomes) if condition.connector == Q.AND else any(outcomes)
    return not result if condition.negated else result


class MemoryQuerySet:
    def __init__(self, rows):
        self.rows = list(rows)
        self.filters = []

    def annotate(self, **expressions):
        # Count is supplied by fixtures, not falsely claimed as tested SQL.
        expression = expressions.get("search_state")
        if expression is not None:
            for row in self.rows:
                row.search_state = next(
                    (
                        case.result.value
                        for case in expression.cases
                        if evaluate_condition(row, case.condition)
                    ),
                    expression.default.value,
                )
        return self

    def filter(self, **lookups):
        self.filters.append(lookups)
        self.rows = [
            row
            for row in self.rows
            if all(matches(row, key, value) for key, value in lookups.items())
        ]
        return self

    def order_by(self, *fields):
        self.rows.sort(key=lambda row: tuple(getattr(row, field) for field in fields))
        return self


class SearchBuilderUnitTests(SimpleTestCase):
    def setUp(self):
        self.now = datetime(2030, 11, 19, 5, tzinfo=timezone.utc)
        self.start = datetime.fromisoformat("2030-11-20T00:00:00+07:00")
        self.end = self.start + timedelta(days=1)

    def row(self, pk, **changes):
        data = {
            "pk": pk,
            "sport_id": 1,
            "venue_id": 2,
            "venue": SimpleNamespace(venue_type="Indoor"),
            "title": "Needle badminton",
            "starts_at": self.start,
            "ends_at": self.end,
            "cancelled_at": None,
            "active_member_count": 1,
            "capacity": 3,
        }
        data.update(changes)
        return SimpleNamespace(**data)

    def search(self, rows, **params):
        query = QueryDict("", mutable=True)
        query.update(params)
        repository = MemoryQuerySet(rows)
        with patch("parties.search.Party.objects") as manager:
            manager.select_related.return_value = repository
            result = search_parties(parse_search_query(query), now=self.now)
            manager.select_related.assert_called_once_with("host__profile")
        return result

    def test_ut02_combined_filters_require_all_conditions(self):
        rows = [
            self.row(1),
            self.row(2, sport_id=9),
            self.row(3, venue_id=9),
            self.row(4, venue=SimpleNamespace(venue_type="Outdoor")),
            self.row(5, title="Unrelated"),
            self.row(6, starts_at=self.end, ends_at=self.end + timedelta(hours=1)),
        ]
        result = self.search(
            rows,
            sport_id="1",
            venue_id="2",
            venue_type="Indoor",
            q="  NEEDLE  ",
            starts_from=self.start.isoformat(),
            starts_to=self.end.isoformat(),
        )
        self.assertEqual([row.pk for row in result.rows], [1])
        self.assertEqual(len(result.filters), 7)

    def test_ut03_sport_and_venue_type_are_independent_predicates(self):
        rows = [
            self.row(1),
            self.row(2, sport_id=9),
            self.row(3, venue=SimpleNamespace(venue_type="Outdoor")),
            self.row(4, venue=SimpleNamespace(venue_type=None)),
        ]
        self.assertEqual([r.pk for r in self.search(rows, sport_id="1").rows], [1, 3, 4])
        self.assertEqual([r.pk for r in self.search(rows, venue_type="Indoor").rows], [1, 2])
        self.assertEqual(
            [r.pk for r in self.search(rows, sport_id="9", venue_type="Outdoor").rows], []
        )

    def test_ut04_bangkok_boundaries_are_start_inclusive_end_exclusive(self):
        rows = [
            self.row(1, starts_at=self.start - timedelta(microseconds=1)),
            self.row(2),
            self.row(3, starts_at=self.end - timedelta(microseconds=1)),
            self.row(4, starts_at=self.end, ends_at=self.end + timedelta(hours=1)),
        ]
        for start, end in [
            (self.start.isoformat(), self.end.isoformat()),
            (
                self.start.astimezone(timezone.utc).isoformat(),
                self.end.astimezone(timezone.utc).isoformat(),
            ),
        ]:
            with self.subTest(start=start):
                result = self.search(rows, starts_from=start, starts_to=end)
                self.assertEqual([row.pk for row in result.rows], [2, 3])
        self.assertEqual(
            [r.pk for r in self.search(rows, starts_to=self.start.isoformat()).rows], [1]
        )

    def test_ut05_state_predicates_match_detail_and_precedence(self):
        rows = [
            self.row(1),
            self.row(2, active_member_count=3),
            self.row(3, starts_at=self.now),
            self.row(4, starts_at=self.now - timedelta(hours=1), ends_at=self.now),
            self.row(
                5,
                cancelled_at=self.now,
                active_member_count=3,
                starts_at=self.now - timedelta(hours=2),
                ends_at=self.now - timedelta(hours=1),
            ),
        ]
        states = ["Open", "Full", "InProgress", "Completed", "Cancelled"]
        for row, expected in zip(rows, states, strict=True):
            self.assertEqual(
                get_party_state(row, now=self.now, member_count=row.active_member_count), expected
            )
        for expected in states:
            with self.subTest(state=expected):
                result = self.search(rows, state=expected)
                self.assertEqual([r.pk for r in result.rows], [states.index(expected) + 1])
                self.assertTrue(all(r.search_state == expected for r in result.rows))
        self.assertEqual([r.pk for r in self.search(rows).rows], [1])
        self.assertEqual(len(self.search(rows, state="all").rows), 5)

    def test_ut02_stable_order_and_no_state_predicate_for_all(self):
        result = self.search([self.row(3), self.row(1), self.row(2)], state="all")
        self.assertEqual([r.pk for r in result.rows], [1, 2, 3])
        self.assertEqual(result.filters, [])
