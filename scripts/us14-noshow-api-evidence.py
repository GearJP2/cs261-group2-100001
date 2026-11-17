"""Task94 real HTTP/SQL retest. DEBUG + disposable DB + explicit confirmation only.

Uses existing Browser session fixtures, never live TU credentials. Changes the
feature flag only in a dedicated s2-task94-* Docker Compose project. No rows reset.
"""

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
from conduct.services import submit_review  # noqa: E402
from django.conf import settings  # noqa: E402
from django.contrib.auth import get_user_model  # noqa: E402
from django.db import connection  # noqa: E402
from django.utils import timezone  # noqa: E402
from parties.models import Party, PartyMembership  # noqa: E402
from venues.models import Sport, Venue  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-test-database", action="store_true")
    parser.add_argument("--base-url", default="http://127.0.0.1:25894")
    parser.add_argument("--compose-env", required=True)
    parser.add_argument("--compose-overlay", required=True)
    parser.add_argument("--project", default="s2-task94-noshow")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    url = urlparse(args.base_url)
    output = Path(args.output)
    if (
        not args.confirm_test_database
        or not settings.DEBUG
        or connection.vendor != "postgresql"
        or not connection.settings_dict["NAME"].startswith("s2_task94_")
        or not args.project.startswith("s2-task94-")
        or url.scheme != "http"
        or url.hostname not in {"127.0.0.1", "localhost"}
        or url.username
        or url.password
        or url.path not in {"", "/"}
        or url.query
        or url.fragment
        or output.exists()
    ):
        raise SystemExit("Requires confirmed DEBUG test DB/project, loopback HTTP and new output")
    output.mkdir(parents=True)
    spec = importlib.util.spec_from_file_location(
        "task56_browser", ROOT / "scripts/us10-api-evidence.py"
    )
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    browser = helper.Browser
    prefix = "qa94_" + uuid4().hex[:8]
    users = {
        role: get_user_model().objects.create_user(prefix + role)
        for role in ("host", "a", "b", "target", "early", "outsider", "negative", "unverified")
    }
    for role, user in users.items():
        UserProfile.objects.create(
            user=user,
            display_name="Synthetic " + role,
            credit_score=-2 if role == "negative" else None,
        )
    sport = Sport.objects.create(name=prefix)
    venue = Venue.objects.create(name=prefix, location_text="Synthetic Task94 fixture")
    now = timezone.now()
    parties = {}
    for label in ("main", "single", "negative", "expired", "future", "cancelled"):
        solo = label in {"single", "negative"}
        p = Party.objects.create(
            host=users["a"] if solo else users["host"],
            sport=sport,
            venue=venue,
            title=prefix + label,
            capacity=10,
            starts_at=now - timedelta(hours=3),
            ends_at=now - timedelta(hours=2),
        )
        roles = (
            ("a", "negative")
            if label == "negative"
            else ("a", "target")
            if solo
            else ("host", "a", "b", "target", "early")
        )
        for role in roles:
            PartyMembership.objects.create(
                party=p,
                user=users[role],
                left_at=p.ends_at - timedelta(seconds=1) if role == "early" else None,
            )
        if label == "expired":
            p.starts_at = now - timedelta(days=9, hours=1)
            p.ends_at = now - timedelta(days=9)
        if label == "future":
            p.starts_at, p.ends_at = now + timedelta(days=1), now + timedelta(days=1, hours=1)
        if label == "cancelled":
            p.cancelled_at = now
        p.save()
        parties[label] = p
    # Establish real star rows/cache as fixture preparation, independently of No-show.
    for role, rating in (("host", 3), ("a", 5)):
        submit_review(
            party_id=parties["main"].pk,
            reviewer=users[role],
            reviewee_id=users["target"].pk,
            rating=rating,
            comment="Synthetic opening rating",
        )
    clients = {
        role: browser(args.base_url, u, verified=role != "unverified") for role, u in users.items()
    }
    clients["anonymous"] = browser(args.base_url)
    report = {
        "kind": "real HTTP + PostgreSQL; synthetic verified sessions, not TU login/human UAT",
        "started_at": timezone.localtime().isoformat(),
        "database": connection.settings_dict["NAME"],
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "fixture_users": {r: u.pk for r, u in users.items()},
        "fixture_parties": {r: p.pk for r, p in parties.items()},
        "cases": [],
    }
    with connection.cursor() as cursor:
        cursor.execute("SELECT version()")
        report["postgresql"] = cursor.fetchone()[0]

    def snapshot():
        with connection.cursor() as cursor:
            result = {}
            for table, clause, ids in (
                ("conduct_noshowreport", "party_id", [p.pk for p in parties.values()]),
                ("conduct_conductcreditevent", "party_id", [p.pk for p in parties.values()]),
                ("accounts_userprofile", "user_id", [u.pk for u in users.values()]),
                ("conduct_partyreview", "party_id", [p.pk for p in parties.values()]),
            ):
                cursor.execute(
                    f'SELECT * FROM "{table}" WHERE "{clause}"=ANY(%s) ORDER BY id', [ids]
                )
                result[table] = [
                    dict(zip([c[0] for c in cursor.description], row, strict=True))
                    for row in cursor.fetchall()
                ]
        return result

    def flag(enabled):
        command = [
            "docker",
            "compose",
            "--env-file",
            args.compose_env,
            "-f",
            str(ROOT / "docker-compose.yml"),
            "-f",
            args.compose_overlay,
            "-p",
            args.project,
            "up",
            "-d",
            "--wait",
            "--force-recreate",
            "backend",
        ]
        env = dict(os.environ, TASK94_FLAG="true" if enabled else "false")
        with (output / ("flag-on.log" if enabled else "flag-off.log")).open("w") as log:
            subprocess.run(
                command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, check=True
            )

    def check(
        label,
        *,
        role="a",
        party="main",
        target="target",
        status=201,
        code=None,
        unchanged=False,
        payload=None,
        csrf="valid",
        profile_credit=None,
        events=None,
    ):
        before = snapshot()
        party_id = parties[party].pk if party in parties else party
        actual_status, body, headers = clients[role].send(
            "POST",
            f"/api/v1/parties/{party_id}/no-show-reports",
            {"reported_id": users[target].pk} if payload is None else payload,
            csrf=csrf,
        )
        after = snapshot()
        assert actual_status == status, (label, actual_status, body)
        assert "no-store" in (headers["Cache-Control"] or ""), (label, headers)
        if code:
            assert body["error"]["code"] == code, (label, body)
        if unchanged:
            assert before == after, label
        if status == 201:
            assert set(body) == {"data"} and set(body["data"]) == {"report"}
            assert set(body["data"]["report"]) == {"id", "party_id", "reported_id", "created_at"}
            assert body["data"]["report"]["reported_id"] == users[target].pk
        if profile_credit is not None:
            actual = next(
                p for p in after["accounts_userprofile"] if p["user_id"] == users[target].pk
            )
            assert actual["credit_score"] == profile_credit, (label, actual)
        if events is not None:
            assert len(after["conduct_conductcreditevent"]) == events
        # No-show must never rewrite existing star rows or star caches.
        assert before["conduct_partyreview"] == after["conduct_partyreview"]
        for old, new in zip(
            before["accounts_userprofile"], after["accounts_userprofile"], strict=True
        ):
            assert (old["rating_sum"], old["rating_count"]) == (
                new["rating_sum"],
                new["rating_count"],
            )
        report["cases"].append(
            {
                "id": label,
                "actor": role,
                "expected": {
                    "status": status,
                    "code": code,
                    "unchanged": unchanged,
                    "credit": profile_credit,
                    "events": events,
                },
                "actual": {"status": actual_status, "body": body, "headers": headers},
                "sql_before": before,
                "sql_after": after,
                "result": "Pass",
            }
        )
        (output / "results.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2, default=str)
        )
        print("PASS", label, flush=True)

    check("N01-flag-off-authenticated", status=404, code="NOT_FOUND", unchanged=True)
    check("N02-flag-off-anonymous", role="anonymous", status=404, code="NOT_FOUND", unchanged=True)
    check(
        "N03-flag-off-csrf-still-enforced",
        status=403,
        code="CSRF_FAILED",
        csrf="missing",
        unchanged=True,
    )
    flag(True)
    for role, status, code in (
        ("anonymous", 401, "AUTH_REQUIRED"),
        ("unverified", 403, "FORBIDDEN"),
        ("outsider", 403, "FORBIDDEN"),
        ("early", 403, "FORBIDDEN"),
    ):
        check("N04-" + role, role=role, status=status, code=code, unchanged=True)
    for label, payload in (
        ("self", {"reported_id": users["a"].pk}),
        ("nonparticipant", {"reported_id": users["outsider"].pk}),
        ("unknown-user", {"reported_id": 2147483646}),
        ("wrong-type", {"reported_id": True}),
        ("actor-injection", {"reported_id": users["target"].pk, "reporter_id": users["a"].pk}),
    ):
        check("N05-" + label, payload=payload, status=400, code="INVALID_INPUT", unchanged=True)
    for label, code in (
        ("future", "PARTY_NOT_COMPLETED"),
        ("cancelled", "PARTY_NOT_COMPLETED"),
        ("expired", "REPORT_WINDOW_CLOSED"),
    ):
        check("N06-" + label, party=label, status=409, code=code, unchanged=True)
    check("N07-missing-csrf", status=403, code="CSRF_FAILED", csrf="missing", unchanged=True)
    check("N08-missing-party", party=2147483646, status=404, code="NOT_FOUND", unchanged=True)
    check("N09-first-below-threshold", events=0)
    assert UserProfile.objects.get(user=users["target"]).credit_score is None
    check("N10-duplicate", status=409, code="REPORT_EXISTS", unchanged=True)
    check("N11-threshold-second-report", role="host", profile_credit=95, events=1)
    check("N12-third-report-no-second-deduction", role="b", profile_credit=95, events=1)
    check("N13-next-party-preserves-opening-balance", party="single", profile_credit=90, events=2)
    check("N14-negative-no-floor", party="negative", target="negative", profile_credit=-7, events=3)
    before = snapshot()
    flag(False)
    assert before == snapshot()
    check(
        "N15-disabled-retains-reports-and-credit",
        status=404,
        code="NOT_FOUND",
        unchanged=True,
        profile_credit=90,
        events=3,
    )
    report.update(
        finished_at=timezone.localtime().isoformat(),
        summary={"Pass": len(report["cases"]), "Fail": 0},
        source_sha256={
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in (
                "backend/conduct/views.py",
                "backend/conduct/services.py",
                "backend/conduct/policy.py",
                "backend/conduct/test_policy.py",
                "backend/conduct/test_reviews_unit.py",
                "scripts/us10-api-evidence.py",
                "scripts/us14-noshow-api-evidence.py",
            )
        },
        not_run=[
            "Human UAT/live TU login",
            "Exact seven-day microsecond over network (controlled-clock integration tests cover it)",
            "Production load",
        ],
    )
    (output / "results.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str)
    )
    print("DONE", report["summary"], flush=True)


if __name__ == "__main__":
    main()
