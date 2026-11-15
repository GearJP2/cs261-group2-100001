"""Task84: real loopback HTTP + PostgreSQL; agent-operated, not human UI/UAT."""

import hashlib
import json
import os
import platform
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import django
from accounts.test_support import force_university_login
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import Client, LiveServerTestCase, override_settings
from venues.models import Sport, Venue, VenueSport

from .models import JoinRequest, Party, PartyMembership

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "database/seeds/us2_search_snapshot.sql"


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


@override_settings(DEBUG=True)
class SearchDatabaseAcceptanceTests(LiveServerTestCase):
    def setUp(self):
        self.assertEqual(connection.vendor, "postgresql")
        self.at = datetime(2030, 11, 19, 12, tzinfo=ZoneInfo("Asia/Bangkok"))
        self.start = self.at + timedelta(hours=12)
        self.end = self.start + timedelta(days=1)
        clock = patch("parties.views.timezone.now", return_value=self.at)
        clock.start()
        self.addCleanup(clock.stop)
        self.users = [get_user_model().objects.create_user(username=f"db84_{i}") for i in range(5)]
        self.sports = [Sport.objects.create(name=n) for n in ("DB84 badminton", "DB84 tennis")]
        self.venues = [
            Venue.objects.create(name=f"DB84 {kind}", location_text="synthetic", venue_type=kind)
            for kind in ("Indoor", "Outdoor", None)
        ]
        VenueSport.objects.bulk_create(
            [VenueSport(venue=v, sport=self.sports[0]) for v in self.venues]
            + [VenueSport(venue=self.venues[0], sport=self.sports[1])]
        )
        self.rows = {}
        for name, start, sport, venue, capacity, cancelled in (
            ("lower", self.start, 0, 0, 3, None),
            ("inside", self.end - timedelta(microseconds=1), 0, 0, 3, None),
            ("upper", self.end, 0, 0, 3, None),
            ("overlap", self.start - timedelta(microseconds=1), 0, 0, 3, None),
            ("outdoor", self.start, 0, 1, 3, None),
            ("unknown", self.start, 0, 2, 3, None),
            ("other", self.start, 1, 0, 3, None),
            ("full", self.start, 0, 0, 2, None),
            ("started", self.at, 0, 0, 3, None),
            ("ended", self.at - timedelta(hours=1), 0, 0, 3, None),
            ("cancelled", self.at - timedelta(hours=1), 0, 0, 2, self.at),
        ):
            party = Party.objects.create(
                host=self.users[0],
                sport=self.sports[sport],
                venue=self.venues[venue],
                title=f"DB84 {name}",
                starts_at=start,
                ends_at=start + timedelta(hours=1),
                capacity=capacity,
                cancelled_at=cancelled,
            )
            self.rows[name] = party
            PartyMembership.objects.bulk_create(
                [
                    PartyMembership(party=party, user=self.users[0]),
                    PartyMembership(party=party, user=self.users[1]),
                    PartyMembership(party=party, user=self.users[2], left_at=self.at),
                ]
            )
            JoinRequest.objects.bulk_create(
                [
                    JoinRequest(party=party, user=self.users[3]),
                    JoinRequest(
                        party=party, user=self.users[4], status="Rejected", decided_at=self.at
                    ),
                ]
            )
        self.headers = {}
        for actor in (0, 3):
            client = Client(enforce_csrf_checks=True)
            force_university_login(client, self.users[actor])
            csrf = client.get("/api/v1/auth/csrf").json()["data"]["csrf_token"]
            cookie = "; ".join(f"{key}={value.value}" for key, value in client.cookies.items())
            self.headers[actor] = {
                "Cookie": cookie,
                "X-CSRFToken": csrf,
                "Origin": self.live_server_url,
                "Content-Type": "application/json",
            }
        self.events = []
        self.baseline = self.snapshot()

    def snapshot(self):
        with connection.cursor() as cursor:
            cursor.execute(SNAPSHOT.read_text(encoding="utf-8"), [self.at])
            columns = [column.name for column in cursor.description]
            return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]

    def http(self, path, *, actor=0, method="GET", payload=None):
        request = Request(
            self.live_server_url + path,
            method=method,
            headers=self.headers[actor],
            data=None if payload is None else json.dumps(payload).encode(),
        )
        try:
            response = urlopen(request, timeout=10)
        except HTTPError as error:
            response = error
        with response:
            status, body = response.status, json.loads(response.read())
        # Deliberately omit cookie/CSRF headers and the synthetic session key.
        self.events.append(
            {
                "method": method,
                "path": path,
                "actor_alias": f"db84_{actor}",
                "payload": payload,
                "status": status,
                "response": body,
            }
        )
        return status, body

    def search(self, query, expected_names, *, page=1, size=20):
        before = self.snapshot()
        expected_ids = [self.rows[name].pk for name in expected_names]
        expected_ids.sort(
            key=lambda pk: next((r["starts_at"], pk) for r in before if r["id"] == pk)
        )
        selected = expected_ids[(page - 1) * size : page * size]
        status, body = self.http(
            "/api/v1/parties?" + urlencode(query | {"page": page, "page_size": size})
        )
        self.assertEqual(status, 200, body)
        actual = body["data"]
        self.assertEqual([p["id"] for p in actual], selected)
        self.assertEqual(len({p["id"] for p in actual}), len(actual))
        self.assertEqual(
            (body["total"], body["page"], body["page_size"]), (len(expected_ids), page, size)
        )
        sql_rows = {row["id"]: row for row in before}
        for item in actual:
            sql = sql_rows[item["id"]]
            self.assertEqual(
                (item["state"], item["member_count"], item["remaining_slots"]),
                (sql["state"], sql["active_count"], sql["capacity"] - sql["active_count"]),
            )
            self.assertEqual(
                (item["sport_id"], item["venue_id"]), (sql["sport_id"], sql["venue_id"])
            )
            self.assertEqual(datetime.fromisoformat(item["starts_at"]), sql["starts_at"])
        # Detail must agree without modifying any business row either.
        for item in actual:
            status, detail = self.http(f"/api/v1/parties/{item['id']}")
            self.assertEqual(status, 200)
            self.assertEqual(
                (detail["data"]["state"], detail["data"]["member_count"]),
                (item["state"], item["member_count"]),
            )
        after = self.snapshot()
        self.assertEqual(after, before)
        self.events.append(
            {
                "check": "search_vs_independent_sql",
                "query": query,
                "expected_fixture_names": expected_names,
                "expected_ids": selected,
                "actual_ids": [p["id"] for p in actual],
                "expected_total": len(expected_ids),
                "actual_total": body["total"],
                "page": page,
                "page_size": size,
                "business_before_sha256": digest(before),
                "business_after_sha256": digest(after),
                "business_rows_unchanged": True,
                "result": "PASS",
            }
        )

    def evidence(self, case):
        directory = os.environ.get("TASK84_EVIDENCE_DIR")
        if not directory:
            return
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database(), version()")
            database, version = cursor.fetchone()
        record = {
            "case": case,
            "result": "PASS",
            "kind": "agent-operated real loopback HTTP + SQL",
            "not_covered": "human UI/UAT, live TU login, concurrent race/production load",
            "source": os.environ.get("TASK84_SOURCE", "unspecified checkout"),
            "tester": "agent on Gold workstation",
            "executed_at": datetime.now(ZoneInfo("Asia/Bangkok")).isoformat(),
            "controlled_now": self.at.isoformat(),
            "database": database,
            "postgresql": version,
            "python": platform.python_version(),
            "django": django.get_version(),
            "source_sha256": {
                name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                for name in (
                    "backend/parties/views.py",
                    "backend/parties/services.py",
                    "backend/parties/test_search_database_acceptance.py",
                    "database/seeds/us2_search_snapshot.sql",
                )
            },
            "baseline_sql_snapshot": self.baseline,
            "events": self.events,
        }
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        # Keep earlier runs intact and emit PASS only after all assertions return.
        with (directory / f"{case}.json").open("x", encoding="utf-8") as output:
            output.write(json.dumps(record, ensure_ascii=False, indent=2, default=str) + "\n")

    def test_db84_01_and_multi_sport_venue_type_null_and_no_fanout(self):
        open_names = ["lower", "inside", "upper", "overlap", "outdoor", "unknown", "other"]
        for query, expected in (
            ({}, open_names),
            ({"sport_id": self.sports[0].pk}, [n for n in open_names if n != "other"]),
            ({"venue_id": self.venues[0].pk}, ["lower", "inside", "upper", "overlap", "other"]),
            ({"venue_type": "Outdoor"}, ["outdoor"]),
            ({"venue_type": "Indoor"}, ["lower", "inside", "upper", "overlap", "other"]),
            ({"sport_id": self.sports[0].pk, "venue_type": "Indoor", "q": " LOWER "}, ["lower"]),
            ({"sport_id": self.sports[1].pk, "venue_id": self.venues[1].pk}, []),
            ({"sport_id": 99999999}, []),
        ):
            self.search(query, expected)
        self.evidence("DB84-01")

    def test_db84_02_half_open_one_sided_and_offset_equivalence(self):
        base = {"sport_id": self.sports[0].pk, "venue_id": self.venues[0].pk}
        self.search(
            base | {"starts_from": self.start.isoformat(), "starts_to": self.end.isoformat()},
            ["lower", "inside"],
        )
        self.search(base | {"starts_from": self.start.isoformat()}, ["lower", "inside", "upper"])
        self.search(base | {"starts_to": self.end.isoformat()}, ["overlap", "lower", "inside"])
        utc = ZoneInfo("UTC")
        self.search(
            base
            | {
                "starts_from": self.start.astimezone(utc).isoformat(),
                "starts_to": self.end.astimezone(utc).isoformat(),
            },
            ["lower", "inside"],
        )
        self.evidence("DB84-02")

    def test_db84_03_all_states_exact_time_and_detail(self):
        for state, expected in (
            ("Open", ["lower", "inside", "upper", "overlap", "outdoor", "unknown", "other"]),
            ("Full", ["full"]),
            ("InProgress", ["started"]),
            ("Completed", ["ended"]),
            ("Cancelled", ["cancelled"]),
            ("all", list(self.rows)),
        ):
            self.search({"state": state}, expected)
        self.evidence("DB84-03")

    def test_db84_04_101_tied_results_filter_before_count_and_pagination(self):
        new = Party.objects.bulk_create(
            [
                Party(
                    host=self.users[0],
                    sport=self.sports[0],
                    venue=self.venues[0],
                    title=f"DB84 page {i:03}",
                    starts_at=self.start,
                    ends_at=self.start + timedelta(hours=1),
                    capacity=3,
                )
                for i in range(101)
            ]
        )
        for i, party in enumerate(new):
            self.rows[f"page_{i:03}"] = party
        self.baseline = self.snapshot()
        names = [n for n in self.rows if n.startswith("page_")]
        for page in (1, 2, 3, 4, 5, 6, 999):
            self.search({"q": "DB84 page", "venue_type": "Indoor"}, names, page=page)
        self.search({"q": "DB84 page"}, names, size=100)
        self.evidence("DB84-04")

    def test_db84_05_search_refresh_after_committed_approve_leave_cancel(self):
        party = self.rows["lower"]
        query = {"q": "DB84 lower"}
        self.search(query, ["lower"])
        pending = JoinRequest.objects.get(party=party, user=self.users[3])
        status, _ = self.http(
            f"/api/v1/parties/{party.pk}/join-requests/{pending.pk}/decision",
            method="POST",
            payload={"status": "Approved"},
        )
        self.assertEqual(status, 200)
        self.search(query, [])
        self.search(query | {"state": "Full"}, ["lower"])
        before_leave = next(r for r in self.snapshot() if r["id"] == party.pk)
        membership = PartyMembership.objects.get(party=party, user=self.users[3])
        status, body = self.http(
            f"/api/v1/parties/{party.pk}/leave", actor=3, method="POST", payload={}
        )
        self.assertEqual(status, 200, body)
        self.search(query, ["lower"])
        after_leave = next(r for r in self.snapshot() if r["id"] == party.pk)
        self.assertEqual((before_leave["active_count"], after_leave["active_count"]), (3, 2))
        membership.refresh_from_db()
        self.assertIsNotNone(membership.left_at)
        self.assertTrue(JoinRequest.objects.filter(pk=pending.pk, status="Approved").exists())
        status, _ = self.http(f"/api/v1/parties/{party.pk}/cancel", method="POST", payload={})
        self.assertEqual(status, 200)
        self.search(query, [])
        self.search(query | {"state": "Cancelled"}, ["lower"])
        self.events.append(
            {
                "transition_sql_before_leave": before_leave,
                "transition_sql_after_leave": after_leave,
                "transition_sql_after_cancel": next(
                    r for r in self.snapshot() if r["id"] == party.pk
                ),
            }
        )
        self.evidence("DB84-05")

    def test_db84_06_invalid_queries_preserve_business_rows(self):
        for query in (
            {"starts_from": self.start.isoformat(), "starts_to": self.start.isoformat()},
            {"starts_from": self.end.isoformat(), "starts_to": self.start.isoformat()},
            {"starts_from": "2030-11-20T00:00:00"},
            {"starts_to": "2030-11-20"},
            {"unknown": "ignored?"},
            {"page_size": 101},
        ):
            before = self.snapshot()
            status, body = self.http("/api/v1/parties?" + urlencode(query))
            self.assertEqual(status, 400, body)
            self.assertEqual(body["error"]["code"], "INVALID_INPUT")
            after = self.snapshot()
            self.assertEqual(before, after)
            self.events.append(
                {
                    "check": "invalid_query_read_only",
                    "expected_status": 400,
                    "actual_status": status,
                    "business_before_sha256": digest(before),
                    "business_after_sha256": digest(after),
                    "result": "PASS",
                }
            )
        self.evidence("DB84-06")
