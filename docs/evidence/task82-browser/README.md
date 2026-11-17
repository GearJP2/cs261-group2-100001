# Task82 / S2-US2-T-UI browser acceptance

17 November 2026. Assistant-operated at Gear's request; not V/Net's test run or sign-off. Base main `b46bd06` plus this PR's tests/harness. No runtime/application changes were required.

## Results: 12 native browser scenarios PASS

Real Chromium + Django HTTP + isolated PostgreSQL. [Raw HTTP responses, expected/actual, SQL before-after and source hashes](run/results.json). [Execution log](execution.log).

| Scenario | Expected and actual |
| --- | --- |
| B01 pagination | 21 fixture matches; page1 has20, page2 has1; previous page restores the same ordered20. |
| B02 combined filters | q + sport + venue + Indoor + Bangkok date/09:00–11:00 returns exactly IndoorA, excluding sportB/outdoor/other titles. Six visible chips and exact URL params. Browser timezone deliberately America/New_York; Bangkok input/params remain correct. |
| B03 chip | Remove Indoor chip only; sport and other filters remain. |
| B04 reset | All controls/chips cleared; default Open query has only page=1. |
| B05 empty | Genuine HTTP200/total0 shows empty, not error. |
| B06 error | Invalid time range reaches real API400; visible error and hidden empty state. |
| B07 recovery | Clear invalid URL/filters recovers default actual results. |
| B08 old success | Hold an older real request, finish newer query first, then continue older request; newer IndoorA remains. Loading state visible while pending. |
| B09 old error | Hold invalid request, reset and finish new results, then continue real400; error stays hidden/default result remains. |
| B10 Full | Full fixture appears under Full filter; follow native Detail link; actual DetailAPI200/stateFull and no enabled join button for nonmember. |
| B10 InProgress | Started fixture appears; native DetailAPI200/stateInProgress; no enabled join. |
| B10 Cancelled | Cancelled fixture appears; native DetailAPI200/stateCancelled; no enabled join. |

Fixtures include21 page matches, sportA/sportB, Indoor/Outdoor, full/started/cancelled parties. The viewer is not the Host or a member of the restricted-state parties. The Full Party is filled by a separate account, so the disabled join check does not pass merely because the viewer already joined.

All scenarios assert unchanged fixture Party/membership/request SQL snapshots. These are read-only search flows; no mutation is expected. SQL before/after are recorded. Out-of-order tests hold/continue actual network requests; no route fulfill, invented response or mocked business service. Recorded Detail responses independently confirm the state of all three restricted parties.

Screenshots: [pagination](run/pagination.png), [combined filters](run/combined-filters.png), [real400/error](run/validation-error.png), [Full](run/full-detail.png), [started](run/inprogress-detail.png), [cancelled](run/cancelled-detail.png).

## Unit coverage and regression

- New `frontend/tests/search-ui.test.cjs`: **5/5 PASS**. Executes actual app.js closure functions with controlled dependencies: separate sport/venue/type/time params; reset/invalidation/page1; Full/InProgress/Cancelled card→Detail mapping; empty vs error; loading hides stale content.
- Existing `search-request-state.test.cjs`: **5/5 PASS**, stale success/error and reset during initialization. These are isolated Node tests, not browser evidence.
- All frontend tests run individually: **40/40 PASS**. [frontend.log](frontend.log), [new unit log](search-ui-unit.log).
- `make verify`: **717 backend tests PASS, no skips**, Django/migration drift/Ruff/format pass. [verify.log](verify.log).
- `make smoke`: PASS. [smoke.log](smoke.log).

No runtime bug reproduced in this scope, so there is no invented bug/retest record. The only changes are tests, guarded evidence tooling and artifacts. No dependency, schema, environment variable for deployment or runtime policy was added. The existing Search UI uses Detail links, rather than direct card join buttons; final join eligibility was checked on actual Detail pages.

## Reproduce / environment

Use project Python dependencies plus Playwright/Chromium in a separate tooling environment. Load the disposable database environment, run a matching Compose API on loopback25882, then:

```sh
TASK82_CONFIRM_TEST_DATABASE=yes TASK82_OUTPUT=/tmp/task82-new-output TASK82_CHROME=/path/to/chrome python scripts/us2-search-browser-evidence.py
```

Guard requires DEBUG, PostgreSQL database prefix `s2_task82_`, explicit confirmation and a new output directory. Fixed API is127.0.0.1:25882. Recorded project `s2-task82-browser`, DB `s2_task82_http`, PostgreSQL port25482. Unique synthetic fixtures only. Reuses the existing US10 helper to create synthetic verified sessions; cookies/tokens are not recorded. Exact versions, fixture IDs, timing, source SHA256 and tested base commit are in results.json; [complete source manifest](source-manifest.json) also includes Node tests. Remove only this disposable project's containers/volume afterward.

## Acceptance / limits

This completes the technical/preparation/execution/report/evidence parts of Task82. Final Gear review/merge remains pending; the pre-existing closure of issue97 by RieroS is not acceptance of this new evidence. Do not attribute this run to V/Net. Not run: live TU login, human UAT, production load, exhaustive accessibility or full Task96 cross-story regression. Browser assertions are automated and screenshot evidence accompanies the actual network/SQL run.
