# Task93 — real browser / API / PostgreSQL evidence

Tested source: `eff8b799efc08538d6637d146d244147f689ccc3`. Executed 2026-11-17T05:00:48.855361+00:00 to 2026-11-17T05:00:56.226999+00:00. Tester: Codex (assistant-operated), not human UAT.

## Result

**23 scenarios passed: 10 native-browser scenarios and 13 direct HTTP permission/validation checks.** All use the running Django application and PostgreSQL. No API response was mocked. One native POST was delayed before forwarding to inspect pending/duplicate-submit behavior.

Docker project `s2-task93-browser`, database `s2_task93_browser`, application localhost:25880 / database localhost:25480. Backend Python3.12.15/Django5.2.18/PostgreSQL17.11; Chromium156, Python3.12.0/Playwright for browser orchestration. Synthetic roles/verified sessions are installed using the existing test helper; live TU authentication is not exercised.

| Scenario | Expected | Result |
|---|---|---|
| B01-eligibility-keyboard | exclude self/early/future/cancelled; Tab avoids background controls; Escape returns focus | Pass |
| B02-native-required-whitespace | missing rating/blank comment block POST and preserve DB | Pass |
| B03-native-maxlength | textarea limits entry to500 characters | Pass |
| B04-real201-double-submit-reload | one POST/one row, rating_sum5/count1/credit unchanged; reviewed target persists | Pass |
| B05-profile-live-summary-xss | profile loads saved review via real API; average5.0,count1; HTML inert and credit separate | Pass |
| B06-rating1-and-live-average | rating1 accepted on anotherParty; profile average(5+1)/2=3.0 | Pass |
| B07-real409-conflict | stale form receives real409, target disabled, DB/cache unchanged | Pass |
| A-rating0 | 400; no mutation | Pass |
| A-rating6 | 400; no mutation | Pass |
| A-rating-bool | 400; no mutation | Pass |
| A-comment501 | 400; no mutation | Pass |
| A-self | 400; no mutation | Pass |
| A-early-target | 400; no mutation | Pass |
| A-future | 409; no mutation | Pass |
| A-cancelled | 409; no mutation | Pass |
| A-unknown-party | 404; no mutation | Pass |
| A-csrf | 403 CSRF_FAILED, no mutation | Pass |
| A-outsider | no eligible history; POST403, no mutation | Pass |
| A-early | no eligible history; POST403, no mutation | Pass |
| A-anonymous-list | 401 without verified session | Pass |
| B08-live-pagination-public-fields | 11 reviews; pages10+1; average3.82(API)/3.8(UI); public allowlist; credit unchanged | Pass |
| B09-profile-empty | no reviews shows empty/null summary and hides error/pagination | Pass |
| B10-account-isolation | reviewed status scoped to reviewer, even in same browser context | Pass |

## SQL and runtime checks

- Saved target receives 11 reviews: rating_sum42, rating_count11, API average3.82, UI average3.8. Credit remains NULL and is displayed separately. Another target receives one concurrent-review fixture; final stored review rows12.
- The profile fetches real pages of10 and1 reviews; next/previous navigation and public-field allowlist checked. HTML in a saved comment remains literal text and is not executed.
- Rejected validation/state/permission/CSRF requests compare complete fixture review/cache snapshots before and after; no mutation.
- `make verify` through the isolated Docker Compose project passed: **713 discovered, 712 passed, one existing US14 No-show placeholder skipped**. Skip is not Pass and does not imply the approved policy is missing.
- `make smoke` passed against the running project. Native browser page errors: zero. Smoke itself is not used to infer JavaScript behavior.

## Artifacts

- [Full scenario results and SQL before/after](results.json)
- [Execution log](execution.log), [Docker startup](startup.log), [make verify](verify.log), [make smoke](smoke.log), [runtime versions](runtime.json)
- [Saved review dialog](review-saved.png), [profile page1](profile-page1.png), [profile page2](profile-page2.png)
- [Seed script](seed-fixture.py), [browser runner](browser-runner.py)

The first harness attempt required every Tab stop to remain inside dialog DOM. Chromium may place focus at browser chrome/body. That harness assertion failed before any review writes; the corrected check allows body/browser chrome while excluding background page controls and still checks Escape/focus restoration. [Original harness failure](harness-initial-failure.json) is preserved; it is not presented as a product regression.

## Reproduction

Use a fresh local DEBUG PostgreSQL database whose name starts `s2_task93_`, with migrations applied and a matching running app/session SECRET_KEY. Both scripts require `TASK93_CONFIRM_TEST_DATABASE=yes`. Use normal Django environment variables for the test DB; do not use a development/production database.

In a disposable Python environment install the pinned backend requirements plus Playwright. Set:

```text
TASK93_CONFIRM_TEST_DATABASE=yes
TASK93_FIXTURE_FILE=/tmp/new-private-task93-fixture.json
TASK93_OUTPUT_DIR=/tmp/new-task93-evidence
TASK93_BASE_URL=http://127.0.0.1:25880
TASK93_CHROME=/path/to/chromium-or-chrome
```

The fixture path and output directory must be new. Run `python docs/evidence/task93-browser/seed-fixture.py` then `python docs/evidence/task93-browser/browser-runner.py`. The fixture file holds synthetic session cookies, is chmod0600, and must stay outside version control. Neither logs nor results store cookie/token values. The runner only permits loopback HTTP and preserves prior evidence instead of overwriting it.

The recorded full verification used the repository Makefile with a separate Compose project and env/overlay files in /tmp. The overlay selects a dedicated image, env_file and blank TU key; default localhost ports were overridden to25880/25480. No shared service/volume was changed.

## Limits

This is browser automation + real backend/API/DB with synthetic users. It is not live TU login, human UAT/sign-off, production-load testing, No-show acceptance, or the full cross-story Sprint2 integration flow. Native rating/comment validation, error409, account isolation and review→profile summary are covered by this run.
