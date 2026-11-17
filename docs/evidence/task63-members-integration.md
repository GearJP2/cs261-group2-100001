# Task63 — Members refresh integration with Task55

PR #179 / Issue #78; verified 17 November 2026 by Codex.

PR177 is merged into main. This branch also includes PR178's corrected Task55 fixture/evidence so the shared Approve handler is tested with its new PartyMembers dependency. Merge PR178 before PR179 to keep the final diff scoped to Members integration.

## Reproduction and actual results

Run `node frontend/tests/myparty-requests.test.cjs`: **8 tests passed**. Uses the actual inline handler from `frontend/templates/myparty.html` with controlled DOM/API dependencies.

| Additional integration case | Expected | Actual |
| --- | --- | --- |
| Approve 200, Members request pending | Refresh the matching Party, keep loading state and defer reload until Members settles | Pass |
| Approve 200, Members unauthorized | Stop the handler's normal reload/success flow; the Members component owns login navigation | Pass |
| Approve 200, Members returns loading error | Preserve the committed Approve success and request a reload; do not offer duplicate Approve as if POST failed | Pass |

The shared five Task55 cases continue to pass with the Members dependency, including CSRF header and escaped names. These are Node component tests, not a real browser, human UAT, or proof of PostgreSQL mutation.

Run each file in `frontend/tests/*.test.cjs` with Node: **27 cases passed** across requests8, leave8, members4, navigation2 and search5. Raw output: [task63-frontend-tests.log](task63-frontend-tests.log). The existing CI wildcard runs all five test files.

## Limits

No runtime/backend/schema/dependency changes were needed for the review fixes. Docker/full PostgreSQL suite, native browser and TU login were not rerun locally in this fix. CI is reported separately. Task55's actual browser/manual acceptance remains Not run as recorded in [its corrected report](task55-ui.md); these tests do not close the full UI acceptance task or assert a teammate's sign-off.
