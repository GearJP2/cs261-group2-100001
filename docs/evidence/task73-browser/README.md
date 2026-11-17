# Task73 — real browser / API / PostgreSQL evidence

Verified17November2026 byCodex (assistant-operated). Source PR181 baseline7ac3dae; runtime source hashes below match the isolated app used for PR180, since PR180/181 changes only tests/evidence. Synthetic verified sessions, no live TU login.

**11 scenarios passed: native browser4 and direct HTTP7.** No API response mocked. Project`s2-task93-browser`, DB`s2_task93_browser`, localhost25880/25480. Chromium156; backendPython3.12.15/Django5.2.18/PostgreSQL17.11.

| Scenario | Expected | Result |
|---|---|---|
| B01-native-cancel-and-eligibility | Host/started/cancelled/Pending disabled; cancel/Escape send zero POST, no domain mutation | Pass |
| B02-native-confirm-double-submit-reload | one realPOST200; softleft once; requests/capacity/history unchanged; count1/slots2; focus/reload correct | Pass |
| A01-idempotent-retry | repeat realAPI200 sameleft_at; no mutation | Pass |
| B03-live-state-change409 | realcancel→leave409, no leave mutation, reload shows disabled state | Pass |
| A-nonmember | 403; no domain mutation | Pass |
| A-host | 403; no domain mutation | Pass |
| A-pending | 403; no domain mutation | Pass |
| A-started | 409; no domain mutation | Pass |
| A-forged-actor | 400; no domain mutation | Pass |
| A-missing-csrf | 403; no domain mutation | Pass |
| B04-real-session-expiry401 | realDBsessionexpiry→POST401/login; privatecardsgone; domain unchanged | Pass |

## Evidence

- [Requests/results and raw SQL snapshots](results.json), [execution log](execution.log)
- [Successful soft leave](leave-saved.png), [real expired session returns to Login](expired-session-login.png)
- [Guarded fixture seed](seed-fixture.py), [browser runner](browser-runner.py)
- Node22 UI unit tests: **9 passed**; [raw log](../task73-ui-unit.log)
- Combined PR180/181 frontend tests: **32 passed**; [raw log](../task73-frontend-combined.log)
- Shared backend source matches the isolated app verified for PR180: make verify713discovered/712passed/1legacyNo-showplaceholder skipped, smoke passed. [PR180 evidence](https://github.com/GearJP2/cs261-group2-100001/blob/1e27d93/docs/evidence/task93-browser/README.md). This is reuse of the same backend run, not a second full-suite claim.

## Invariants

Native Cancel/Escape sends zero leave POSTs. Pending confirmation disables controls and ignores a second submit while its real POST is delayed300ms before forwarding. Success writes only one left_at, preserves Party capacity, row history and Approved request metadata, displays member_count1/remaining_slots2 from Detail, and remains absent after reload. Native close focus is checked with Playwright’s wait for the asynchronous close event. A repeat API leave returns identical left_at/body without mutation.

A Host cancels a Party through the real API after the member page rendered: leave returns409, shows refresh and reload produces disabled eligibility. The final session case waits for initial background requests to settle, then expires the actual Django session row in the isolated database: leave returns401, Login opens and private cards disappear. Permission/CSRF errors compare full fixture domain snapshots before/after.

## Harness retests

The initial immediate close-focus assertion raced the native close event; it was replaced with an auto-wait focus check. The first expiry attempt overlapped initial background Members fetches, so they redirected on401 before the expected leave POST. The final test waits for network idle before expiry and passes. [Focus harness log](harness-initial-failure.log), [expiry harness log](session-expiry-harness-failure.log), [partial results before that retest](partial-before-expiry-harness-fix.json) are retained. These are test-driver orchestration fixes, not hidden runtime fixes.

## Reproduction and limits

Run against a fresh isolated DEBUG PostgreSQL database named`s2_task93_*` and a matching app/session SECRET_KEY. Install pinned backend requirements plus Playwright in a disposable environment. Set TASK73_CONFIRM_TEST_DATABASE=yes, TASK73_FIXTURE_FILE to a new private JSON path outside Git, TASK73_OUTPUT_DIR to a new directory, TASK73_BASE_URL to loopback HTTP, and TASK73_CHROME to an installed Chromium executable. Run seed-fixture.py then browser-runner.py. Both scripts require explicit test DB confirmation; previous fixture/evidence files are not overwritten. Cookie values stay in the chmod0600 private fixture and are not in results/logs.

This is real browser automation/API/PostgreSQL with synthetic users. It does not exercise live TU credentials, production load, or constitute human UAT/sign-off. No runtime bug found in these11scenarios; PR181 review fixes add the previously missing Cancel test and concrete success-count assertions.
