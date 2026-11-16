"""Task56 assisted HTTP acceptance run against a disposable local PostgreSQL DB.

Requires DEBUG, DB name s2_task56_*, and --confirm-test-database. Sessions are
synthetic university fixtures, not TU login. Never log cookies or CSRF tokens.
Output is JSON on stdout; diagnostics belong on stderr. No existing rows deleted.
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import timedelta
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from accounts.models import UserProfile  # noqa: E402
from accounts.test_support import force_university_login  # noqa: E402
from django.conf import settings  # noqa: E402
from django.contrib.auth import get_user_model  # noqa: E402
from django.contrib.sessions.models import Session  # noqa: E402
from django.db import connection  # noqa: E402
from django.test import Client  # noqa: E402
from django.utils import timezone  # noqa: E402
from parties.models import JoinRequest, Party, PartyMembership  # noqa: E402
from venues.models import Sport, Venue  # noqa: E402


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Browser:
    def __init__(self, base, user=None, *, verified=True, expired=False):
        self.base = base
        self.cookies = {}
        if user is not None:
            fixture = Client()
            if verified:
                force_university_login(fixture, user)
            else:
                fixture.force_login(user)
            key = fixture.cookies[settings.SESSION_COOKIE_NAME].value
            if expired:
                Session.objects.filter(session_key=key).update(
                    expire_date=timezone.now() - timedelta(seconds=1)
                )
            self.cookies[settings.SESSION_COOKIE_NAME] = key
        status, body, _ = self.send("GET", "/api/v1/auth/csrf")
        if status != 200:
            raise RuntimeError(f"CSRF endpoint returned {status}")
        self.token = body["data"]["csrf_token"]

    def send(self, method, path, payload=None, *, raw=None, csrf="valid", origin=None):
        headers = {
            "Content-Type": "application/json",
            "Cookie": "; ".join(f"{key}={value}" for key, value in self.cookies.items()),
        }
        if method not in {"GET", "HEAD", "OPTIONS"} and csrf != "missing":
            headers["X-CSRFToken"] = self.token if csrf == "valid" else "invalid"
        if origin:
            headers["Origin"] = origin
        data = (
            raw
            if raw is not None
            else (json.dumps(payload).encode() if payload is not None else None)
        )
        request = Request(self.base + path, data=data, method=method, headers=headers)
        try:
            response = build_opener(NoRedirect()).open(request, timeout=10)
        except HTTPError as error:
            response = error
        with response:
            for cookie in response.headers.get_all("Set-Cookie", []):
                self.cookies.update({key: item.value for key, item in SimpleCookie(cookie).items()})
            try:
                body = json.loads(response.read())
            except ValueError:
                body = {"non_json": True}
            return (
                response.status,
                body,
                {
                    "Cache-Control": response.headers.get("Cache-Control"),
                    "Allow": response.headers.get("Allow"),
                },
            )


def snapshot():
    # Direct table reads provide an oracle independent of the business service.
    with connection.cursor() as cursor:
        result = {}
        for table in ("parties_party", "parties_joinrequest", "parties_partymembership"):
            cursor.execute(f'SELECT * FROM "{table}" ORDER BY id')
            columns = [item[0] for item in cursor.description]
            result[table] = [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
        return result


def digest(value):
    return hashlib.sha256(json.dumps(value, default=str, sort_keys=True).encode()).hexdigest()


def focus(snapshot_value, party):
    return {
        table: [
            row for row in rows if row["id" if table == "parties_party" else "party_id"] == party.pk
        ]
        for table, rows in snapshot_value.items()
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-test-database", action="store_true")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--source-commit", required=True)
    args = parser.parse_args()
    parsed = urlparse(args.base_url)
    if (
        not args.confirm_test_database
        or not settings.DEBUG
        or connection.vendor != "postgresql"
        or not connection.settings_dict["NAME"].startswith("s2_task56_")
        or parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost"}
        or parsed.username
        or parsed.password
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise SystemExit(
            "Requires confirmation, DEBUG, s2_task56_* PostgreSQL DB and loopback HTTP URL"
        )

    prefix = "t56_" + uuid4().hex[:10]
    now = timezone.now()
    users = {
        role: get_user_model().objects.create_user(f"{prefix}_{role}")
        for role in ("host", "applicant", "outsider", "inactive")
    }
    for role, user in users.items():
        UserProfile.objects.create(user=user, display_name=f"Task56 {role}")
    browsers = {role: Browser(args.base_url.rstrip("/"), user) for role, user in users.items()}
    users["inactive"].is_active = False
    users["inactive"].save(update_fields=["is_active"])
    browsers["anonymous"] = Browser(args.base_url)
    browsers["unverified"] = Browser(args.base_url, users["host"], verified=False)
    browsers["expired"] = Browser(args.base_url, users["host"], expired=True)
    sport = Sport.objects.create(name=prefix)
    venue = Venue.objects.create(name=prefix, location_text="Synthetic Task56 fixture")

    report = {
        "kind": "assistant-operated real HTTP + SQL; not human UAT or live TU authentication",
        "started_at": timezone.localtime(now).isoformat(),
        "source_commit": args.source_commit,
        "database": connection.settings_dict["NAME"],
        "base_url": args.base_url,
        "python": sys.version.split()[0],
        "django": django.get_version(),
        "fixture_prefix": prefix,
        "source_sha256": {
            path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
            for path in (
                "scripts/us10-api-evidence.py",
                "backend/parties/services.py",
                "backend/parties/views.py",
                "backend/parties/urls.py",
                "backend/accounts/decorators.py",
                "backend/parties/test_decision_unit.py",
            )
        },
        "cases": [],
    }
    with connection.cursor() as cursor:
        cursor.execute("SELECT version()")
        report["postgresql"] = cursor.fetchone()[0]

    def fixture(label, state="Open"):
        party = Party.objects.create(
            host=users["host"],
            sport=sport,
            venue=venue,
            title=f"{prefix} {label}",
            capacity=2,
            starts_at=now + timedelta(days=1),
            ends_at=now + timedelta(days=1, hours=1),
        )
        PartyMembership.objects.create(party=party, user=users["host"])
        if state == "Full":
            PartyMembership.objects.create(party=party, user=users["outsider"])
        elif state == "Cancelled":
            party.cancelled_at = now
        elif state == "InProgress":
            party.starts_at = now - timedelta(hours=1)
        elif state == "Completed":
            party.starts_at, party.ends_at = now - timedelta(hours=2), now - timedelta(hours=1)
        party.save()
        pending = JoinRequest.objects.create(party=party, user=users["applicant"])
        return party, pending

    def run(
        case,
        party,
        path,
        *,
        actor="host",
        method="POST",
        payload=None,
        code=None,
        status=200,
        unchanged=False,
        check=None,
        expected="",
        **options,
    ):
        before = snapshot()
        actual_status, body, headers = browsers[actor].send(method, path, payload, **options)
        after = snapshot()
        checks = {
            "status": actual_status == status,
            "json": "non_json" not in body,
            "no_store": "no-store" in (headers["Cache-Control"] or ""),
        }
        if code:
            checks["error_code"] = body.get("error", {}).get("code") == code
        if unchanged:
            checks["no_domain_mutation"] = before == after
        if check:
            checks.update(check(body, before, after))
        report["cases"].append(
            {
                "id": case,
                "executed_at": timezone.localtime().isoformat(),
                "actor": actor,
                "request": {
                    "method": method,
                    "path": path,
                    "payload": payload,
                    "options": {
                        key: (value.decode() if isinstance(value, bytes) else value)
                        for key, value in options.items()
                    },
                },
                "expected": {
                    "status": status,
                    "code": code,
                    "unchanged": unchanged,
                    "description": expected,
                },
                "actual": {"status": actual_status, "body": body, "headers": headers},
                "sql_before": focus(before, party),
                "sql_after": focus(after, party),
                "domain_before_sha256": digest(before),
                "domain_after_sha256": digest(after),
                "checks": checks,
                "result": "Pass" if all(checks.values()) else "Fail",
            }
        )

    def decision_path(party, pending):
        return f"/api/v1/parties/{party.pk}/join-requests/{pending.pk}/decision"

    def outcome(party, pending, state):
        def check(body, before, after):
            row = next(row for row in after["parties_joinrequest"] if row["id"] == pending.pk)
            members = [
                row
                for row in after["parties_partymembership"]
                if row["party_id"] == party.pk and row["left_at"] is None
            ]
            checks = {
                "exact_body": body == {"data": {"id": pending.pk, "status": state}},
                "decision": row["status"] == state
                and row["decided_by_id"] == users["host"].pk
                and row["decided_at"] is not None,
                "party_unchanged": before["parties_party"] == after["parties_party"],
            }
            if state == "Approved":
                checks["applicant_active_once"] = (
                    sum(m["user_id"] == users["applicant"].pk for m in members) == 1
                )
                checks["one_member_added"] = (
                    len(after["parties_partymembership"])
                    == len(before["parties_partymembership"]) + 1
                )
                checks["capacity_respected"] = len(members) <= party.capacity
            else:
                checks["members_unchanged"] = (
                    before["parties_partymembership"] == after["parties_partymembership"]
                )
            return checks

        return check

    party, pending = fixture("permissions")
    path = decision_path(party, pending)
    pending_path = f"/api/v1/parties/{party.pk}/join-requests/pending"
    run(
        "QA-US10-API-01/host",
        party,
        pending_path,
        method="GET",
        unchanged=True,
        check=lambda body, *_: {
            "public_pending": len(body.get("data", [])) == 1
            and set(body["data"][0]) == {"id", "display_name", "created_at"}
            and body["data"][0]["id"] == pending.pk
        },
    )
    run(
        "QA-US10-API-01/nonhost",
        party,
        pending_path,
        actor="outsider",
        method="GET",
        status=403,
        code="FORBIDDEN",
        unchanged=True,
    )
    for actor, status, code in (
        ("anonymous", 401, "AUTH_REQUIRED"),
        ("unverified", 403, "FORBIDDEN"),
        ("inactive", 401, "AUTH_REQUIRED"),
        ("expired", 401, "AUTH_REQUIRED"),
        ("outsider", 403, "FORBIDDEN"),
        ("applicant", 403, "FORBIDDEN"),
    ):
        for state in ("Approved", "Rejected"):
            run(
                f"QA-US10-API-08/{actor}-{state}",
                party,
                path,
                actor=actor,
                payload={"status": state},
                status=status,
                code=code,
                unchanged=True,
            )
    other_party, _ = fixture("other-party")
    for state in ("Approved", "Rejected"):
        run(
            f"QA-US10-API-05/cross-party-{state}",
            party,
            decision_path(other_party, pending),
            payload={"status": state},
            status=404,
            code="NOT_FOUND",
            unchanged=True,
        )
    for label, bad_path in (
        ("party", f"/api/v1/parties/0/join-requests/{pending.pk}/decision"),
        ("request", f"/api/v1/parties/{party.pk}/join-requests/0/decision"),
    ):
        run(
            f"QA-US10-API-05/missing-{label}",
            party,
            bad_path,
            payload={"status": "Approved"},
            status=404,
            code="NOT_FOUND",
            unchanged=True,
        )
    for label, raw in (
        ("json", b"{"),
        ("array", b'{"status":[]}'),
        ("object", b'{"status":{}}'),
        ("status", b'{"status":"Pending"}'),
        ("actor", b'{"status":"Approved","user_id":99}'),
    ):
        run(
            f"QA-US10-API-07/input-{label}",
            party,
            path,
            raw=raw,
            status=400,
            code="INVALID_INPUT",
            unchanged=True,
        )
    for label, options in (
        ("csrf-missing", {"csrf": "missing"}),
        ("csrf-wrong", {"csrf": "wrong"}),
        ("origin", {"origin": "https://untrusted.invalid"}),
    ):
        run(
            f"QA-US10-API-08/{label}",
            party,
            path,
            payload={"status": "Rejected"},
            status=403,
            code="CSRF_FAILED",
            unchanged=True,
            **options,
        )
    run(
        "QA-US10-API-08/method",
        party,
        path,
        method="GET",
        status=405,
        code="METHOD_NOT_ALLOWED",
        unchanged=True,
    )

    for state in ("Full", "InProgress", "Completed", "Cancelled"):
        p, q = fixture(state, state)
        for decision in ("Approved", "Rejected"):
            allowed = state == "Full" and decision == "Rejected"
            code = {"Full": "PARTY_FULL", "Cancelled": "PARTY_CANCELLED"}.get(
                state, "PARTY_STARTED"
            )
            run(
                f"QA-US10-API-07/{state}-{decision}",
                p,
                decision_path(p, q),
                payload={"status": decision},
                status=200 if allowed else 409,
                code=None if allowed else code,
                unchanged=not allowed,
                check=outcome(p, q, "Rejected") if allowed else None,
            )

    p, q = fixture("approve")
    path = decision_path(p, q)
    run(
        "QA-US10-API-02/approve",
        p,
        path,
        payload={"status": "Approved"},
        check=outcome(p, q, "Approved"),
    )
    for state in ("Approved", "Rejected"):
        run(
            f"QA-US10-API-06/after-approve-{state}",
            p,
            path,
            payload={"status": state},
            status=409,
            code="REQUEST_DECIDED",
            unchanged=True,
        )

    p, q = fixture("reapply")
    path = decision_path(p, q)
    run(
        "QA-US10-API-04/reject",
        p,
        path,
        payload={"status": "Rejected"},
        check=outcome(p, q, "Rejected"),
    )
    for state in ("Approved", "Rejected"):
        run(
            f"QA-US10-API-06/after-reject-{state}",
            p,
            path,
            payload={"status": state},
            status=409,
            code="REQUEST_DECIDED",
            unchanged=True,
        )

    def reopened(body, before, after):
        row = next(row for row in after["parties_joinrequest"] if row["id"] == q.pk)
        return {
            "same_id": body.get("data", {}).get("id") == q.pk,
            "pending": row["status"] == "Pending"
            and row["decided_at"] is None
            and row["decided_by_id"] is None,
            "row_count": len(before["parties_joinrequest"]) == len(after["parties_joinrequest"]),
            "no_member_change": before["parties_partymembership"]
            == after["parties_partymembership"],
        }

    run(
        "QA-US10-API-04/reapply",
        p,
        f"/api/v1/parties/{p.pk}/join-requests",
        actor="applicant",
        payload={},
        status=201,
        check=reopened,
    )
    run(
        "QA-US10-API-04/approve-reopened",
        p,
        path,
        payload={"status": "Approved"},
        check=outcome(p, q, "Approved"),
    )
    for label, url, check in (
        ("pending", f"/api/v1/parties/{p.pk}/join-requests/pending", lambda b: b == {"data": []}),
        (
            "detail",
            f"/api/v1/parties/{p.pk}",
            lambda b: (
                (b["data"]["member_count"], b["data"]["remaining_slots"], b["data"]["state"])
                == (2, 0, "Full")
            ),
        ),
    ):
        run(
            f"QA-US10-API-04/read-{label}",
            p,
            url,
            method="GET",
            unchanged=True,
            check=lambda body, *_, predicate=check: {"read_result": predicate(body)},
        )

    # Keep the pre-logout cookies to simulate a second tab with the old session.
    stale = browsers["host"].cookies.copy()
    run("QA-US10-API-08/logout", party, "/api/v1/auth/logout", payload={}, unchanged=True)
    browsers["host"].cookies = stale
    run(
        "QA-US10-API-08/stale-cookie",
        party,
        decision_path(party, pending),
        payload={"status": "Approved"},
        status=401,
        code="AUTH_REQUIRED",
        unchanged=True,
    )
    report["finished_at"] = timezone.localtime().isoformat()
    report["summary"] = {
        result: sum(case["result"] == result for case in report["cases"])
        for result in ("Pass", "Fail")
    }
    report["not_run"] = [
        "Live TU login",
        "Human manual sign-off / browser UAT",
        "Exact starts_at boundary over HTTP (controlled-clock unit/IT cover it)",
    ]
    print(json.dumps(report, default=str, ensure_ascii=False, indent=2))
    return 1 if report["summary"]["Fail"] else 0


if __name__ == "__main__":
    sys.exit(main())
