"""Task65 real HTTP evidence: disposable DEBUG PostgreSQL and loopback only."""

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django  # noqa: E402

django.setup()
from accounts.models import UserProfile  # noqa: E402
from django.conf import settings  # noqa: E402
from django.contrib.auth import get_user_model  # noqa: E402
from django.db import connection  # noqa: E402
from django.utils import timezone  # noqa: E402
from parties.models import JoinRequest, Party, PartyMembership  # noqa: E402
from venues.models import Sport, Venue  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-test-database", action="store_true")
    parser.add_argument("--base-url", default="http://127.0.0.1:25865")
    args = parser.parse_args()
    url = urlparse(args.base_url)
    if (
        not args.confirm_test_database
        or not settings.DEBUG
        or connection.vendor != "postgresql"
        or not connection.settings_dict["NAME"].startswith("s2_task65_")
        or url.scheme != "http"
        or url.hostname not in {"127.0.0.1", "localhost"}
        or url.username
        or url.password
        or url.path not in {"", "/"}
        or url.query
        or url.fragment
    ):
        raise SystemExit("Requires confirmed disposable DEBUG PostgreSQL and loopback HTTP")
    spec = importlib.util.spec_from_file_location(
        "existing_http", ROOT / "scripts/us10-api-evidence.py"
    )
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    prefix = "qa65_" + uuid4().hex[:8]
    roles = [
        "host",
        "member",
        "fallback",
        "left",
        "pending",
        "rejected",
        "outsider",
        "other",
        "unverified",
    ]
    users = {
        r: get_user_model().objects.create_user(prefix + r, email=prefix + r + "@example.invalid")
        for r in roles
    }
    for r, u in users.items():
        if r != "fallback":
            UserProfile.objects.create(user=u, display_name="Synthetic " + r)
    now = timezone.now()
    sport = Sport.objects.create(name=prefix)
    venue = Venue.objects.create(name=prefix, location_text="Synthetic Task65")
    schedule = dict(
        sport=sport,
        venue=venue,
        starts_at=now + timedelta(days=1),
        ends_at=now + timedelta(days=1, hours=1),
        capacity=10,
    )
    party = Party.objects.create(host=users["host"], title=prefix, **schedule)
    other = Party.objects.create(host=users["outsider"], title=prefix + "other", **schedule)
    # Host inserted last to prove Host-first ordering rather than insertion order.
    for r in ["fallback", "member", "host", "left"]:
        PartyMembership.objects.create(
            party=party, user=users[r], left_at=now if r == "left" else None
        )
    PartyMembership.objects.create(party=other, user=users["other"])
    JoinRequest.objects.create(party=party, user=users["pending"])
    JoinRequest.objects.create(
        party=party,
        user=users["rejected"],
        status=JoinRequest.Status.REJECTED,
        decided_at=now,
        decided_by=users["host"],
    )
    clients = {
        r: helper.Browser(args.base_url, u, verified=r != "unverified") for r, u in users.items()
    }
    clients["anonymous"] = helper.Browser(args.base_url)
    report = dict(
        kind="Assistant-operated real HTTP + PostgreSQL, synthetic verified sessions; not Austin original run or human UAT",
        started_at=now.isoformat(),
        source_commit=subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        database=connection.settings_dict["NAME"],
        python=sys.version.split()[0],
        django=django.get_version(),
        fixture_users={r: u.pk for r, u in users.items()},
        party_id=party.pk,
        cases=[],
    )

    def snapshot():
        with connection.cursor() as cursor:
            result = {}
            for table, column, ids in [
                ("parties_partymembership", "party_id", [party.pk, other.pk]),
                ("parties_joinrequest", "party_id", [party.pk, other.pk]),
                ("accounts_userprofile", "user_id", [u.pk for u in users.values()]),
            ]:
                cursor.execute(
                    f'SELECT * FROM "{table}" WHERE "{column}"=ANY(%s) ORDER BY id', [ids]
                )
                result[table] = [
                    dict(zip([c[0] for c in cursor.description], row, strict=True))
                    for row in cursor.fetchall()
                ]
            return result

    initial = snapshot()
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT user_id FROM parties_partymembership WHERE party_id=%s AND left_at IS NULL ORDER BY joined_at,id",
            [party.pk],
        )
        active = [r[0] for r in cursor.fetchall()]
    expected = [users["host"].pk] + [u for u in active if u != users["host"].pk]
    for label, role, status, code, method, path in [
        ("anonymous", "anonymous", 401, "AUTH_REQUIRED", "GET", None),
        ("unverified", "unverified", 403, "FORBIDDEN", "GET", None),
        ("outsider", "outsider", 403, "FORBIDDEN", "GET", None),
        ("pending", "pending", 403, "FORBIDDEN", "GET", None),
        ("rejected", "rejected", 403, "FORBIDDEN", "GET", None),
        ("left-history", "left", 403, "FORBIDDEN", "GET", None),
        ("other-party-member", "other", 403, "FORBIDDEN", "GET", None),
        ("unknown-party", "host", 404, "NOT_FOUND", "GET", "/api/v1/parties/2147483646/members"),
        ("post", "host", 405, "METHOD_NOT_ALLOWED", "POST", None),
        ("host", "host", 200, None, "GET", None),
        ("active-member", "member", 200, None, "GET", None),
        ("missing-profile-member", "fallback", 200, None, "GET", None),
        (
            "actor-query-spoof",
            "outsider",
            403,
            "FORBIDDEN",
            "GET",
            f"/api/v1/parties/{party.pk}/members?user_id={users['host'].pk}",
        ),
    ]:
        path = path or f"/api/v1/parties/{party.pk}/members"
        actual, body, headers = clients[role].send(method, path, {} if method == "POST" else None)
        assert actual == status, (label, actual, body)
        assert "no-store" in (headers["Cache-Control"] or ""), label
        assert initial == snapshot(), label
        if code:
            assert body["error"]["code"] == code, (label, body)
            assert set(body) == {"error"}, label
        else:
            assert set(body) == {"data"} and set(body["data"]) == {"members", "member_count"}
            data = body["data"]
            members = data["members"]
            assert data["member_count"] == len(active) == len(members)
            assert [m["user_id"] for m in members] == expected
            for m in members:
                assert set(m) == {"user_id", "display_name", "role"}
                assert m["role"] == ("Host" if m["user_id"] == users["host"].pk else "Member")
                assert m["display_name"] == (
                    "ผู้ใช้"
                    if m["user_id"] == users["fallback"].pk
                    else "Synthetic " + next(r for r, u in users.items() if u.pk == m["user_id"])
                )
            text = json.dumps(body, ensure_ascii=False)
            assert all(u.username not in text and u.email not in text for u in users.values())
        if method == "POST":
            assert headers["Allow"] == "GET"
        report["cases"].append(
            dict(
                label=label,
                role=role,
                method=method,
                path=path,
                expected_status=status,
                actual_status=actual,
                expected_code=code,
                response=body,
                headers=headers,
                status="PASS",
                sql_unchanged=True,
            )
        )
    actual, detail, _ = clients["host"].send("GET", f"/api/v1/parties/{party.pk}")
    assert actual == 200 and detail["data"]["member_count"] == len(active), (actual, detail)
    report.update(
        finished_at=timezone.now().isoformat(),
        summary={"Pass": len(report["cases"]), "Fail": 0},
        detail_count=detail["data"]["member_count"],
        sql_before=initial,
        sql_after=snapshot(),
        expected_active_ids=active,
        source_sha256={
            f: hashlib.sha256((ROOT / f).read_bytes()).hexdigest()
            for f in [
                "backend/parties/views.py",
                "backend/parties/services.py",
                "backend/parties/test_members.py",
                "backend/parties/test_members_unit.py",
                "scripts/us10-api-evidence.py",
                "scripts/us6-members-http-evidence.py",
            ]
        },
        not_run=["Live TU login", "Human UI/UAT", "Production load"],
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
