"""Task66 reproducible HTTP + SQL evidence, ONLY against an isolated local test DB.

Run with Django environment supplied by Compose. No real TU login is performed.
This is an assistant-operated integration rehearsal, not human UI/UAT evidence.
"""

import hashlib
import json
import os
import sys
from io import StringIO
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from accounts.models import UserProfile  # noqa: E402
from accounts.test_support import force_university_login  # noqa: E402
from django.conf import settings  # noqa: E402
from django.contrib.auth import get_user_model  # noqa: E402
from django.core.management import call_command  # noqa: E402
from django.db import connection  # noqa: E402
from django.test import Client  # noqa: E402
from django.utils import timezone  # noqa: E402
from parties.models import JoinRequest, Party, PartyMembership  # noqa: E402

base = os.environ.get("US6_EVIDENCE_URL", "http://127.0.0.1:8000")
parsed = urlparse(base)
if (
    not settings.DEBUG
    or not connection.settings_dict["NAME"].startswith("s2_task66_")
    or parsed.scheme != "http"
    or parsed.hostname not in {"127.0.0.1", "localhost"}
    or parsed.username
    or parsed.password
):
    raise SystemExit("Requires DEBUG, s2_task66_* disposable DB and loopback HTTP URL")

reference = timezone.localtime()
call_command("seed_sprint2", confirm_test_data=True, at=reference.isoformat(), stdout=StringIO())
host = get_user_model().objects.get(username="s2data_h")
client = Client()
force_university_login(client, host)
# Synthetic local session; keep cookie/CSRF values in memory, never in the evidence.
session_cookie = client.cookies[settings.SESSION_COOKIE_NAME].value
from django.middleware.csrf import _get_new_csrf_string  # noqa: E402

csrf = _get_new_csrf_string()
headers = {
    "Cookie": f"{settings.SESSION_COOKIE_NAME}={session_cookie}; csrftoken={csrf}",
    "X-CSRFToken": csrf,
    "Content-Type": "application/json",
}
report = {
    "kind": "assistant-operated real HTTP + PostgreSQL SQL; NOT manual UI/UAT or TU login",
    "started_at": reference.isoformat(),
    "source": os.environ.get("US6_EVIDENCE_SOURCE", "unspecified checkout"),
    "database": connection.settings_dict["NAME"],
    "python": sys.version.split()[0],
    "django": django.get_version(),
    "sql_sha256": hashlib.sha256(
        (ROOT / "database/seeds/us6_active_members.sql").read_bytes()
    ).hexdigest(),
    "source_sha256": {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in (
            "backend/parties/views.py",
            "backend/parties/urls.py",
            "backend/parties/test_members_database.py",
            "scripts/us6-db-api-evidence.py",
        )
    },
    "requests": [],
    "cases": [],
}
with connection.cursor() as cursor:
    cursor.execute("SELECT version()")
    report["postgresql"] = cursor.fetchone()[0]


def http(path, payload=None):
    request = Request(
        base + path,
        data=None if payload is None else json.dumps(payload).encode(),
        headers=headers,
        method="GET" if payload is None else "POST",
    )
    try:
        response = urlopen(request, timeout=10)
    except HTTPError as error:
        response = error
    raw = response.read()
    try:
        body = json.loads(raw)
    except ValueError:
        body = {"non_json_status": response.status}
    report["requests"].append(
        {
            "method": request.method,
            "path": path,
            "payload": payload,
            "status": response.status,
            "body": body,
        }
    )
    return response.status, body


def oracle(party):
    with connection.cursor() as cursor:
        cursor.execute((ROOT / "database/seeds/us6_active_members.sql").read_text(encoding="utf-8"))
        rows = [row for row in cursor.fetchall() if row[0] == party.pk]
    return {"ids": sorted(row[3] for row in rows), "count": len(rows)}


def compare(party):
    sql = oracle(party)
    status, body = http(f"/api/v1/parties/{party.pk}/members")
    detail_status, detail = http(f"/api/v1/parties/{party.pk}")
    data = body.get("data", {})
    ids = sorted(row["user_id"] for row in data.get("members", []))
    observed = {"ids": ids, "count": data.get("member_count")}
    return {
        "sql": sql,
        "api": observed,
        "detail_count": detail.get("data", {}).get("member_count"),
        "status": "PASS"
        if status == detail_status == 200
        and observed == sql
        and len(ids) == len(set(ids))
        and detail["data"]["member_count"] == sql["count"]
        else "FAIL",
    }


party = Party.objects.get(title="[S2-DATA] Open")
probe, _ = http(f"/api/v1/parties/{party.pk}/members")
if probe == 404:
    report["cases"].append(
        {
            "id": "DB66-M00",
            "status": "BLOCKED",
            "expected": "Members route available (200)",
            "actual": "HTTP 404",
        }
    )
else:
    for row in Party.objects.order_by("pk"):
        report["cases"].append({"id": "DB66-M01", "party": row.title, **compare(row)})
    before = [
        list(m.objects.order_by("pk").values()) for m in (PartyMembership, JoinRequest, UserProfile)
    ]
    compare(party)
    after = [
        list(m.objects.order_by("pk").values()) for m in (PartyMembership, JoinRequest, UserProfile)
    ]
    report["cases"].append(
        {
            "id": "DB66-M02",
            "expected": "GET preserves all fields/rows",
            "actual": "unchanged" if before == after else "changed",
            "status": "PASS" if before == after else "FAIL",
        }
    )
    pending = party.join_requests.get(user__username="s2data_a")
    decision_url = f"/api/v1/parties/{party.pk}/join-requests/{pending.pk}/decision"
    status, _ = http(decision_url, {"status": "Approved"})
    result = compare(party)
    pending.refresh_from_db()
    report["cases"].append(
        {
            "id": "DB66-M03",
            "expected": "200, Approved, SQL/API count 3",
            "decision_status": status,
            "request_status": pending.status,
            **result,
            "status": "PASS"
            if status == 200
            and pending.status == "Approved"
            and result["status"] == "PASS"
            and result["sql"]["count"] == 3
            else "FAIL",
        }
    )
    status, _ = http(decision_url, {"status": "Approved"})
    result = compare(party)
    report["cases"].append(
        {
            "id": "DB66-M04",
            "expected": "409; count stays 3",
            "decision_status": status,
            **result,
            "status": "PASS"
            if status == 409 and result["status"] == "PASS" and result["sql"]["count"] == 3
            else "FAIL",
        }
    )
    last = Party.objects.get(title="[S2-DATA] Last slot")
    rejected = last.join_requests.get(user__username="s2data_b")
    status, _ = http(
        f"/api/v1/parties/{last.pk}/join-requests/{rejected.pk}/decision", {"status": "Rejected"}
    )
    result = compare(last)
    rejected.refresh_from_db()
    report["cases"].append(
        {
            "id": "DB66-M05",
            "expected": "200, Rejected, count stays 2",
            "decision_status": status,
            "request_status": rejected.status,
            **result,
            "status": "PASS"
            if status == 200
            and rejected.status == "Rejected"
            and result["status"] == "PASS"
            and result["sql"]["count"] == 2
            else "FAIL",
        }
    )
    membership = party.memberships.get(user__username="s2data_m")
    original = (membership.pk, membership.joined_at)
    for attempt in (1, 2):
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE parties_partymembership SET left_at=%s WHERE id=%s",
                [reference, membership.pk],
            )
        result = compare(party)
        membership.refresh_from_db()
        history_ok = (
            membership.pk,
            membership.joined_at,
        ) == original and membership.left_at == reference
        history_ok &= party.join_requests.get(user=membership.user).status == "Approved"
        report["cases"].append(
            {
                "id": "DB66-M06",
                "attempt": attempt,
                "method": "SQL state preparation, NOT HTTP leave",
                "expected": "history retained, count 2 on both writes",
                "history_preserved": history_ok,
                "history_before": {"id": original[0], "joined_at": original[1]},
                "history_after": {
                    "id": membership.pk,
                    "joined_at": membership.joined_at,
                    "left_at": membership.left_at,
                    "request_status": party.join_requests.get(user=membership.user).status,
                },
                **result,
                "status": "PASS"
                if history_ok and result["status"] == "PASS" and result["sql"]["count"] == 2
                else "FAIL",
            }
        )
    UserProfile.objects.filter(user__username="s2data_a").delete()
    report["cases"].append(
        {"id": "DB66-M07", "expected": "Profile absent: active ID still present", **compare(party)}
    )
    party.memberships.filter(user=host).update(left_at=reference)
    report["cases"].append(
        {
            "id": "DB66-M08",
            "expected": "No inferred host: SQL/API/detail match",
            "policy": "Task60 actual rows; PR123 legacy fallback awaits team decision",
            **compare(party),
        }
    )
report["cases"].append(
    {
        "id": "DB66-M09",
        "status": "BLOCKED",
        "expected": "Real HTTP leave followed by SQL/API comparison",
        "actual": "Task70 leave endpoint is not available in the checked source",
    }
)
client.logout()
report["finished_at"] = timezone.localtime().isoformat()
print(json.dumps(report, ensure_ascii=True, indent=2, default=str))
# Nonzero means this is not an all-pass acceptance report. Keep the JSON as evidence.
raise SystemExit(1 if any(c["status"] != "PASS" for c in report["cases"]) else 0)
