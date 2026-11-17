# Task73 — US4 UI handler regression evidence

[Issue #88](https://github.com/GearJP2/cs261-group2-100001/issues/88)

Verified 17 November 2026. This report records automated Node unit tests with controlled DOM/API dependencies for the US4 leave dialog handler (`frontend/static/js/myparty-leave.js`), not live browser execution, human UAT, or live HTTP/database acceptance.

## Additional real-browser acceptance

A separate real Chromium/DjangoAPI/PostgreSQL run passed11scenarios, including nativeCancel/noPOST, pendingdouble-submit, softleave/idempotency, actualHostcancel409, permissions/CSRF and realDBsessionexpiry401. See [browser/API/SQL evidence and screenshots](task73-browser/README.md). This is assistant-operated automation, not humanUAT. The unit-only Not run statements below remain historical scope distinctions.

## Source and environment

- Tested source baseline: `7ac3dae1e66189d5347cd911d0b23067fba5aeed`; runtime leave code unchanged by this PR.
- Tested UI script: `frontend/static/js/myparty-leave.js`; LF-normalized SHA-256 `5a709d02617c7fe88d91d235b991f530a14eb24127387039a50787cb2145a4df`.
- Tests: `frontend/tests/myparty-leave.test.cjs` in this PR; raw output: [task73-ui-unit.log](task73-ui-unit.log).
- Environment: `node:22-alpine` container via Docker; no database, backend server, or TU account required for this unit test run.

## Reproduction

- Run `MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd):/app" -w /app node:22-alpine node --test --test-reporter=spec frontend/tests/myparty-leave.test.cjs` from the repository root. Expected: all tests pass, zero failures.

| Case | Fixture / action | Expected | Actual |
| --- | --- | --- | --- |
| UT-US4-UI-01 | Click cancel in confirm/close dialog | Does not call leave API and keeps data/card intact | Pass |
| UT-US4-UI-02 | Confirm leave action while request is pending | Disables button and prevents duplicate/second submission | Pass |
| UT-US4-UI-03 | Mocked leave success response | Refreshes member list/count, removes card, and updates remaining slots correctly | Pass |
| UT-US4-UI-04 | Mocked 500/409/network,403,401 | 500/409/network offer refresh;403 is scoped to Party;401 clears protected data and navigates to Login; no false success | Pass |

Result after review fixes: **9 tests passed** on Node22-alpine. The earlier eight-test log did not contain a Cancel case; the report no longer relies on that untested claim.

The added Cancel test checks modal close, zero API calls, unchanged cards and an enabled opener. The pending test also checks Escape cancellation is prevented. The success test asserts both `/leave` and Detail calls and exact server-derived member_count1/remaining_slots6, rather than only matching a generic success message.


## Not run / remaining Task73 acceptance

- Actual Chromium/browser flow and native modal interaction: **Not run in this unit test scope**.
- Live HTTP/PostgreSQL integration: **Verified separately via backend test suite / CI**.