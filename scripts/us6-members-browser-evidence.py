"""Task64: real browser/HTTP/SQL on confirmed disposable PostgreSQL only."""

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
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
from parties.models import JoinRequest, Party, PartyMembership  # noqa: E402
from playwright.sync_api import expect, sync_playwright  # noqa: E402
from venues.models import Sport, Venue  # noqa: E402


def main():
    assert (
        settings.DEBUG
        and connection.vendor == "postgresql"
        and connection.settings_dict["NAME"].startswith("s2_task64_")
    )
    assert os.environ.get("TASK64_CONFIRM_TEST_DATABASE") == "yes"
    out = Path(os.environ["TASK64_OUTPUT"])
    assert not out.exists()
    out.mkdir(parents=True)
    base = "http://127.0.0.1:25864"
    spec = importlib.util.spec_from_file_location(
        "existing_browser", ROOT / "scripts/us10-api-evidence.py"
    )
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    prefix = "qa64_" + uuid4().hex[:8]
    users = {
        r: get_user_model().objects.create_user(prefix + r, email=prefix + r + "@example.invalid")
        for r in ["host", "member", "fallback", "left", "pending", "outsider"]
    }
    for r, u in users.items():
        if r != "fallback":
            UserProfile.objects.create(user=u, display_name="QA64 " + r)
    clients = {r: helper.Browser(base, u) for r, u in users.items()}
    sport = Sport.objects.create(name=prefix)
    venue = Venue.objects.create(name=prefix, location_text="Synthetic QA64")
    now = timezone.now()
    parties = {}
    for label in ["main", "empty", "missing"]:
        p = Party.objects.create(
            host=users["host"],
            title="QA64 " + label,
            sport=sport,
            venue=venue,
            capacity=8,
            starts_at=now + timedelta(days=1),
            ends_at=now + timedelta(days=1, hours=1),
        )
        parties[label] = p.pk
        if label != "empty":
            for r in ["fallback", "member", "host", "left"]:
                PartyMembership.objects.create(
                    party=p, user=users[r], left_at=now if r == "left" else None
                )
    request = JoinRequest.objects.create(party_id=parties["main"], user=users["pending"])

    pool = ThreadPoolExecutor(max_workers=1)

    def read_sql():
        result = {}
        with connection.cursor() as c:
            for table in ["parties_partymembership", "parties_joinrequest"]:
                c.execute(
                    f'SELECT * FROM "{table}" WHERE party_id=ANY(%s) ORDER BY id',
                    [list(parties.values())],
                )
                result[table] = [
                    dict(zip([x[0] for x in c.description], r, strict=True)) for r in c.fetchall()
                ]
        return result

    def sql():
        return pool.submit(read_sql).result()

    cases = []
    responses = []
    errors = []

    def save(label, expected, actual, before):
        cases.append(
            dict(
                id=label,
                expected=expected,
                actual=actual,
                before=before,
                after=sql(),
                result="PASS",
            )
        )
        (out / "results.json").write_text(
            json.dumps(
                dict(cases=cases, responses=responses), ensure_ascii=False, indent=2, default=str
            )
        )
        print("PASS", label, flush=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            executable_path=os.environ["TASK64_CHROME"], args=["--no-sandbox"]
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
                if "/api/v1/parties/" in resp.url:
                    try:
                        body = resp.json()
                    except Exception:
                        body = {"non_json": True}
                    responses.append(
                        dict(
                            method=resp.request.method,
                            path=resp.url.replace(base, ""),
                            status=resp.status,
                            body=body,
                            cache_control=resp.headers.get("cache-control"),
                        )
                    )

            page.on("response", record)
            return page

        host = context("host")
        member = context("member")
        outsider = context("outsider")
        left = context("left")
        hp = page_for(host)
        mp = page_for(member)
        selector = f'[data-party-members="{parties["main"]}"]'
        hp.goto(base + "/my-parties/")
        hp.wait_for_load_state("networkidle")
        panel = hp.locator(selector).first
        expect(panel.locator("[data-member-count]")).to_have_text("3")
        names = panel.locator(".mp-member-name").all_text_contents()
        assert names == ["QA64 host", "ผู้ใช้", "QA64 member"], names
        assert panel.locator(".mp-member-role").all_text_contents() == ["ผู้จัด", "สมาชิก", "สมาชิก"]
        assert prefix not in panel.inner_text()
        before = sql()
        hp.screenshot(path=str(out / "host-fallback-order.png"), full_page=True)
        save(
            "B01-host-fallback-order-count",
            "Host first, fallback, roles, count3 matching SQL",
            dict(names=names, count=3),
            before,
        )
        assert (
            sum(
                r["left_at"] is None and r["party_id"] == parties["main"]
                for r in before["parties_partymembership"]
            )
            == 3
        )
        mp.goto(base + "/my-parties/")
        mp.wait_for_load_state("networkidle")
        mp.locator('[data-myparty-tab="joined"]').click()
        expect(mp.locator(selector).locator("[data-member-count]")).to_have_text("3")
        save("B02-member", "active Member sees same list/count", {"count": 3}, sql())
        for role, ctx in [("outsider", outsider), ("left", left)]:
            page = page_for(ctx)
            before = sql()
            page.goto(base + "/my-parties/")
            page.wait_for_load_state("networkidle")
            assert page.locator(selector).count() == 0
            r = ctx.request.get(base + f"/api/v1/parties/{parties['main']}/members")
            assert r.status == 403 and before == sql()
            save(
                "B03-" + role,
                "no private panel, real API403, SQL unchanged",
                dict(http=r.status, body=r.json()),
                before,
            )
        empty = hp.locator(f'[data-party-members="{parties["empty"]}"]').first
        expect(empty.locator("[data-member-status]")).to_have_text("ยังไม่มีสมาชิกปัจจุบัน")
        expect(empty.locator("[data-member-count]")).to_have_text("0")
        save(
            "B04-empty", "Host without membership gets true empty list/count0", {"count": 0}, sql()
        )
        # Hold a genuine response to observe loading; never fulfill or fake an API result.
        before = sql()
        hp.route(
            f"**/parties/{parties['main']}/members",
            lambda route: (hp.wait_for_timeout(250), route.continue_()),
        )
        hp.evaluate("(id)=>{window.task64Pending=window.PartyMembers.refresh(id)}", parties["main"])
        expect(panel.locator("[data-member-status]")).to_have_text("กำลังโหลดสมาชิก…")
        expect(panel.locator("[data-member-list] li")).to_have_count(0)
        hp.evaluate("()=>window.task64Pending")
        hp.unroute(f"**/parties/{parties['main']}/members")
        expect(panel.locator("[data-member-count]")).to_have_text("3")
        assert before == sql()
        save(
            "B05-loading",
            "loading clears stale rows then actual API restores list",
            {"restored": 3},
            before,
        )
        before = sql()
        button = hp.locator(f'[data-request-id="{request.pk}"].btn-approve')
        expect(button).to_be_visible()
        button.click()
        expect(panel.locator("[data-member-count]")).to_have_text("4")
        expect(panel.locator(".mp-member-name").filter(has_text="QA64 pending")).to_have_count(1)
        hp.wait_for_timeout(1200)
        hp.wait_for_load_state("networkidle")
        expect(hp.locator(selector).first.locator("[data-member-count]")).to_have_text("4")
        after = sql()
        assert len(after["parties_partymembership"]) == len(before["parties_partymembership"]) + 1
        assert any(
            r["user_id"] == users["pending"].pk and r["status"] == "Approved"
            for r in after["parties_joinrequest"]
        )
        hp.screenshot(path=str(out / "approved-refresh.png"), full_page=True)
        save(
            "B06-approve-refresh",
            "native Approve→POST200→membersGET/count4 persists reload",
            {"count": 4},
            before,
        )
        # An actual soft leave revokes the viewer while the list remains open.
        before = sql()
        mp.locator(f'[data-leave-party="{parties["main"]}"]').click()
        mp.locator("[data-leave-confirm]").click()
        expect(mp.locator("[data-leave-message]")).to_contain_text("ถอนตัวสำเร็จ")
        assert (
            mp.locator(selector).count() == 0
            or mp.locator(selector).locator("[data-member-list] li").count() == 0
        )
        r = member.request.get(base + f"/api/v1/parties/{parties['main']}/members")
        assert r.status == 403
        after = sql()
        changed = [
            (a, b)
            for a, b in zip(before["parties_partymembership"], after["parties_partymembership"])
            if a != b
        ]
        assert (
            len(changed) == 1
            and changed[0][1]["user_id"] == users["member"].pk
            and changed[0][1]["left_at"] is not None
        )
        mp.screenshot(path=str(out / "leave-clears-private-list.png"), full_page=True)
        save(
            "B07-leave-clears",
            "native leave→softleft→members403; private list cleared",
            {"http_after": 403},
            before,
        )
        # Another open viewer refreshes after rights were revoked, observing real 403 UI.
        stale = page_for(context("fallback"))
        stale.goto(base + "/my-parties/")
        stale.wait_for_load_state("networkidle")
        stale.locator('[data-myparty-tab="joined"]').click()
        sp = stale.locator(selector)
        expect(sp.locator("[data-member-list] li")).to_have_count(3)
        before = sql()
        status, body, _ = clients["fallback"].send(
            "POST", f"/api/v1/parties/{parties['main']}/leave", {}
        )
        assert status == 200
        result = stale.evaluate("(id)=>window.PartyMembers.refresh(id)", parties["main"])
        assert result["status"] == "forbidden"
        expect(sp.locator("[data-member-list] li")).to_have_count(0)
        expect(sp.locator("[data-member-status]")).to_contain_text("เฉพาะผู้จัดหรือสมาชิกปัจจุบัน")
        save(
            "B08-revoked403",
            "open viewer→external real leave→refresh403 clears stale rows",
            {"http": 403, "ui": "forbidden"},
            before,
        )
        before = sql()
        missing = parties["missing"]
        pool.submit(lambda: Party.objects.get(pk=missing).delete()).result()
        result = hp.evaluate("(id)=>window.PartyMembers.refresh(id)", missing)
        assert result["status"] == "error"
        missing_panel = hp.locator(f'[data-party-members="{missing}"]').first
        retry = missing_panel.locator("[data-member-retry]")
        expect(retry).to_be_visible()
        expect(missing_panel.locator("[data-member-list] li")).to_have_count(0)
        retry.focus()
        expect(retry).to_be_focused()
        with hp.expect_response(
            lambda r: r.url.endswith(f"/parties/{missing}/members") and r.status == 404
        ):
            hp.keyboard.press("Enter")
        expect(missing_panel.locator("[data-member-status]")).to_contain_text(
            "โหลดรายชื่อสมาชิกไม่สำเร็จ"
        )
        hp.screenshot(path=str(out / "not-found-keyboard-retry.png"), full_page=True)
        save(
            "B09-not-found-keyboard-retry",
            "fixture deleted→real404 clears list; keyboard retry sends GET404",
            {"http": 404, "keyboard": "Enter"},
            before,
        )
        assert not errors, errors
        report = json.loads((out / "results.json").read_text())
        report.update(
            summary={"Pass": len(cases), "Fail": 0},
            tested_source=subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip(),
            source_sha256={
                f: hashlib.sha256((ROOT / f).read_bytes()).hexdigest()
                for f in [
                    "frontend/static/js/party-members.js",
                    "frontend/static/js/myparty-leave.js",
                    "frontend/templates/myparty.html",
                    "frontend/tests/party-members.test.cjs",
                    "scripts/us6-members-browser-evidence.py",
                ]
            },
            browser=browser.version,
            python=sys.version.split()[0],
            django=django.get_version(),
            database=connection.settings_dict["NAME"],
            fixture_users={r: u.pk for r, u in users.items()},
            fixture_parties=parties,
            page_errors=errors,
            finished_at=timezone.now().isoformat(),
            not_run=["Live TU login", "Human UAT / teammate sign-off", "Production load"],
            avatar="N/A: public Members contract has no avatar; API supplies fallback display name",
        )
        (out / "results.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2, default=str)
        )
        print("DONE", report["summary"])
        browser.close()


if __name__ == "__main__":
    main()
