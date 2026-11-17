# Task93 — US14 UI handler regression evidence

[Issue #108](https://github.com/GearJP2/cs261-group2-100001/issues/108)

Verified 17 November 2026. This report records automated Node unit tests with controlled DOM/API dependencies for the US14 review dialog handler (`frontend/static/js/myparty-review.js`) and template structure (`frontend/templates/partials/review_history_content.html`), not live browser execution, human UAT, or live HTTP/database acceptance.

## Source and environment

- Source baseline commit: `71a1ace006d72f33bf48685fe650e9aba039e09e`.
- Tested UI script: `frontend/static/js/myparty-review.js`; SHA-256 `a4f2d80e296f4708e4c433170a676dbeba7f131f530a33b3608189627e68c99f`.
- Tested template partial: `frontend/templates/partials/review_history_content.html`; SHA-256 `38b060cc2d3978f0f86c7afe88ddf097e4b9e878d6a0debd0a3224742e3e90e8`.
- Tested template tag module: `backend/core/templatetags/review_ui.py`; SHA-256 `a34f5c7abdedc72e24fec8c96fc129812eeae19b9cd2c173b37311370f250041`.
- Tests: `frontend/tests/myparty-review.test.cjs` in this PR; raw output: [task93-ui-unit.log](task93-ui-unit.log).
- Environment: `node:22-alpine` container via Docker; no database, backend server, or TU account required for this unit test run.

## Reproduction

- Run `MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd):/app" -w /app node:22-alpine node --test --test-reporter=spec frontend/tests/myparty-review.test.cjs` from the repository root. Expected: four tests pass, zero failures.

| Case | Fixture / action | Expected | Actual |
| --- | --- | --- | --- |
| UT-US14-UI-01 | `canReview: false` and already-reviewed target option; dispatch submit | Opener button and reviewed option are disabled; no POST request sent (`apiCalls = 0`) | Pass |
| UT-US14-UI-02 | Whitespace-only comment (`"   "`) submitted; then valid text input event dispatched | Sets custom validity `"กรุณาระบุความคิดเห็น"`, blocks submit (`apiCalls = 0`), updates live character counter on input | Pass |
| UT-US14-UI-03 | Keep review POST pending; trigger duplicate submit; resolve 201 response | Controls disabled while in-flight, duplicate submit ignored (`calls.length = 1`), trims comment, marks option `"— รีวิวแล้ว"`, resets counter, updates opener to `"รีวิวสมาชิกครบแล้ว"` | Pass |
| UT-US14-UI-04 | Mock 409 `REVIEW_EXISTS`, network failure, and inspect `review_history_content.html` | 409 disables target option and shows server message; network failure shows fallback error without false success; template renders empty state and star rating (1–5) separate from conduct credit | Pass |

Result: **4 tests passed**.

## Not run / remaining Task93 acceptance

- Actual Chromium/browser flow, native `<dialog>` modal focus/escape behavior, and live DOM rendering: **Not run in this unit test scope**.
- Live HTTP/PostgreSQL, TU login, and full Docker integration tests (`backend/core/test_review_ui.py`): **Verified separately via backend test suite / GitHub CI**, not treated as human browser UAT.
- Human Manual UI/UAT and named teammate sign-off: **Not run / not asserted**.