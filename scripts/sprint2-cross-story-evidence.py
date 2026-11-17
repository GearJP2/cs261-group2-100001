"""Task96: integrated native browser/HTTP/SQL; disposable PostgreSQL only."""

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import time, timedelta
from pathlib import Path
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
from parties.models import Party  # noqa: E402
from playwright.sync_api import expect, sync_playwright  # noqa: E402
from venues.models import Sport, Venue, VenueOpeningHour, VenueSport  # noqa: E402


def main():
    assert (
        settings.DEBUG
        and connection.vendor == "postgresql"
        and connection.settings_dict["NAME"].startswith("s2_task96_")
    )
    assert os.environ.get("TASK96_CONFIRM_TEST_DATABASE") == "yes"
    out = Path(os.environ["TASK96_OUTPUT"])
    assert not out.exists()
    out.mkdir(parents=True)
    base = "http://127.0.0.1:25896"
    spec = importlib.util.spec_from_file_location(
        "existing_browser", ROOT / "scripts/us10-api-evidence.py"
    )
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    prefix = "QA96" + uuid4().hex[:6]
    users = {
        r: get_user_model().objects.create_user(prefix + r, email=prefix + r + "@example.invalid")
        for r in ["host", "a", "b", "c", "outsider", "unverified"]
    }
    for r, u in users.items():
        UserProfile.objects.create(user=u, display_name="QA96 " + r)
    clients = {r: helper.Browser(base, u, verified=r != "unverified") for r, u in users.items()}
    clients["anonymous"] = helper.Browser(base)
    sport = Sport.objects.create(name=prefix)
    venue = Venue.objects.create(name=prefix, location_text="Synthetic QA96", venue_type="Indoor")
    VenueSport.objects.create(venue=venue, sport=sport)
    start = (timezone.localtime() + timedelta(days=2)).replace(
        hour=10, minute=0, second=0, microsecond=0
    )
    VenueOpeningHour.objects.create(
        venue=venue, weekday=start.weekday(), opens_at=time(8), closes_at=time(20)
    )
    payload = dict(
        title=prefix + " flow",
        sport_id=sport.pk,
        venue_id=venue.pk,
        starts_at=start.isoformat(),
        ends_at=(start + timedelta(hours=1)).isoformat(),
        capacity=3,
    )
    ids = []
    cases = []
    responses = []
    errors = []
    transitions = []
    pool = ThreadPoolExecutor(max_workers=1)

    def read_sql():
        result = {}
        with connection.cursor() as cur:
            for table, col, values in [
                ("parties_party", "id", ids),
                ("parties_partymembership", "party_id", ids),
                ("parties_joinrequest", "party_id", ids),
                ("conduct_partyreview", "party_id", ids),
                ("conduct_noshowreport", "party_id", ids),
                ("conduct_conductcreditevent", "party_id", ids),
                ("accounts_userprofile", "user_id", [u.pk for u in users.values()]),
            ]:
                cur.execute(f'SELECT * FROM "{table}" WHERE "{col}"=ANY(%s) ORDER BY id', [values])
                result[table] = [
                    dict(zip([c[0] for c in cur.description], row, strict=True))
                    for row in cur.fetchall()
                ]
        return result

    def sql():
        return pool.submit(read_sql).result()

    def save(label, expected, actual, before):
        cases.append(
            dict(
                id=label,
                expected=expected,
                actual=actual,
                before=before,
                after=sql(),
                status="PASS",
            )
        )
        print("PASS", label, flush=True)
        (out / "results.json").write_text(
            json.dumps(
                dict(cases=cases, responses=responses, fixture_transitions=transitions),
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )

    def api(role, method, path, data=None, status=200, code=None, csrf="valid", unchanged=False):
        before = sql()
        actual, body, headers = clients[role].send(method, "/api/v1" + path, data, csrf=csrf)
        responses.append(
            dict(
                kind="real HTTP",
                role=role,
                method=method,
                path="/api/v1" + path,
                status=actual,
                expected_status=status,
                response=body,
                cache_control=headers.get("Cache-Control"),
            )
        )
        assert actual == status, (role, method, path, status, actual, body)
        if code:
            assert body["error"]["code"] == code, (path, body)
        if unchanged:
            assert before == sql(), path
        return body

    def count(party, expected):
        snapshot = sql()
        active = [
            r
            for r in snapshot["parties_partymembership"]
            if r["party_id"] == party and r["left_at"] is None
        ]
        assert len(active) == expected, (party, active)
        body = api("host", "GET", f"/parties/{party}/members")["data"]
        assert body["member_count"] == expected and {r["user_id"] for r in body["members"]} == {
            r["user_id"] for r in active
        }
        detail = api("host", "GET", f"/parties/{party}")["data"]
        assert (
            detail["member_count"] == expected
            and detail["remaining_slots"] == detail["capacity"] - expected
        )
        return body

    def flag(enabled):
        command = [
            "docker",
            "compose",
            "--env-file",
            "/tmp/task96.env",
            "-f",
            str(ROOT / "docker-compose.yml"),
            "-f",
            "/tmp/task96.compose.yml",
            "-p",
            "s2-task96-cross",
            "up",
            "-d",
            "--wait",
            "--force-recreate",
            "backend",
        ]
        with (out / ("flag-on.log" if enabled else "flag-off.log")).open("w") as log:
            subprocess.run(
                command,
                cwd=ROOT,
                env=dict(os.environ, TASK96_FLAG="true" if enabled else "false"),
                stdout=log,
                stderr=subprocess.STDOUT,
                check=True,
            )

    before = sql()
    api("anonymous", "GET", "/me", status=401, unchanged=True)
    api("unverified", "GET", "/me", status=403, unchanged=True)
    api("a", "GET", "/me")
    api("anonymous", "POST", "/auth/login", {}, status=400, unchanged=True)
    assert not settings.TU_APPLICATION_KEY
    api(
        "anonymous",
        "POST",
        "/auth/login",
        dict(username="synthetic", password="not-a-real-password"),
        status=502,
        code="UNIVERSITY_API_UNAVAILABLE",
        unchanged=True,
    )
    save(
        "R01-auth-regression",
        "401/403 session guards; synthetic verified/me200; invalid400; absent TU key502 (live login Not run)",
        {"guards": "PASS", "live_TU": "Not run"},
        before,
    )
    before = sql()
    body = api("host", "POST", "/parties", payload, status=201)
    party = body["data"]["id"]
    ids.append(party)
    count(party, 1)
    save("F01-create", "real Host create201/one Host row/count1/2 slots", {"party": party}, before)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            executable_path=os.environ["TASK96_CHROME"], args=["--no-sandbox"]
        )

        def context(role):
            ctx = browser.new_context(viewport={"width": 1280, "height": 900})
            ctx.add_cookies(
                [
                    dict(
                        name="sessionid",
                        value=clients[role].cookies["sessionid"],
                        domain="127.0.0.1",
                        path="/",
                    )
                ]
            )
            return ctx

        def page_for(ctx):
            page = ctx.new_page()
            page.on("pageerror", lambda e: errors.append(str(e)))

            def record(resp):
                if "/api/v1/parties" in resp.url:
                    try:
                        body = resp.json()
                    except Exception:
                        body = {"non_json": True}
                    responses.append(
                        dict(
                            kind="native browser HTTP",
                            method=resp.request.method,
                            path=resp.url.replace(base, ""),
                            status=resp.status,
                            response=body,
                        )
                    )

            page.on("response", record)
            return page

        hctx = context("host")
        actx = context("a")
        hp = page_for(hctx)
        ap = page_for(actx)
        before = sql()
        ap.goto(base + "/search/")
        ap.wait_for_load_state("networkidle")
        ap.locator("[data-search-query]").fill(payload["title"])
        ap.locator("[data-search-form] button[type=submit]").click()
        expect(ap.locator(".search-card h3")).to_have_text([payload["title"]])
        ap.locator(".search-card-link").click()
        ap.wait_for_load_state("networkidle")
        with ap.expect_response(
            lambda r: (
                r.request.method == "POST" and r.url.endswith(f"/parties/{party}/join-requests")
            )
        ) as pending:
            ap.get_by_role("button", name="ขอเข้าร่วม", exact=True).click()
        response = pending.value
        assert response.status == 201
        request_a = api("a", "GET", f"/parties/{party}/join-requests/me")["data"]["id"]
        ap.wait_for_load_state("networkidle")
        expect(ap.get_by_text("ส่งคำขอเข้าร่วมแล้ว กำลังรอการตอบรับ", exact=True)).to_be_visible()
        count(party, 1)
        ap.screenshot(path=str(out / "pending-no-seat.png"), full_page=True)
        save(
            "F02-search-to-pending",
            "native Search→Detail→join201 Pending; Host count1 unchanged",
            {"request": request_a, "members": 1},
            before,
        )
        before = sql()
        hp.goto(base + "/my-parties/")
        hp.wait_for_load_state("networkidle")
        with hp.expect_response(
            lambda r: (
                r.request.method == "POST"
                and r.url.endswith(f"/join-requests/{request_a}/decision")
            )
        ) as pending:
            hp.locator(f'.btn-approve[data-request-id="{request_a}"]').click()
        assert pending.value.status == 200
        panel = hp.locator(f'[data-party-members="{party}"]').first
        expect(panel.locator("[data-member-count]")).to_have_text("2")
        count(party, 2)
        hp.wait_for_timeout(1100)
        hp.wait_for_load_state("networkidle")
        ap.reload()
        ap.wait_for_load_state("networkidle")
        expect(ap.get_by_text("คุณเป็นสมาชิกของปาร์ตี้นี้แล้ว", exact=True)).to_be_visible()
        save(
            "F03-approve-to-members",
            "native Host Approve200→Members refresh2→Member Detail updated",
            {"members": 2},
            before,
        )
        before = sql()
        body = api("b", "POST", f"/parties/{party}/join-requests", {}, status=201)
        request_b = body["data"]["id"]
        count(party, 2)
        hp.reload()
        hp.wait_for_load_state("networkidle")
        with hp.expect_response(
            lambda r: (
                r.request.method == "POST"
                and r.url.endswith(f"/join-requests/{request_b}/decision")
            )
        ) as pending:
            hp.locator(f'.btn-reject[data-request-id="{request_b}"]').click()
        assert pending.value.status == 200
        count(party, 2)
        api("b", "GET", f"/parties/{party}/members", status=403, unchanged=True)
        save(
            "F04-reject-no-seat",
            "B Pending/reject200 never creates seat; B members403",
            {"members": 2, "rejected": request_b},
            before,
        )
        before = sql()
        body = api("c", "POST", f"/parties/{party}/join-requests", {}, status=201)
        request_c = body["data"]["id"]
        api(
            "host",
            "POST",
            f"/parties/{party}/join-requests/{request_c}/decision",
            {"status": "Approved"},
        )
        count(party, 3)
        api("outsider", "POST", f"/parties/{party}/join-requests", {}, status=409, unchanged=True)
        save(
            "F05-full-policy",
            "C approval fills final slot; outsider join409/no mutation",
            {"members": 3},
            before,
        )
        before = sql()
        ap.goto(base + "/my-parties/")
        ap.wait_for_load_state("networkidle")
        ap.locator('[data-myparty-tab="joined"]').click()
        expect(ap.locator(f'[data-party-members="{party}"] [data-member-count]')).to_have_text("3")
        ap.locator(f'[data-leave-party="{party}"]').click()
        with ap.expect_response(
            lambda r: r.request.method == "POST" and r.url.endswith(f"/parties/{party}/leave")
        ) as pending:
            ap.locator("[data-leave-confirm]").click()
        assert pending.value.status == 200
        expect(ap.locator("[data-leave-message]")).to_contain_text("ถอนตัวสำเร็จ")
        assert ap.locator(f'[data-party-members="{party}"] [data-member-list] li').count() == 0
        count(party, 2)
        api("a", "GET", f"/parties/{party}/members", status=403, unchanged=True)
        after = sql()
        old_members = len(after["parties_partymembership"])
        left_row = next(
            r
            for r in after["parties_partymembership"]
            if r["party_id"] == party and r["user_id"] == users["a"].pk
        )
        assert left_row["left_at"] is not None
        ap.screenshot(path=str(out / "leave-restores-slot.png"), full_page=True)
        save(
            "F06-leave-to-open",
            "native Leave200→softleft/403 clears list; count2/one slot",
            {"members": 2, "left_row": left_row["id"]},
            before,
        )
        before = sql()
        api("a", "POST", f"/parties/{party}/leave", {})
        assert before == sql()
        save(
            "F07-leave-idempotent",
            "retry200 keeps same left_at/history/count",
            {"unchanged": True},
            before,
        )
        before = sql()
        ap.goto(base + "/search/")
        ap.wait_for_load_state("networkidle")
        ap.locator("[data-search-query]").fill(payload["title"])
        ap.locator("[data-search-form] button[type=submit]").click()
        expect(ap.locator(".search-card h3")).to_have_text([payload["title"]])
        ap.locator(".search-card-link").click()
        ap.wait_for_load_state("networkidle")
        with ap.expect_response(
            lambda r: (
                r.request.method == "POST" and r.url.endswith(f"/parties/{party}/join-requests")
            )
        ) as pending:
            ap.get_by_role("button", name="ขอเข้าร่วม", exact=True).click()
        assert pending.value.status == 201
        request_again = api("a", "GET", f"/parties/{party}/join-requests/me")["data"]["id"]
        count(party, 2)
        api(
            "host",
            "POST",
            f"/parties/{party}/join-requests/{request_again}/decision",
            {"status": "Approved"},
        )
        count(party, 3)
        after = sql()
        row = next(
            r
            for r in after["parties_partymembership"]
            if r["party_id"] == party and r["user_id"] == users["a"].pk
        )
        assert (
            row["id"] == left_row["id"]
            and row["left_at"] is None
            and len(after["parties_partymembership"]) == old_members
        )
        save(
            "F08-rejoin-history",
            "Search Open again→new Pending→approve; reuse membership row/no duplicate/count3",
            {"members": 3, "same_membership_id": row["id"]},
            before,
        )
        before = sql()
        api(
            "outsider",
            "POST",
            f"/parties/{party}/join-requests/{request_again}/decision",
            {"status": "Approved"},
            status=403,
            unchanged=True,
        )
        api(
            "host",
            "POST",
            f"/parties/{party}/join-requests/{request_again}/decision",
            {"status": "Approved"},
            status=409,
            unchanged=True,
        )
        api("a", "POST", f"/parties/{party}/leave", {}, status=403, csrf="missing", unchanged=True)
        save(
            "F09-guards",
            "nonHost decision403, repeated decision409, missingCSRF403 preserve all domain rows",
            {"unchanged": True},
            before,
        )
        before = sql()
        api(
            "a",
            "POST",
            f"/parties/{party}/reviews",
            {"reviewee_id": users["host"].pk, "rating": 5, "comment": "too early"},
            status=409,
            code="PARTY_NOT_COMPLETED",
            unchanged=True,
        )
        save(
            "F10-review-before-end",
            "review409 before completion/no rows/cache changes",
            {"http": 409},
            before,
        )
        # Explicit QA fixture transition only; no wall-clock waiting or fake API state.
        before = sql()
        completed = timezone.now() - timedelta(seconds=1)
        pool.submit(
            lambda: Party.objects.filter(pk=party).update(
                starts_at=completed - timedelta(hours=1), ends_at=completed
            )
        ).result()
        transitions.append(
            dict(
                kind="fixture clock transition, not business API",
                party_id=party,
                fields=["starts_at", "ends_at"],
                before=before["parties_party"],
                after=sql()["parties_party"],
            )
        )
        before = sql()
        ap.goto(base + "/my-parties/")
        ap.wait_for_load_state("networkidle")
        ap.locator('[data-myparty-tab="history"]').click()
        dialog = ap.locator(f"#review-dialog-{party}")
        ap.locator(f'[data-open-review="review-dialog-{party}"]').click()
        dialog.locator("select").select_option(str(users["host"].pk))
        dialog.locator('[name=rating][value="5"]').check()
        dialog.locator("textarea").fill("Task96 integrated review")
        with ap.expect_response(
            lambda r: r.request.method == "POST" and r.url.endswith(f"/parties/{party}/reviews")
        ) as pending:
            dialog.locator("[type=submit]").click()
        assert pending.value.status == 201
        expect(dialog.locator("[data-review-message]")).to_have_text("บันทึกรีวิวเรียบร้อยแล้ว")
        profile = next(r for r in sql()["accounts_userprofile"] if r["user_id"] == users["host"].pk)
        assert (profile["rating_sum"], profile["rating_count"], profile["credit_score"]) == (
            5,
            1,
            None,
        )
        ap.screenshot(path=str(out / "completed-review.png"), full_page=True)
        save(
            "F11-completed-native-review",
            "Completed History→native review201→one row/cache5,1/creditNULL",
            {"http": 201, "rating_sum": 5, "rating_count": 1},
            before,
        )
        before = sql()
        api(
            "a",
            "POST",
            f"/parties/{party}/reviews",
            {"reviewee_id": users["host"].pk, "rating": 1, "comment": "duplicate"},
            status=409,
            code="REVIEW_EXISTS",
            unchanged=True,
        )
        api(
            "b",
            "POST",
            f"/parties/{party}/reviews",
            {"reviewee_id": users["host"].pk, "rating": 5, "comment": "not participant"},
            status=403,
            unchanged=True,
        )
        api(
            "c",
            "POST",
            f"/parties/{party}/reviews",
            {"reviewee_id": users["a"].pk, "rating": 4, "comment": "eligible C"},
            status=201,
        )
        save(
            "F12-review-eligibility-unique",
            "duplicate409/rejectedB403 unchanged; eligibleC201 independent review",
            {"reviews": len(sql()["conduct_partyreview"])},
            before,
        )
        before = sql()
        ap.goto(base + f"/users/{users['host'].pk}/")
        ap.wait_for_load_state("networkidle")
        expect(ap.locator("[data-review-summary]")).to_contain_text("5.0")
        expect(ap.locator(".review-comment")).to_have_text("Task96 integrated review")
        profilebody = api("a", "GET", f"/users/{users['host'].pk}/profile")["data"]
        assert profilebody["display_name"] == "QA96 host"
        ap.screenshot(path=str(out / "profile-review-summary.png"), full_page=True)
        assert before == sql()
        save(
            "F13-profile-summary",
            "native Profile shows actual review5.0/comment; reads do not mutate DB",
            {"summary": "5.0"},
            before,
        )
        before = sql()
        api(
            "a",
            "POST",
            f"/parties/{party}/no-show-reports",
            {"reported_id": users["host"].pk},
            status=404,
            unchanged=True,
        )
        flag(True)
        assert before == sql()
        save(
            "F14-no-show-flag-off",
            "default off404/no mutation; enable only dedicated test backend",
            {"off": 404},
            before,
        )
        before = sql()
        stars = before["conduct_partyreview"]
        api(
            "a",
            "POST",
            f"/parties/{party}/no-show-reports",
            {"reported_id": users["host"].pk},
            status=201,
        )
        profile = next(r for r in sql()["accounts_userprofile"] if r["user_id"] == users["host"].pk)
        assert profile["credit_score"] is None
        api(
            "c",
            "POST",
            f"/parties/{party}/no-show-reports",
            {"reported_id": users["host"].pk},
            status=201,
        )
        profile = next(r for r in sql()["accounts_userprofile"] if r["user_id"] == users["host"].pk)
        assert (
            profile["credit_score"] == 95
            and profile["rating_sum"] == 5
            and profile["rating_count"] == 1
            and len(sql()["conduct_conductcreditevent"]) == 1
        )
        assert stars == sql()["conduct_partyreview"]
        save(
            "F15-no-show-credit-isolation",
            "2 eligible reporters→one credit95 event; star reviews/cache unchanged",
            {"credit": 95, "events": 1},
            before,
        )
        before = sql()
        api(
            "a",
            "POST",
            f"/parties/{party}/no-show-reports",
            {"reported_id": users["host"].pk},
            status=409,
            unchanged=True,
        )
        api(
            "b",
            "POST",
            f"/parties/{party}/no-show-reports",
            {"reported_id": users["host"].pk},
            status=403,
            unchanged=True,
        )
        flag(False)
        assert before == sql()
        api(
            "a",
            "POST",
            f"/parties/{party}/no-show-reports",
            {"reported_id": users["host"].pk},
            status=404,
            unchanged=True,
        )
        save(
            "F16-no-show-duplicate-and-off",
            "duplicate409/B403 no double deduction; restore false preserves ledger/credit",
            {"credit": 95, "flag": False},
            before,
        )
        before = sql()
        extra = dict(payload, title=prefix + " regression")
        body = api("host", "POST", "/parties", extra, status=201)
        other = body["data"]["id"]
        ids.append(other)
        api("host", "PATCH", f"/parties/{other}", {"title": prefix + " edited", "capacity": 2})
        count(other, 1)
        api(
            "outsider",
            "PATCH",
            f"/parties/{other}",
            {"title": "forged"},
            status=403,
            unchanged=True,
        )
        api("host", "POST", f"/parties/{other}/cancel", {})
        api("a", "POST", f"/parties/{other}/join-requests", {}, status=409, unchanged=True)
        save(
            "R02-create-edit-cancel",
            "actual create201/edit200/cancel200; nonHost403/cancelled join409",
            {"party": other},
            before,
        )
        before = sql()
        body = api("a", "POST", "/auth/logout", {})
        assert body["data"]["logged_out"]
        api("a", "GET", "/me", status=401, unchanged=True)
        assert before == sql()
        save(
            "R03-logout",
            "real logout200 then session401; domain unchanged",
            {"logged_out": True},
            before,
        )
        assert not errors, errors
        report = json.loads((out / "results.json").read_text())
        report.update(
            summary={
                "Pass": len(cases),
                "Fail": 0,
                "Not run": ["Live TU authentication", "Human UAT", "Production load"],
            },
            source_commit=subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip(),
            source_sha256={
                f: hashlib.sha256((ROOT / f).read_bytes()).hexdigest()
                for f in [
                    "scripts/sprint2-cross-story-evidence.py",
                    "backend/parties/services.py",
                    "backend/parties/views.py",
                    "backend/parties/search.py",
                    "backend/conduct/services.py",
                    "backend/conduct/views.py",
                    "frontend/static/js/app.js",
                    "frontend/templates/myparty.html",
                    "frontend/static/js/party-members.js",
                    "frontend/static/js/myparty-leave.js",
                    "frontend/static/js/myparty-review.js",
                ]
            },
            fixture_users={r: u.pk for r, u in users.items()},
            fixture_parties=ids,
            fixture_transitions=transitions,
            final_sql=sql(),
            browser=browser.version,
            python=sys.version.split()[0],
            django=django.get_version(),
            database=connection.settings_dict["NAME"],
            finished_at=timezone.now().isoformat(),
            page_errors=errors,
        )
        (out / "results.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2, default=str)
        )
        print("DONE", report["summary"])
        browser.close()


if __name__ == "__main__":
    main()
