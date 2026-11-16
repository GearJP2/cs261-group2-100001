# Task72: leave error recovery

PR #175 / Issue #87. Verified 16 November 2026.

- HTTP errors expose a reload button instead of leaving the user at a disabled trigger with no recovery. Reload reads current server state before another explicit leave; no automatic replay across membership cycles.
- HTTP 401 removes joined cards, member data and the created/history panes, then navigates to `/login/`. This also applies if the detail refresh loses its session after a successful leave.
- HTTP 403 and Party-specific updates affect only the matching Party. Other Parties' members and counts remain intact.

## Verification

`node frontend/tests/myparty-leave.test.cjs`: 7 tests passed. Covers 500, 409, network error, 401 during leave/detail refresh, scoped 403, and pending double submission. Uses controlled API/DOM dependencies and the actual production script. CI now runs every `frontend/tests/*.test.cjs` file.

Existing search regression tests: 5 passed. JavaScript syntax and `git diff --check` passed.

Chromium 156 used the actual Django-rendered `joined_party_content.html`, leave script and stylesheet, served by a temporary loopback HTTP fixture:

| Controlled API response | Observed result |
| --- | --- |
| Leave 500 | Refresh button visible; no automatic retry; current card preserved |
| Leave 401 | Browser navigates to login; protected joined/created/history data absent |
| Leave 200, detail 401 | Same login navigation |
| Leave 403 | Current Party error; other Party count and member list intact |
| Leave 200, detail 200 | Current card removed; member_count=1, remaining_slots=2; other Party intact |

Browser responses were simulated through the request helper, not a live backend/database or TU authentication. No backend/schema/dependency changes. Docker/full PostgreSQL suite were not rerun locally; GitHub CI runs the existing verification workflow separately. This is not human UAT or a named teammate's sign-off.
