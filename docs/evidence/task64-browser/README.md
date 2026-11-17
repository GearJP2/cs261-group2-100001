# Task64 / S2-US6-T-UI browser acceptance and retest

17 November 2026, assistant-operated on Gear's request. This is a new automated run, not V/Net's sign-off or human UAT. Base main `4deb414b069bceeef60623c1d756db0a415222cb` plus this PR's CSRF fix/tests/harness. Runtime core page fix is described below.

## Actual results

Real Chromium + Django HTTP + PostgreSQL: **10 scenarios PASS, 0 FAIL**, no page JavaScript errors. [Raw results / HTTP responses / SQL before-after](run/results.json), [execution log](execution.log).

| Case | Expected and actual |
| --- | --- |
| B01 Host | Host-first, API fallback ผู้ใช้, Thai Host/Member badges, count3 matches direct SQL active rows. |
| B02 Member | Same actual list/count3 from the native joined tab. |
| B03 outsider | No private Members panel; actual API403; no SQL changes. |
| B03 left | Withdrawn viewer has no panel; API403; history retained/no changes. |
| B04 empty | Host without membership row sees genuine empty API list/count0 and empty-state message. |
| B05 loading | Hold/continue a genuine GET; loading clears stale rows then actual response restores count3. No route fulfill/fake response. |
| B06 Approve | Click native Approve button; POST200, Members GET refresh count4; pending account appears; SQL confirms Approved and one new membership. Count persists automatic reload. |
| B07 Leave | Native dialog/confirm; POST200, soft-left once; subsequent Members403 and private list removed. |
| B08 rights revoked | Keep another viewer's list open, submit real leave from that viewer's other session, refresh open panel; actual403 clears all stale rows and renders forbidden message. |
| B09 missing/retry | Delete only the disposable missing-Party fixture after UI renders; actual404 clears list/shows retry; keyboard Enter on focused retry sends another actual404 and retains clear error state. |

Screenshots: [Host/fallback/order/empty](run/host-fallback-order.png), [approved count4](run/approved-refresh.png), [leave clears private list](run/leave-clears-private-list.png), [404 and keyboard retry](run/not-found-keyboard-retry.png).

## Bug and retest

**T64-BUG-01: fresh session has no CSRF cookie.** The existing My Parties Approve handler reads the CSRF cookie directly, while GET My Parties did not set it. Opening that page with an authenticated session but no prior cookie caused a real decision POST403 (`CSRF cookie not set`) and count remained3. [Failure log](csrf-bug-before-fix.log), [partial pre-fix evidence](partial-before-csrf-fix/results.json).

Fix: `ensure_csrf_cookie` on the authenticated GET page, preserving Django's CSRF validation on writes. Regression test starts an actual enforce-CSRF Django client without a cookie, loads the page, then successfully approves using the issued token. Successful B06 retest starts Chromium contexts with only the synthetic session cookie and clicks the actual UI; it does not preload CSRF. No production fixture/data changes or exemptions.

The first harness attempt also hit Django's async-context protection during SQL reads under Playwright. The harness now uses one worker thread for SQL/fixture deletion. [Harness failure log](harness-thread-failure.log). This was a test harness issue, separate from the CSRF application defect. Earlier partial runs remain historical evidence, not overall PASS runs.

## Unit and regression results

- Members isolated Node tests: **7/7 PASS**, including new dedicated API fallback, loading→empty and404→retry cases; existing403 clear case covers forbidden. [member-unit.log](member-unit.log).
- Actual Approve handler with controlled DOM/API: **8/8 PASS**. [approve-unit.log](approve-unit.log).
- All frontend files run individually: **35/35 PASS** (members7, requests8, leave9, navigation2, search5, review4). See [frontend.log](frontend.log).
- `make verify`: **717 backend tests PASS, no skips**, Django checks/migration drift/Ruff/format pass. [verify.log](verify.log).
- `make smoke`: PASS. [smoke.log](smoke.log).

The earlier716-test run excluded the new regression test and is retained as [historical verification](verify-before-csrf-regression.log); the717 run is authoritative for this PR.

## Contract and checklist

UT-US6-UI-01..04 now have explicit evidence. Name fallback is supplied by the public Members API and rendered safely as text. **Avatar fallback is N/A:** Members public contract and component have no avatar field, so this report does not invent image behavior or record an untested image as PASS.

The five preparation/execution/report/evidence steps are delivered. Final team review/acceptance remains pending this PR; existing issue79 was already closed by RieroS, which alone was not used as acceptance. Do not attribute these runs to V/Net. Gear remains the team reviewer.

## Reproduce / isolation

Requires the project's Python dependencies plus Playwright in a separate tooling environment and an installed Chromium; no runtime dependency was added. Start a disposable Docker Compose API/database built from this revision, with the matching database environment loaded into the tooling process. The script requires DEBUG, PostgreSQL DB prefix `s2_task64_`, explicit confirmation, fixed loopback API25864, and a new output directory:

```sh
TASK64_CONFIRM_TEST_DATABASE=yes TASK64_OUTPUT=/tmp/task64-new-output TASK64_CHROME=/path/to/chrome python scripts/us6-members-browser-evidence.py
```

Recorded project `s2-task64-browser`, DB `s2_task64_http`, database port25464. Unique synthetic fixtures only; the missing-Party scenario deliberately deletes one newly created fixture. Cookies/session keys are memory-only and excluded from recorded responses. Exact tested frontend/test/harness hashes and environment versions are in results.json. Backend core fix is included in this PR and verified by the recorded regression suite.

Not run: live TU login, human UAT/teammate sign-off, production load, full Task96 cross-story regression or exhaustive accessibility audit. Keyboard evidence is scoped to real retry focus/Enter. API/database evidence complements native UI testing; Node mocks are labeled separately.
