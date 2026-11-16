"""Task79 validation tests; no database or external university API required."""

from datetime import timedelta

from django.http import QueryDict
from django.test import SimpleTestCase

from .search import parse_search_query
from .services import PartyError


class SearchQueryTests(SimpleTestCase):
    def parse(self, **params):
        query = QueryDict("", mutable=True)
        query.update(params)
        return parse_search_query(query)

    def assert_invalid(self, query, *fields):
        with self.assertRaises(PartyError) as caught:
            parse_search_query(query)
        error = caught.exception
        self.assertEqual((error.code, error.status), ("INVALID_INPUT", 400))
        self.assertEqual(set(error.fields), set(fields))

    def test_defaults_and_normalization(self):
        self.assertEqual(self.parse(), {"q": "", "state": "Open", "page": 1, "page_size": 20})
        result = self.parse(
            q="  เล่นกีฬา  ",
            sport_id="001",
            venue_id="2",
            page="3",
            page_size="100",
            venue_type="Indoor",
            state="all",
        )
        self.assertEqual(
            result,
            {
                "q": "เล่นกีฬา",
                "sport_id": 1,
                "venue_id": 2,
                "page": 3,
                "page_size": 100,
                "venue_type": "Indoor",
                "state": "all",
            },
        )

    def test_all_enum_values(self):
        for state in ["Open", "Full", "InProgress", "Completed", "Cancelled", "all"]:
            self.assertEqual(self.parse(state=state)["state"], state)
        for kind in ["Indoor", "Outdoor"]:
            self.assertEqual(self.parse(venue_type=kind)["venue_type"], kind)

    def test_integer_validation(self):
        for key in ["sport_id", "venue_id", "page", "page_size"]:
            for value in ["", "0", "-1", "1.5", "true", "+1", " 1", "๑"]:
                with self.subTest(key=key, value=value):
                    query = QueryDict("", mutable=True)
                    query[key] = value
                    self.assert_invalid(query, key)
        self.assert_invalid(QueryDict("page_size=101"), "page_size")

    def test_unknown_repeated_empty_and_invalid_enum(self):
        for raw, fields in [
            ("unknown=x", ["unknown"]),
            ("q=a&q=b", ["q"]),
            ("state=Open&state=Open", ["state"]),
            ("state=open", ["state"]),
            ("venue_type=indoor", ["venue_type"]),
            ("venue_type=", ["venue_type"]),
            ("state=&sport_id=x&page=0", ["state", "sport_id", "page"]),
        ]:
            with self.subTest(raw=raw):
                self.assert_invalid(QueryDict(raw), *fields)

    def test_text_limits_after_trim(self):
        self.assertEqual(self.parse(q="  ")["q"], "")
        self.assertEqual(self.parse(q=" " + "ก" * 100 + " ")["q"], "ก" * 100)
        query = QueryDict("", mutable=True)
        query["q"] = "ก" * 101
        self.assert_invalid(query, "q")

    def test_aware_times_normalized_to_same_instant_and_single_bounds(self):
        bangkok = self.parse(starts_from="2030-11-20T00:00:00+07:00")["starts_from"]
        utc = self.parse(starts_from="2030-11-19T17:00:00Z")["starts_from"]
        self.assertEqual(bangkok, utc)
        self.assertEqual(bangkok.utcoffset(), timedelta(0))
        self.assertIn("starts_to", self.parse(starts_to="2030-11-21T00:00:00+07:00"))

    def test_invalid_dates_offsets_and_range(self):
        for value in [
            "",
            "2030-11-20",
            "2030-11-20T00:00:00",
            "2030-02-30T00:00:00Z",
            "2030-11-20T00:00:00+25:00",
            "0001-01-01T00:00:00+07:00",
        ]:
            with self.subTest(value=value):
                query = QueryDict("", mutable=True)
                query["starts_from"] = value
                self.assert_invalid(query, "starts_from")
        for end in ["2030-11-20T00:00:00Z", "2030-11-19T00:00:00Z"]:
            query = QueryDict("", mutable=True)
            query.update(starts_from="2030-11-20T00:00:00Z", starts_to=end)
            self.assert_invalid(query, "starts_to")
