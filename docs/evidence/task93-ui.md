# Task93 — US14 UI handler regression evidence

[Issue #108](https://github.com/GearJP2/cs261-group2-100001/issues/108)

Verified 17 November 2026. This report records automated Node unit tests with controlled DOM/API dependencies for the US14 review dialog handler (`frontend/static/js/myparty-review.js`) and template structure (`frontend/templates/partials/review_history_content.html`), not live browser execution, human UAT, or live HTTP/database acceptance.

## Additional real-browser acceptance

The earlier unit-only Not run statements below describe that unit run. On 17 November2026, a separate **real Chromium + Django API + PostgreSQL run passed23scenarios**, including native validation, double submit, real201/409, review-to-profile summary, pagination, CSRF/permissions and SQL/cache invariants. See [browser/API/DB report and screenshots](task93-browser/README.md). Docker make verify713discovered/712passed/1existing skip and make smoke passed. This remains assistant-operated automation, not human UAT or live TU login.

## Source and environment

- Source baseline commit: `71a1ace006d72f33bf48685fe650e9aba039e09e`.
- Hash convention: decode source as UTF-8, normalize CRLF to LF, then calculate SHA-256 of the UTF-8 bytes. The previous script hash used CRLF; these normalized hashes match Git LF files.
- Tested UI script: `frontend/static/js/myparty-review.js`; SHA-256 `ccd3dfe856361994c6aaa2cca26b8c522dec53f2578a5cd02ab3d116d7c576e3`.
- Tested template partial: `frontend/templates/partials/review_history_content.html`; SHA-256 `38b060cc2d3978f0f86c7afe88ddf097e4b9e878d6a0debd0a3224742e3e90e8`.
- Related backend template tag module (not executed by these Node tests): `backend/core/templatetags/review_ui.py`; SHA-256 `a34f5c7abdedc72e24fec8c96fc129812eeae19b9cd2c173b37311370f250041`.
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

## Review fix verification — 17 November 2026

- Read the exact `frontend/templates/partials/review_history_content.html` path directly. Missing files now fail the test instead of skipping template assertions.
- Reran `node frontend/tests/myparty-review.test.cjs`: four passed on Node24.17.0/Linux. The raw log below is from this rerun; the original run used the Node22 container described above.
- Negative check: temporarily made the partial unavailable in the isolated test worktree; the test exited nonzero with ENOENT. Restored the file and reran successfully. This demonstrates that missing-template coverage cannot silently disappear.
- Checked all three reported SHA-256 values after LF normalization; all match.
- No production code, template, backend or dependency changes. This verification adds no browser/UAT claims.


## Not run / remaining Task93 acceptance

- Actual Chromium/browser flow, native `<dialog>` modal focus/escape behavior, and live DOM rendering: **Not run in this unit test scope**.
- Live HTTP/PostgreSQL, TU login, and full Docker integration tests (`backend/core/test_review_ui.py`): **Verified separately via backend test suite / GitHub CI**, not treated as human browser UAT.
- Human Manual UI/UAT and named teammate sign-off: **Not run / not asserted**.