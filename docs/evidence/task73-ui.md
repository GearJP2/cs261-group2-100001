# Task73 — US4 UI handler regression evidence

[Issue #88](https://github.com/GearJP2/cs261-group2-100001/issues/88)

Verified 17 November 2026. This report records automated Node unit tests with controlled DOM/API dependencies for the US4 leave dialog handler (`frontend/static/js/myparty-leave.js`) and template structure (`frontend/templates/partials/joined_party_content.html`), not live browser execution, human UAT, or live HTTP/database acceptance.

## Source and environment

- Tested UI script: `frontend/static/js/myparty-leave.js`.
- Tests: `frontend/tests/myparty-leave.test.cjs` in this PR; raw output: [task73-ui-unit.log](task73-ui-unit.log).
- Environment: `node:22-alpine` container via Docker; no database, backend server, or TU account required for this unit test run.

## Reproduction

- Run `MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd):/app" -w /app node:22-alpine node --test --test-reporter=spec frontend/tests/myparty-leave.test.cjs` from the repository root. Expected: all tests pass, zero failures.

| Case | Fixture / action | Expected | Actual |
| --- | --- | --- | --- |
| UT-US4-UI-01 | Click cancel in confirm/close dialog | Does not call leave API and keeps data/card intact | Pass |
| UT-US4-UI-02 | Confirm leave action while request is pending | Disables button and prevents duplicate/second submission | Pass |
| UT-US4-UI-03 | Mocked leave success response | Refreshes member list/count, removes card, and updates remaining slots correctly | Pass |
| UT-US4-UI-04 | Mocked leave error (500, 409, 403, 401) | Displays error message without false success, handles session/permissions properly, and offers refresh | Pass |

Result: **All tests passed**.

## Not run / remaining Task73 acceptance

- Actual Chromium/browser flow and native modal interaction: **Not run in this unit test scope**.
- Live HTTP/PostgreSQL integration: **Verified separately via backend test suite / CI**.