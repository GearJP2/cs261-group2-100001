"""Task82 native search acceptance; confirmed disposable local PostgreSQL only."""

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse
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
from parties.models import Party, PartyMembership  # noqa: E402
from playwright.sync_api import expect, sync_playwright  # noqa: E402
from venues.models import Sport, Venue, VenueSport  # noqa: E402


def main():
    assert (
        settings.DEBUG
        and connection.vendor == "postgresql"
        and connection.settings_dict["NAME"].startswith("s2_task82_")
    )
    assert os.environ.get("TASK82_CONFIRM_TEST_DATABASE") == "yes"
    out = Path(os.environ["TASK82_OUTPUT"])
    assert not out.exists()
    out.mkdir(parents=True)
    base = "http://127.0.0.1:25882"
    spec = importlib.util.spec_from_file_location(
        "existing_browser", ROOT / "scripts/us10-api-evidence.py"
    )
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    prefix = "QA82" + uuid4().hex[:6]
    host = get_user_model().objects.create_user(prefix + "host")
    viewer = get_user_model().objects.create_user(prefix + "viewer")
    filler = get_user_model().objects.create_user(prefix + "filler")
    UserProfile.objects.create(user=host, display_name="Synthetic search Host")
    UserProfile.objects.create(user=viewer, display_name="Synthetic search Viewer")
    client = helper.Browser(base, viewer)
    sports = [
        Sport.objects.create(name=prefix + " sport A"),
        Sport.objects.create(name=prefix + " sport B"),
    ]
    venues = [
        Venue.objects.create(
            name=prefix + " indoor", location_text="Synthetic", venue_type="Indoor"
        ),
        Venue.objects.create(
            name=prefix + " outdoor", location_text="Synthetic", venue_type="Outdoor"
        ),
    ]
    for v in venues:
        for s in sports:
            VenueSport.objects.create(venue=v, sport=s)
    now = timezone.now()
    start = timezone.localtime(now).replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(
        days=2
    )
    parties = {}
    labels = [f"Page{i:02}" for i in range(21)] + [
        "IndoorA",
        "OutdoorA",
        "IndoorB",
        "Full",
        "InProgress",
        "Cancelled",
    ]
    for label in labels:
        p = Party.objects.create(
            host=host,
            sport=sports[1] if label == "IndoorB" else sports[0],
            venue=venues[1] if label == "OutdoorA" else venues[0],
            title=prefix + " " + label,
            capacity=2 if label == "Full" else 8,
            starts_at=start,
            ends_at=start + timedelta(hours=1),
        )
        parties[label] = p.pk
        PartyMembership.objects.create(party=p, user=host)
        if label == "Full":
            PartyMembership.objects.create(party=p, user=filler)
        if label == "InProgress":
            p.starts_at = now - timedelta(minutes=5)
            p.ends_at = now + timedelta(hours=1)
        if label == "Cancelled":
            p.cancelled_at = now
        p.save()
    pool = ThreadPoolExecutor(max_workers=1)

    def snapshot_read():
        with connection.cursor() as c:
            data = {}
            for table, col in [
                ("parties_party", "id"),
                ("parties_partymembership", "party_id"),
                ("parties_joinrequest", "party_id"),
            ]:
                c.execute(
                    f'SELECT * FROM "{table}" WHERE "{col}"=ANY(%s) ORDER BY id',
                    [list(parties.values())],
                )
                data[table] = [
                    dict(zip([x[0] for x in c.description], r, strict=True)) for r in c.fetchall()
                ]
            return data

    def sql():
        return pool.submit(snapshot_read).result()

    initial = sql()
    cases = []
    responses = []
    errors = []

    def save(label, expected, actual):
        assert sql() == initial, label
        cases.append(
            dict(id=label, expected=expected, actual=actual, status="PASS", sql_unchanged=True)
        )
        (out / "results.json").write_text(
            json.dumps(
                dict(cases=cases, responses=responses), ensure_ascii=False, indent=2, default=str
            )
        )
        print("PASS", label, flush=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            executable_path=os.environ["TASK82_CHROME"], args=["--no-sandbox"]
        )
        ctx = browser.new_context(
            viewport={"width": 1400, "height": 1000}, timezone_id="America/New_York"
        )
        ctx.add_cookies(
            [
                dict(
                    name="sessionid",
                    value=client.cookies["sessionid"],
                    domain="127.0.0.1",
                    path="/",
                )
            ]
        )
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
                        method=resp.request.method,
                        path=resp.url.replace(base, ""),
                        status=resp.status,
                        body=body,
                    )
                )

        page.on("response", record)

        def submit():
            query = page.locator("[data-search-query]").input_value().strip()
            with page.expect_response(
                lambda r: (
                    "/api/v1/parties?" in r.url
                    and parse_qs(urlparse(r.url).query).get("q", [""])[0] == query
                )
            ):
                page.locator("[data-search-form] button[type=submit]").click()
            expect(page.locator("[data-search-status]")).to_be_hidden()

        def search(text):
            page.locator("[data-search-query]").fill(text)
            submit()

        def cards():
            return page.locator(".search-card h3").all_text_contents()

        page.goto(base + "/search/")
        page.wait_for_load_state("networkidle")
        search(prefix + " Page")
        expect(page.locator(".search-card")).to_have_count(20)
        expect(page.locator("[data-result-count]")).to_have_text("21 กิจกรรม")
        first = cards()
        page.locator("[data-page-next]").click()
        expect(page.locator(".search-card")).to_have_count(1)
        assert cards() == [prefix + " Page20"]
        page.locator("[data-page-previous]").click()
        expect(page.locator(".search-card")).to_have_count(20)
        assert cards() == first
        page.screenshot(path=str(out / "pagination.png"), full_page=True)
        save(
            "B01-pagination",
            "21 fixture rows;20+1 stable pages and back",
            dict(first_page=first, second_page=[prefix + " Page20"]),
        )
        search(prefix + " Indoor")
        page.locator("[data-filter-sport]").select_option(str(sports[0].pk))
        page.locator("[data-filter-venue]").select_option(str(venues[0].pk))
        page.locator("[data-filter-venue-type]").select_option("Indoor")
        page.locator("[data-filter-date]").fill(start.date().isoformat())
        page.locator("[data-filter-time-from]").fill("09:00")
        page.locator("[data-filter-time-to]").fill("11:00")
        submit()
        assert cards() == [prefix + " IndoorA"], cards()
        params = parse_qs(urlparse(page.url).query)
        assert (
            params["sport_id"] == [str(sports[0].pk)]
            and params["venue_type"] == ["Indoor"]
            and params["venue_id"] == [str(venues[0].pk)]
            and params["starts_from"] == [start.date().isoformat() + "T09:00:00+07:00"]
        )
        assert page.locator(".search-chip").count() == 6
        page.screenshot(path=str(out / "combined-filters.png"), full_page=True)
        save(
            "B02-combined-filters",
            "q+sport+venue+Indoor+Bangkok date/time, one matching fixture",
            dict(params=params, titles=cards(), timezone="America/New_York"),
        )
        page.get_by_role("button", name="ล้างตัวกรอง ในร่ม", exact=True).click()
        page.wait_for_load_state("networkidle")
        assert "venue_type" not in parse_qs(urlparse(page.url).query)
        assert page.locator("[data-filter-sport]").input_value() == str(sports[0].pk)
        save(
            "B03-chip",
            "remove Indoor chip alone preserves sport",
            {"params": parse_qs(urlparse(page.url).query)},
        )
        page.locator("[data-filter-reset]").click()
        page.wait_for_load_state("networkidle")
        params = parse_qs(urlparse(page.url).query)
        assert params == {"page": ["1"]}, params
        for field in ["query", "sport", "venue", "venue-type", "date", "time-from", "time-to"]:
            selector = "[data-search-query]" if field == "query" else f"[data-filter-{field}]"
            assert page.locator(selector).input_value() == ""
        assert page.locator("[data-filter-state]").input_value() == "Open"
        expect(page.locator("[data-search-chips]")).to_be_hidden()
        save(
            "B04-reset",
            "all controls/chips clear, defaultOpen query page1 only",
            dict(params=params),
        )
        search(prefix + " NO_MATCH")
        expect(page.locator("[data-search-empty]")).to_be_visible()
        expect(page.locator("[data-search-error]")).to_be_hidden()
        save("B05-empty", "genuine 200 total0 renders empty not error", {"titles": cards()})
        page.locator("[data-empty-reset]").click()
        page.wait_for_load_state("networkidle")
        page.locator("[data-search-query]").fill(prefix)
        page.locator("[data-filter-date]").fill(start.date().isoformat())
        page.locator("[data-filter-time-from]").fill("13:00")
        page.locator("[data-filter-time-to]").fill("12:00")
        submit()
        expect(page.locator("[data-search-error]")).to_be_visible()
        expect(page.locator("[data-search-empty]")).to_be_hidden()
        assert any(r["status"] == 400 for r in responses)
        page.screenshot(path=str(out / "validation-error.png"), full_page=True)
        save(
            "B06-real400-error",
            "invalid time range→API400→error, never empty",
            {"error": page.locator("[data-search-error-message]").inner_text()},
        )
        page.locator("[data-search-clear]").click()
        page.wait_for_load_state("networkidle")
        expect(page.locator("[data-search-error]")).to_be_hidden()
        save(
            "B07-clear-error",
            "clear invalid URL/filters recovers real default search",
            {"params": parse_qs(urlparse(page.url).query)},
        )
        # Keep older network requests pending while newer real queries finish.
        held = []

        def hold(route):
            q = parse_qs(urlparse(route.request.url).query).get("q", [""])[0]
            if q.endswith(" Page"):
                held.append(route)
            else:
                route.continue_()

        page.route("**/api/v1/parties?*", hold)
        page.locator("[data-search-query]").fill(prefix + " Page")
        page.locator("[data-search-form] button[type=submit]").click()
        page.wait_for_timeout(100)
        assert len(held) == 1
        expect(page.locator("[data-search-status]")).to_be_visible()
        expect(page.locator("[data-search-empty]")).to_be_hidden()
        search(prefix + " IndoorA")
        assert cards() == [prefix + " IndoorA"]
        held.pop().continue_()
        page.wait_for_load_state("networkidle")
        assert cards() == [prefix + " IndoorA"]
        page.unroute("**/api/v1/parties?*")
        save(
            "B08-old-success",
            "old real success arrives last; newer result remains visible",
            {"titles": cards()},
        )
        held = []

        def hold_error(route):
            q = parse_qs(urlparse(route.request.url).query)
            if "starts_from" in q:
                held.append(route)
            else:
                route.continue_()

        page.route("**/api/v1/parties?*", hold_error)
        page.locator("[data-filter-date]").fill(start.date().isoformat())
        page.locator("[data-filter-time-from]").fill("13:00")
        page.locator("[data-filter-time-to]").fill("12:00")
        page.locator("[data-search-form] button[type=submit]").click()
        page.wait_for_timeout(100)
        assert len(held) == 1
        page.locator("[data-filter-reset]").click()
        page.wait_for_timeout(150)
        expect(page.locator(".search-card").first).to_be_visible()
        held.pop().continue_()
        page.wait_for_load_state("networkidle")
        expect(page.locator("[data-search-error]")).to_be_hidden()
        assert parse_qs(urlparse(page.url).query) == {"page": ["1"]}
        page.unroute("**/api/v1/parties?*")
        save(
            "B09-old-error-reset",
            "delayed real400 after reset cannot override new default result",
            {"error_hidden": True},
        )
        for state in ["Full", "InProgress", "Cancelled"]:
            page.locator("[data-search-query]").fill(prefix + " " + state)
            page.locator("[data-filter-state]").select_option(state)
            submit()
            assert cards() == [prefix + " " + state]
            page.locator(".search-card-link").click()
            page.wait_for_load_state("networkidle")
            assert f"/parties/{parties[state]}/" in page.url
            join = page.get_by_role("button", name="ขอเข้าร่วม", exact=True)
            assert join.count() == 0 or join.is_disabled(), state
            page.screenshot(path=str(out / (state.lower() + "-detail.png")), full_page=True)
            save(
                "B10-state-" + state,
                "matching state visible; Detail does not allow join",
                dict(state=state, join_enabled=False, url=page.url.replace(base, "")),
            )
            page.goto(base + "/search/")
            page.wait_for_load_state("networkidle")
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
                    "frontend/static/js/app.js",
                    "frontend/static/js/search-request-state.js",
                    "frontend/templates/search.html",
                    "scripts/us2-search-browser-evidence.py",
                    "backend/parties/search.py",
                ]
            },
            sql_before=initial,
            sql_after=sql(),
            browser=browser.version,
            python=sys.version.split()[0],
            django=django.get_version(),
            database=connection.settings_dict["NAME"],
            fixture_prefix=prefix,
            fixture_parties=parties,
            page_errors=errors,
            finished_at=timezone.now().isoformat(),
            not_run=["Live TU login", "Human UAT/sign-off", "Production load"],
        )
        (out / "results.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2, default=str)
        )
        print("DONE", report["summary"])
        browser.close()


if __name__ == "__main__":
    main()
