# Task94 / US14: No-show follow-up evidence

Run: 17 November 2026, against main `2256998` plus the test changes in this PR. Runtime source is unchanged. Exact tested source hashes are in [http/results.json](http/results.json).

## Results

- Real HTTP + PostgreSQL: **24 passed, 0 failed**. No mocked HTTP responses or service calls in this acceptance run.
- Targeted isolated unit tests (`conduct.test_policy conduct.test_reviews_unit`): **37 passed**, no skips.
- `make verify`: **716 backend tests passed, no skips**, including controlled-clock boundaries and concurrency tests; Django checks, migration drift, Ruff and formatting pass. See [verify.log](verify.log).
- `make smoke`: passed after restoring `NO_SHOW_ENABLED=false`. See [smoke.log](smoke.log).

The obsolete skipped policy placeholder is replaced by a real public-serializer unit test. Three additional credit unit tests check the approved constants, first/existing/negative balances and duplicate ledger handling. Existing database/concurrency coverage remains in place.

## HTTP / SQL acceptance

[Execution log](execution.log), [raw results and SQL snapshots](http/results.json).

| Area | Verified result |
| --- | --- |
| Flag off | Authenticated/anonymous requests return 404; CSRF middleware still rejects missing CSRF with 403. No database writes. |
| Access | Anonymous 401; unverified account, outsider and participant who left before completion 403. |
| Input | Self-report, nonparticipant, unknown target, boolean ID and actor injection rejected with 400. |
| Party/window | Future/cancelled party 409; nine-day-old party 409; missing party 404. |
| Threshold | First report leaves credit NULL; Host second report reaches threshold and creates one deduction, credit 95. |
| Duplicate | Same reporter gets 409; third distinct reporter adds no second deduction. |
| Existing balance | Another party changes 95 to 90, preserving the previous balance. |
| Negative credit | Existing -2 becomes -7; no unapproved floor. |
| Public fields | Each 201 response contains only id, party_id, reported_id and created_at. |
| Independence | Existing star-review rows and rating caches remain identical across every No-show request. |
| Flag restored | Turning the flag off retains reports, ledger and credit; subsequent request returns 404 without writes. |

Every denied request compares full fixture report/ledger/profile/review snapshots before and after. Successful requests verify ledger counts and the relevant balance. All fixtures are synthetic. Existing star reviews are prepared using the service before HTTP testing; they are setup, not a claimed HTTP action.

## Reproduction and isolation

Use `scripts/us14-noshow-api-evidence.py --help` in the project Python environment with the database environment loaded. It requires `--confirm-test-database`, DEBUG, PostgreSQL database name starting `s2_task94_`, a loopback HTTP URL, a dedicated Compose project starting `s2-task94-`, env/overlay paths and a new output directory. The overlay must inject `NO_SHOW_ENABLED: ${TASK94_FLAG:-false}` into the backend and use the same disposable database. Do not point it at a shared database.

The recorded run used project `s2-task94-noshow`, database `s2_task94_noshow`, API port 25894 and PostgreSQL port 25494. Synthetic verified sessions reuse the existing US10 evidence helper; session cookies and secrets are not recorded. The script recreates only this project's backend to test the flag and restores false at successful completion. If interrupted, restore false or remove this disposable project before reusing it.

## Limits and acceptance

This is automated HTTP/API/database evidence, not human UAT or live TU login. Exact seven-day microsecond boundaries are covered by controlled-clock integration tests, not asserted through network timing. Production load was not tested. No deployment flag, production data, migrations or policy values were changed.

This evidence supersedes the old Task94 note that No-show was skipped or lacked an API retest; historical reports remain unchanged. Technical checks pass. The follow-up PR still requires the team's review and merge before final acceptance.
