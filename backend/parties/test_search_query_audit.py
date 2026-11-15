"""Task78: real PostgreSQL query audit, not manual HTTP/UI or TU login evidence."""

import hashlib
import json
import os
import platform
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

import django
from accounts.test_support import force_university_login
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, override_settings
from venues.models import Sport, Venue, VenueSport

from .models import JoinRequest, Party, PartyMembership

ROOT = Path(__file__).resolve().parents[2]
ORACLE = ROOT / "database/seeds/us2_search_oracle.sql"
INDEX_AUDIT = ROOT / "database/seeds/us2_search_index_audit.sql"


@override_settings(DEBUG=True)
class SearchQueryAuditTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.at = datetime(2030, 11, 19, 12, tzinfo=ZoneInfo("Asia/Bangkok"))
        cls.start = cls.at + timedelta(hours=12)
        cls.end = cls.start + timedelta(days=1)
        cls.users = [get_user_model().objects.create_user(username=f"q78_{i}") for i in range(5)]
        cls.sports = [Sport.objects.create(name=n) for n in ("q78 badminton", "q78 tennis")]
        cls.venues = [
            Venue.objects.create(name=f"q78_{kind}", location_text="synthetic", venue_type=kind)
            for kind in ("Indoor", "Outdoor", None)
        ]
        # Two sports at one venue must not multiply Party rows or membership counts.
        VenueSport.objects.bulk_create(
            [VenueSport(venue=v, sport=s) for v in cls.venues for s in cls.sports]
        )
        cls.rows = {}
        specs = [
            ("lower", cls.start, 0, 0, 3, None),
            ("upper_inside", cls.end - timedelta(microseconds=1), 0, 0, 3, None),
            ("upper", cls.end, 0, 0, 3, None),
            ("overlap", cls.start - timedelta(microseconds=1), 0, 0, 3, None),
            ("outdoor", cls.start, 0, 1, 3, None),
            ("unknown_type", cls.start, 0, 2, 3, None),
            ("other_sport", cls.start, 1, 0, 3, None),
            ("full", cls.start, 0, 0, 2, None),
            ("started", cls.at, 0, 0, 3, None),
            ("ended", cls.at - timedelta(hours=1), 0, 0, 3, None),
            ("cancelled", cls.at - timedelta(hours=1), 0, 0, 2, cls.at),
        ]
        for name, start, sport, venue, capacity, cancelled in specs:
            p = Party.objects.create(
                host=cls.users[0],
                sport=cls.sports[sport],
                venue=cls.venues[venue],
                title=f"Q78 {name} 100%",
                description="synthetic Task78 data",
                starts_at=start,
                ends_at=start + timedelta(hours=1),
                capacity=capacity,
                cancelled_at=cancelled,
            )
            cls.rows[name] = p
            PartyMembership.objects.bulk_create(
                [
                    PartyMembership(party=p, user=cls.users[0]),
                    PartyMembership(party=p, user=cls.users[1]),
                    PartyMembership(party=p, user=cls.users[2], left_at=cls.at),
                ]
            )
            JoinRequest.objects.bulk_create(
                [
                    JoinRequest(party=p, user=cls.users[3]),
                    JoinRequest(party=p, user=cls.users[4], status="Rejected", decided_at=cls.at),
                ]
            )

    def setUp(self):
        self.assertEqual(connection.vendor, "postgresql")
        with patch("parties.views.timezone.now", return_value=self.at):
            force_university_login(self.client, self.users[0])

    def evidence(self, case, details):
        """Opt-in artifacts only; normal CI does not write evidence into the checkout."""
        target = os.environ.get("TASK78_EVIDENCE_DIR")
        if not target:
            return
        target = Path(target)
        target.mkdir(parents=True, exist_ok=True)
        with connection.cursor() as cursor:
            cursor.execute("SELECT version(), current_database()")
            postgres, database = cursor.fetchone()
        record = {
            "case": case,
            "result": "PASS",
            "kind": "automated PostgreSQL query audit",
            "not_covered": "manual HTTP/UI/UAT, live TU login, Task84 full acceptance",
            "source": os.environ.get("TASK78_SOURCE", "unspecified checkout"),
            "tester": "Gold / agent-operated execution",
            "python": platform.python_version(),
            "django": django.get_version(),
            "postgresql": postgres,
            "database": database,
            "controlled_now": self.at.isoformat(),
            "executed_at": datetime.now(ZoneInfo("Asia/Bangkok")).isoformat(),
            "source_sha256": {
                name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                for name in (
                    "backend/parties/views.py",
                    "backend/parties/models.py",
                    "backend/venues/models.py",
                    "backend/parties/test_search_query_audit.py",
                    "database/seeds/us2_search_oracle.sql",
                )
            },
            **details,
        }
        (target / f"{case}.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8"
        )

    def audit(self, query):
        params = [
            self.at,
            query.get("sport_id"),
            query.get("venue_id"),
            query.get("venue_type"),
            query.get("starts_from"),
            query.get("starts_to"),
            query.get("state", "Open"),
            query.get("q", "").strip() or None,
        ]
        with connection.cursor() as cursor:
            cursor.execute(ORACLE.read_text(encoding="utf-8"), params)
            expected = cursor.fetchall()
        with patch("parties.views.timezone.now", return_value=self.at):
            response = self.client.get("/api/v1/parties", query)
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        page, size = query.get("page", 1), query.get("page_size", 20)
        selected = expected[(page - 1) * size : page * size]
        actual = [(p["id"], p["state"], p["member_count"]) for p in body["data"]]
        self.assertEqual(actual, selected)
        self.assertEqual(body["total"], len(expected))
        self.assertEqual((body["page"], body["page_size"]), (page, size))
        return {
            "query": query,
            "expected": selected,
            "actual": actual,
            "expected_total": len(expected),
            "actual_total": body["total"],
        }

    def test_q78_01_mapping_and_filters_do_not_multiply_active_counts(self):
        checks = []
        for query in (
            {},
            {"sport_id": self.sports[0].pk},
            {"venue_id": self.venues[0].pk},
            {"venue_type": "Indoor"},
            {"venue_type": "Outdoor"},
            {
                "sport_id": self.sports[0].pk,
                "venue_id": self.venues[0].pk,
                "venue_type": "Indoor",
                "q": "  q78 LOWER  ",
            },
            {"venue_id": self.venues[0].pk, "venue_type": "Outdoor"},
            {"sport_id": 99999999},
            {"q": "100%"},
        ):
            with self.subTest(query=query):
                checks.append(self.audit(query))
        self.assertEqual(PartyMembership.objects.filter(party=self.rows["lower"]).count(), 3)
        self.assertEqual(JoinRequest.objects.filter(party=self.rows["lower"]).count(), 2)
        self.evidence("Q78-01", {"checks": checks})

    def test_q78_02_half_open_bangkok_and_utc_boundaries(self):
        query = {
            "starts_from": self.start.isoformat(),
            "starts_to": self.end.isoformat(),
            "sport_id": self.sports[0].pk,
            "venue_id": self.venues[0].pk,
        }
        first = self.audit(query)
        self.assertEqual(
            [p[0] for p in first["actual"]], [self.rows["lower"].pk, self.rows["upper_inside"].pk]
        )
        utc = ZoneInfo("UTC")
        second = self.audit(
            query
            | {
                "starts_from": self.start.astimezone(utc).isoformat(),
                "starts_to": self.end.astimezone(utc).isoformat(),
            }
        )
        self.assertEqual(first["actual"], second["actual"])
        self.evidence("Q78-02", {"checks": [first, second]})

    def test_q78_03_state_precedence_and_detail_agree_at_same_instant(self):
        checks = []
        for state in ("Open", "Full", "InProgress", "Completed", "Cancelled", "all"):
            result = self.audit({"state": state})
            for pk, expected_state, count in result["actual"]:
                with patch("parties.services.timezone.now", return_value=self.at):
                    detail = self.client.get(f"/api/v1/parties/{pk}").json()["data"]
                self.assertEqual((detail["state"], detail["member_count"]), (expected_state, count))
            checks.append(result)
        self.evidence("Q78-03", {"checks": checks})

    def test_q78_04_pagination_after_filter_with_stable_ties(self):
        query = {"venue_type": "Indoor", "state": "all", "page_size": 2}
        checks = [self.audit(query | {"page": p}) for p in (1, 2, 3, 99)]
        self.assertEqual(checks[-1]["actual"], [])
        self.evidence("Q78-04", {"checks": checks})

    def test_q78_05_schema_and_existing_index_inventory(self):
        with connection.cursor() as cursor:
            cursor.execute(INDEX_AUDIT.read_text(encoding="utf-8"))
            indexes = cursor.fetchall()
            constraints = connection.introspection.get_constraints(cursor, "parties_party")
            cursor.execute(
                "SELECT is_nullable, character_maximum_length "
                "FROM information_schema.columns WHERE table_schema=current_schema() "
                "AND table_name='venues_venue' AND column_name='venue_type'"
            )
            self.assertEqual(cursor.fetchone(), ("YES", 7))
        indexed_columns = {tuple(c["columns"]) for c in constraints.values() if c["index"]}
        self.assertIn(("sport_id", "starts_at"), indexed_columns)
        self.assertIn(("venue_id",), indexed_columns)
        self.assertTrue(
            any(c["foreign_key"] == ("venues_sport", "id") for c in constraints.values())
        )
        self.assertTrue(
            any(c["foreign_key"] == ("venues_venue", "id") for c in constraints.values())
        )
        self.evidence(
            "Q78-05",
            {
                "expected": "nullable venue_type + FKs + existing indexes",
                "actual": "matched",
                "indexes": indexes,
            },
        )

    def test_q78_06_explain_actual_api_query_on_selective_10011_party_fixture(self):
        Party.objects.bulk_create(
            [
                Party(
                    host=self.users[0],
                    sport=self.sports[1],
                    venue=self.venues[1],
                    title=f"Q78 bulk {i}",
                    starts_at=self.end + timedelta(days=10, minutes=i),
                    ends_at=self.end + timedelta(days=10, minutes=i + 60),
                    capacity=3,
                )
                for i in range(10000)
            ]
        )
        with connection.cursor() as cursor:
            cursor.execute("ANALYZE parties_party")
            cursor.execute("ANALYZE parties_partymembership")
        captured = []

        def capture(execute, sql, params, many, context):
            if sql.startswith("SELECT") and 'FROM "parties_party"' in sql:
                captured.append((sql, params))
            return execute(sql, params, many, context)

        query = {
            "sport_id": self.sports[0].pk,
            "venue_id": self.venues[0].pk,
            "starts_from": self.start.isoformat(),
            "starts_to": self.end.isoformat(),
        }
        with connection.execute_wrapper(capture):
            result = self.audit(query)
        # Explain both executed SELECTs; pagination also needs a filtered total.
        plans = []
        for sql, params in captured:
            kind = "data" if '"accounts_user"' in sql else "count"
            with connection.cursor() as cursor:
                cursor.execute("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + sql, params)
                plan = cursor.fetchone()[0]
            self.assertEqual(
                plan[0]["Plan"]["Actual Rows"], len(result["actual"]) if kind == "data" else 1
            )
            plans.append({"kind": kind, "sql": sql, "parameters": params, "explain": plan})
        self.assertEqual(Party.objects.count(), 10011)
        self.assertEqual([p["kind"] for p in plans], ["count", "data"])
        self.evidence(
            "Q78-06",
            {
                "fixture_party_count": 10011,
                "check": result,
                "plans": plans,
                "decision": "Review existing planner/index use; no forced index",
            },
        )
