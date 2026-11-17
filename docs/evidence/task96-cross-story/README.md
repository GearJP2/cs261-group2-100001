# Task96 / S2-INT-T-01 — integrated Sprint 2 execution

17 November 2026. Owner Gear, helper P; **assistant-operated at Gear's request**, not P's sign-off or human UAT. All new execution uses integrated main **`d1574878237e0b73a2069761c802be4ae083d10a`**, which includes PR185. No application/runtime code was changed in this PR.

## Actual outcome

- **19/19 cross-story/regression scenarios PASS, 0 FAIL** on real Chromium, actual Django HTTP and isolated PostgreSQL.
- **717 backend tests PASS, no skips** on the same source revision, including actual PostgreSQL transaction/concurrency suites. [verify.log](verify.log)
- **40 frontend tests PASS**, isolated Node mocks recorded separately. [frontend.log](frontend.log)
- `make smoke`: PASS after restoring No-show flag false. [smoke.log](smoke.log)
- **Not run:** live TU authentication, human UAT/sign-off and production load. Synthetic verified sessions and auth guard/logout checks are not claimed as successful live university login.

[Expected/actual execution CSV](execution.csv), [raw HTTP/SQL before-after and fixture transition](run/results.json), [execution log](execution.log), [source fingerprints](source-manifest.json), [server environment / flag false](server-environment.json).

## One continuous workflow / Story trace

The main Party is created through HTTP, then the same Party/membership/request/review IDs are carried through all F01–F16 steps. No preapproved memberships/reviews are inserted for this workflow. Preparatory fixtures only create synthetic accounts/profiles/verified sessions, sport, venue/support and opening hours.

| Case | Story / layer | Expected and actual |
| --- | --- | --- |
| R01 auth | Regression / HTTP | Anonymous401, unverified403, synthetic verified me200; malformed login400; absent TU key returns502 UNIVERSITY_API_UNAVAILABLE without attempting live authentication. |
| F01 create | Regression / HTTP+SQL | Host creates201; Host membership1, capacity3, two free seats. |
| F02 search→Pending | US2→join / native UI+HTTP+SQL | Search current Party, follow Detail, click join201; Pending consumes no seat: count remains1. |
| F03 approve→members | US10→US6 / native UI+HTTP+SQL | Native Host Approve200, matching Members refresh2, Member Detail shows membership. |
| F04 reject | US10→US6 / HTTP/native UI+SQL | B Pending then native Reject200; no membership/count stays2; B Members403. |
| F05 full | US10→US2 / HTTP+SQL | C approved into final seat, count3/Full; outsider join409 without writes. |
| F06 leave | US4→US6→US2 / native UI+HTTP+SQL | Native dialog/confirm sends leave200, soft-left history retained, Members403 and private list cleared; count2/one free seat. |
| F07 retry | US4 / HTTP+SQL | Repeated leave200 keeps exact left_at and all domain rows. |
| F08 rejoin | US2→join→US10→US6 / UI+HTTP+SQL | Open Party reappears in Search; native rejoin201 Pending/count2; Host approval returns count3; reuses the same membership ID, no duplicate row. |
| F09 guards | US10/US4 / HTTP+SQL | Non-Host decision403, repeated decision409, missing CSRF leave403; denied requests preserve domain rows. |
| F10 before end | US14 / HTTP+SQL | Review409 PARTY_NOT_COMPLETED, no review/cache mutation. |
| F11 completed review | US14 / native UI+HTTP+SQL | Completed History→native review201; one review, Host rating_sum5/count1, creditNULL. |
| F12 unique/eligibility | US14 / HTTP+SQL | Duplicate review409 and rejected B403 without writes; eligible C reviews A201 independently. |
| F13 Profile | US14 + profile regression / native UI+HTTP+SQL | Profile reads actual5.0/comment and public profile; read operations do not write. |
| F14 flag off | US14 / HTTP+SQL | Default No-show off returns404/no writes; enable flag only in isolated test backend, no SQL mutation from toggle. |
| F15 No-show | US14 / HTTP+SQL | Two eligible reporters reach threshold: first retains NULL, second creates exactly one ledger event/credit95. Star review rows and Host rating cache5/1 stay unchanged. |
| F16 duplicate/off | US14 / HTTP+SQL | Duplicate report409 and rejected B403 create no second deduction. Restore false; endpoint404, reports/ledger/credit preserved. |
| R02 management | Regression / HTTP+SQL | Separate Party create201/edit200/cancel200; non-Host edit403 and join after cancel409 without unauthorized mutation. |
| R03 logout | Regression / HTTP+SQL | Actual logout200 then same HTTP session me401, domain tables unchanged. |

Images: [Pending/no seat](run/pending-no-seat.png), [leave restores slot](run/leave-restores-slot.png), [Completed review](run/completed-review.png), [Profile summary](run/profile-review-summary.png).

Every snapshot reads actual fixture Party, membership, request, review, No-show report, credit ledger and profile tables directly. `count()` independently compares SQL active rows with the Members list/IDs and Party Detail count/free seats after mutations. Native browser responses and helper HTTP calls are recorded without cookies, CSRF tokens or auth headers. There are no fake HTTP responses or mocked services in this workflow.

### Completion-time fixture transition

After F10, the runner deliberately changes **only the main synthetic Party's starts_at/ends_at** so it is completed one second before the transition. This simulates elapsed activity time; it is **fixture preparation, not a business API action or a PASS test of changing an ended Party's schedule**. Before/after and changed fields are recorded separately in `fixture_transitions`. It permits testing review eligibility on the same participants/Party IDs without waiting two days. All approval/leave/rejoin actions were real HTTP before this transition.

## Race coverage is separate automation

The full717-test suite runs on isolated `test_s2_task96_http`, separate from the browser fixture DB, on the **same source revision**. It includes `parties.test_approval_concurrency`, `parties.test_rejection_concurrency`, `parties.test_editing_concurrency`, `parties.test_leave_database`, `conduct.test_reviews_concurrency` and `conduct.test_no_show_concurrency`: **34 test methods across these selected race/database suites**. Their named results and DB/lock evidence are in verify.log. These tests use real concurrent PostgreSQL connections/transactions; sequential HTTP snapshots are not presented as race proof. Other backend/Node results are regression support, not additional manual browser scenarios.

The existing Task45 inventory101 and 24-AC design matrix remain historical plans. This report executes the specific19 scenarios above; it does **not** change every inventory row to PASS merely because the full unit/integration suite passed. Story-specific edge cases have named automation and prior reports, while this new report supplies the previously missing continuous integrated execution.

## Bug / harness retest

No application defect reproduced in this scope; no runtime patch or invented bug receipt is included.

Two initial **harness** failures were corrected and retained:

1. [Navigation failure](harness-navigation-failure.log): after native join reload, Chromium could no longer read that response body. The runner checks201 and rereads the persisted request ID through the actual `join-requests/me` endpoint. [Partial run](partial-before-navigation-fix/results.json).
2. [Search wait failure](harness-search-wait-failure.log): assertion ran while old unfiltered cards were still visible. The runner waits for the exact filtered list. [Partial run](partial-before-search-wait-fix/results.json).

Neither partial run is called an overall PASS, and neither error was fixed by mocking a domain response or changing expected behavior. The final run completed19 scenarios with no page JavaScript errors.

## Reproduction / isolation

Tooling environment: Python3.12.0/Django5.2.18 plus Playwright and installed Chromium156.0.8078.47. Backend: Python3.12.15/Django5.2.18, PostgreSQL17 Docker. No project dependency was added for browser tooling.

The guarded runner uses fixed loopback API `127.0.0.1:25896`, Compose project `s2-task96-cross`, env `/tmp/task96.env`, overlay `/tmp/task96.compose.yml`. Create a disposable env file with DEBUG=true, a new test-only SECRET_KEY, DB `s2_task96_http`, test-only POSTGRES_USER/PASSWORD, local POSTGRES_HOST=127.0.0.1, POSTGRES_PORT=25496, POSTGRES_HOST_PORT=25496, APP_PORT=25896 and blank TU_APPLICATION_KEY. Do not load shared production/team credentials. The overlay must isolate the image and env and expose the test flag:

```yaml
services:
  backend:
    image: cs261-task96-http:local
    env_file: !override
      - /tmp/task96.env
    environment:
      TU_APPLICATION_KEY: ""
      NO_SHOW_ENABLED: ${TASK96_FLAG:-false}
```

Compose's existing backend environment overrides the database host/port to database:5432; local tooling uses127.0.0.1:25496. Start from the exact source revision, load the disposable env into the tooling process, and use a new output directory:

```sh
docker compose --env-file /tmp/task96.env -f docker-compose.yml -f /tmp/task96.compose.yml -p s2-task96-cross up --build -d --wait
TASK96_CONFIRM_TEST_DATABASE=yes TASK96_OUTPUT=/tmp/task96-new-output TASK96_CHROME=/path/to/chrome python scripts/sprint2-cross-story-evidence.py
make 'COMPOSE=docker compose --env-file /tmp/task96.env -f docker-compose.yml -f /tmp/task96.compose.yml -p s2-task96-cross' verify
make 'COMPOSE=docker compose --env-file /tmp/task96.env -f docker-compose.yml -f /tmp/task96.compose.yml -p s2-task96-cross' smoke
docker compose --env-file /tmp/task96.env -f docker-compose.yml -f /tmp/task96.compose.yml -p s2-task96-cross down --volumes
```

Guard requires DEBUG, PostgreSQL prefix `s2_task96_`, explicit confirmation and a new output directory. The runner creates unique synthetic fixtures and toggles only the fixed test backend. It restores the flag false on successful completion. If interrupted during the flag phase, restore false or remove only this dedicated project before reuse. No deployment flag or shared database was changed.

## Limits and acceptance

Live TU login is **Not run**: no real TU application key/credentials were supplied to this environment. R01 tests the genuine missing-provider response and session guards; it does not fabricate a successful university login. Native UI flows use verified session fixtures. Logout and profile/create/edit/cancel regression are real application HTTP/SQL, with native UI where explicitly stated. Human UAT, P's peer review, Gear's final acceptance, production load and exhaustive browser/device/accessibility coverage are not claimed.

Technical workflow, regression and evidence are delivered. Final team review/merge remains pending this PR before checking the last acceptance item. Task97 can use this report and carry the explicit external-login/UAT limits into its Sprint summary/demo/retrospective.
