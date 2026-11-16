"""Task74 real loopback HTTP rehearsal on a disposable PostgreSQL database.

Assistant-operated evidence, not human UAT or a real TU login. Credentials
remain in memory. No runtime application code or production login is bypassed.
"""

import hashlib
import json
import os
import platform
import sys
from datetime import timedelta
from pathlib import Path
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from wsgiref.simple_server import WSGIRequestHandler, make_server

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from accounts.test_support import force_university_login  # noqa: E402
from django.conf import settings  # noqa: E402
from django.contrib.auth import get_user_model  # noqa: E402
from django.core.management import call_command  # noqa: E402
from django.core.wsgi import get_wsgi_application  # noqa: E402
from django.db import connection  # noqa: E402
from django.middleware.csrf import _get_new_csrf_string  # noqa: E402
from django.test import Client  # noqa: E402
from django.utils import timezone  # noqa: E402
from parties.models import JoinRequest, Party, PartyMembership  # noqa: E402
from venues.models import Sport, Venue  # noqa: E402


def main():
    if not settings.DEBUG or not connection.settings_dict["NAME"].startswith("s2_task74_"):
        raise SystemExit("Requires DEBUG and a disposable s2_task74_* database")
    output = ROOT / "docs/evidence/task74/http-sql.json"
    if not output.parent.is_dir():
        raise SystemExit("Mount docs at /app/docs before running; evidence directory is missing")
    # Refuse reuse instead of deleting or resetting data on a second execution.
    call_command("migrate", interactive=False, verbosity=0)
    if get_user_model().objects.exists() or Party.objects.exists():
        raise SystemExit("Requires an empty disposable DB; no data was reset")
    users = [
        get_user_model().objects.create_user(f"task74_{name}")
        for name in ["host", "member", "other"]
    ]
    host, member, other = users
    sport = Sport.objects.create(name="Task74 synthetic sport")
    venue = Venue.objects.create(name="Task74 synthetic venue", location_text="Test only")
    csrf = _get_new_csrf_string()
    cookies = {}
    for user in users:
        client = Client()
        force_university_login(client, user)
        cookies[user.pk] = client.cookies[settings.SESSION_COOKIE_NAME].value

    def fixture():
        now = timezone.now()
        party = Party.objects.create(
            host=host,
            sport=sport,
            venue=venue,
            title="Task74 fixture",
            starts_at=now + timedelta(hours=1),
            ends_at=now + timedelta(hours=2),
            capacity=3,
        )
        for user in [host, member]:
            PartyMembership.objects.create(party=party, user=user)
        JoinRequest.objects.create(
            party=party, user=member, status="Approved", decided_at=now, decided_by=host
        )
        return party

    def snapshot(party):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, capacity, cancelled_at FROM parties_party WHERE id=%s", [party.pk]
            )
            party_row = cursor.fetchone()
            cursor.execute(
                "SELECT id, user_id, joined_at, left_at FROM parties_partymembership "
                "WHERE party_id=%s ORDER BY id",
                [party.pk],
            )
            memberships = cursor.fetchall()
            cursor.execute(
                "SELECT id, user_id, status, created_at, decided_at, decided_by_id "
                "FROM parties_joinrequest WHERE party_id=%s ORDER BY id",
                [party.pk],
            )
            requests = cursor.fetchall()
        active = sum(row[3] is None for row in memberships)
        return {
            "party": party_row,
            "memberships": memberships,
            "requests": requests,
            "active_count": active,
            "remaining_slots": party_row[1] - active,
        }

    class QuietHandler(WSGIRequestHandler):
        def log_message(self, format, *args):
            pass

    observations = []
    # Port 0 selects an unused loopback port without publishing a host port.
    with make_server("127.0.0.1", 0, get_wsgi_application(), handler_class=QuietHandler) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"

        def send(party, *, actor=member, body=None, include_csrf=True, method="POST"):
            payload = {} if body is None else body
            cookie = f"{settings.CSRF_COOKIE_NAME}={csrf}"
            if actor is not None:
                cookie += f"; {settings.SESSION_COOKIE_NAME}={cookies[actor.pk]}"
            headers = {"Content-Type": "application/json", "Cookie": cookie}
            if include_csrf:
                headers["X-CSRFToken"] = csrf
            request = Request(
                f"{base}/api/v1/parties/{party.pk}/leave",
                data=json.dumps(payload).encode() if method == "POST" else None,
                headers=headers,
                method=method,
            )
            try:
                response = urlopen(request, timeout=10)
            except HTTPError as error:
                response = error
            with response:
                return response.status, json.load(response)

        def check(case, party, *, expected_status, expected_code=None, mutate=False, **kwargs):
            before = snapshot(party)
            status, response = send(party, **kwargs)
            after = snapshot(party)
            assert status == expected_status, (case, status, response)
            if expected_code:
                assert response["error"]["code"] == expected_code, (case, response)
            if not mutate:
                assert before == after, (case, "unexpected SQL mutation")
            else:
                assert after["active_count"] == before["active_count"] - 1
                assert after["remaining_slots"] == before["remaining_slots"] + 1
                assert before["party"] == after["party"]
                assert before["requests"] == after["requests"]
                assert len(before["memberships"]) == len(after["memberships"])
                for old, new in zip(before["memberships"], after["memberships"], strict=True):
                    assert old[:3] == new[:3]
                    if old[1] == member.pk:
                        assert old[3] is None and new[3] is not None
                    else:
                        assert old == new
                assert response["data"]["party_id"] == party.pk
                assert response["data"]["is_member"] is False
            observations.append(
                {
                    "case": case,
                    "expected": {
                        "status": expected_status,
                        "code": expected_code,
                        "mutation": mutate,
                    },
                    "actual": {"status": status, "response": response},
                    "before": before,
                    "after": after,
                    "result": "Pass",
                }
            )
            return response

        try:
            party = fixture()
            first = check("HTTP01-success", party, expected_status=200, mutate=True)
            retry = check("HTTP02-retry", party, expected_status=200)
            assert first == retry
            party = fixture()
            for case, kwargs, status, code in [
                ("HTTP03-anonymous", {"actor": None}, 401, "AUTH_REQUIRED"),
                ("HTTP04-forged-user", {"body": {"user_id": other.pk}}, 400, "INVALID_INPUT"),
                ("HTTP05-nonmember", {"actor": other}, 403, "NOT_MEMBER"),
                ("HTTP06-host", {"actor": host}, 403, "HOST_CANNOT_LEAVE"),
                ("HTTP07-csrf", {"include_csrf": False}, 403, "CSRF_FAILED"),
                ("HTTP08-method", {"method": "GET"}, 405, "METHOD_NOT_ALLOWED"),
            ]:
                check(case, party, expected_status=status, expected_code=code, **kwargs)
            now = timezone.now()
            party.starts_at = now - timedelta(minutes=1)
            party.ends_at = now + timedelta(hours=1)
            party.save(update_fields=["starts_at", "ends_at"])
            check("HTTP09-started", party, expected_status=409, expected_code="PARTY_STARTED")
            party.ends_at = now - timedelta(seconds=1)
            party.save(update_fields=["ends_at"])
            check("HTTP10-completed", party, expected_status=409, expected_code="PARTY_STARTED")
            party.cancelled_at = now
            party.save(update_fields=["cancelled_at"])
            check("HTTP11-cancelled", party, expected_status=409, expected_code="PARTY_CANCELLED")
        finally:
            server.shutdown()
            thread.join(timeout=10)

    sources = [
        "scripts/us4-api-evidence.py",
        "backend/parties/views.py",
        "backend/parties/services.py",
        "backend/accounts/decorators.py",
    ]
    report = {
        "kind": "assistant-operated real HTTP + SQL; NOT human manual UAT or TU login",
        "executed_at": timezone.localtime().isoformat(),
        "source_commit": os.environ.get("TASK74_SOURCE", "unspecified"),
        "source_sha256": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in sources
        },
        "python": platform.python_version(),
        "django": django.get_version(),
        "database": connection.settings_dict["NAME"],
        "vendor": connection.vendor,
        "exact_start_boundary": "See mock clock unit test; not claimed as HTTP timing proof",
        "observations": observations,
    }
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n")
    print(f"PASS: {len(observations)} real HTTP + SQL cases; credentials omitted")


if __name__ == "__main__":
    main()
