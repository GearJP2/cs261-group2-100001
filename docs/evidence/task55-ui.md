# Task55 — US10 UI handler regression evidence

[PR #178](https://github.com/GearJP2/cs261-group2-100001/pull/178) / [Issue #70](https://github.com/GearJP2/cs261-group2-100001/issues/70)

Verified 17 November 2026 by Codex. This report replaces the earlier unqualified Manual UI claims: the checks below are automated Node tests with controlled DOM/API dependencies, not browser execution, human UAT, or live HTTP/database acceptance.

## Source and environment

- Source baseline after merging PR177/main: `82d5ed8325b4e49dff767bee36fdcbb4767816f6`.
- Actual inline handler extracted from `frontend/templates/myparty.html`; SHA-256 `61bf2ff1f61019f2de0e73c8b37bf548adb56a95c317210f5d2026e2c03099eb`.
- Tests: `frontend/tests/myparty-requests.test.cjs` in this PR; raw output: [task55-ui-unit.log](task55-ui-unit.log).
- Node.js v24.17.0 on Linux/WSL; no database, Docker server or TU account required for this run. CI uses Node22 separately.
- The fixture supplies a synthetic CSRF cookie, DOM containers, controlled fetch responses, a Members refresh dependency and intercepted reload timers. Synthetic tokens are not credentials.

## Reproduction

Run `node frontend/tests/myparty-requests.test.cjs` from the repository root. The tests extract and execute the real inline script, not a copied handler implementation. Expected: five tests pass, zero failures. The shared fixture also supplies PartyMembers.refresh so the tests remain valid with PR179's dependency.

| Case | Fixture / action | Expected | Actual |
| --- | --- | --- | --- |
| UT-US10-UI-01 | Keep decision fetch pending; click Approve then the disabled replacement | Loading/disabled state immediately; one POST | Pass |
| UT-US10-UI-02 | Decision API returns200 for Approve | Approved JSON to Party/request URL, fixture CSRF header, success state and scheduled reload callback | Pass |
| UT-US10-UI-03 | Decision API returns200 for Reject | Rejected JSON; no member-added success message; scheduled reload callback | Pass |
| UT-US10-UI-04 | Empty Pending list, list500 and decision409 | Empty/error states; no false success or reload after failed decision | Pass |
| XSS rendering regression | Pending name/level contain HTML tags | Escaped HTML entities; no raw img/script tags inserted | Pass |

Result: **5 tests passed**. Reload is a spy/timer callback: these tests prove a reload was requested, not that a real page fetched updated member counts. The mocked click helper models disabled controls; native browser event/keyboard behavior remains separate.

## Not run / remaining Task55 acceptance

- Actual Chromium/browser flow, keyboard/focus, native double-click behavior, and Pending/Approve/Reject after a real page reload: **Not run in this fix**.
- Live HTTP/PostgreSQL, TU login and full Docker verify/smoke: **not rerun locally**. Use GitHub CI for that workflow's result, without treating it as human UI acceptance.
- Human Manual UI/UAT and named teammate sign-off: **Not run / not asserted**. To close the whole Task55, record fixture roles/Party/request IDs, browser and environment, tested commit, steps, expected/actual, tester/date and screenshots/logs for the remaining UI cases.
- `scripts/smoke.py` checks HTTP/template/static assets; it does not execute JavaScript and cannot prove absence of browser JavaScript errors.

There are no runtime/schema changes in PR178. The report does not close US10 or claim that UI acceptance is complete merely because backend tests/CI pass. PR179 adds Members-specific integration regression checks on top of this fixture.
