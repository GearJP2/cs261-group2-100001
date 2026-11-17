# Task65 / S2-US6-T-API — independent HTTP retest

17 November 2026. Assistant-operated execution requested by Gear, using synthetic verified sessions. This is a new run, not Austin's original log or human UAT. Base main `756b520667eb7672f9db4be3605cb0a5cc98d8f9`; runtime source unchanged, exact tested source hashes in [results.json](results.json).

## Result

**13/13 cases PASS**, plus successful Party Detail count comparison (14 domain HTTP requests; CSRF bootstrap requests are additional). Responses come from the real Docker runserver over loopback and PostgreSQL, without HTTP/service mocks.

| Case | Expected / actual |
| --- | --- |
| Anonymous | 401 AUTH_REQUIRED |
| Local account without university verification | 403 FORBIDDEN |
| Outsider | 403 FORBIDDEN |
| Pending requester | 403 FORBIDDEN |
| Rejected requester | 403 FORBIDDEN |
| Withdrawn member | 403 FORBIDDEN, history retained |
| Member of another party | 403 FORBIDDEN |
| Unknown Party | 404 NOT_FOUND |
| POST, with valid CSRF | 405 METHOD_NOT_ALLOWED, Allow: GET |
| Host | 200, active rows only, Host-first |
| Active member | 200, same list/count/order |
| Active member without profile | 200, fallback ผู้ใช้; no username |
| Actor ID query spoof by outsider | 403 FORBIDDEN |

All responses assert no-store. Every 200 checks exact envelope and member fields `{user_id, display_name, role}`, actual display names/roles, no synthetic private email/login values, count and Host-first order against a direct SQL active-row oracle. Host is inserted after other members to make the ordering assertion meaningful. Pending/Rejected and withdrawn IDs are excluded. All 13 cases assert unchanged full fixture membership/request/profile SQL snapshots, including retained withdrawal history and absent fallback profile. Party Detail returns the same count of 3.

## Verification

- `make verify`: 716 backend tests pass, no skips; Django/migration drift/Ruff/format pass. [verify.log](verify.log)
- `make smoke`: passes. [smoke.log](smoke.log)
- Raw requests, expected/actual, response JSON/headers, SQL before/after, fixture IDs and source hashes: [results.json](results.json)

## Reproduce

Use a disposable Docker Compose database/API built from this revision. Load its database environment into the local Python process, then run:

```sh
python scripts/us6-members-http-evidence.py --confirm-test-database --base-url http://127.0.0.1:25865 > task65-http.json
```

Requires DEBUG, PostgreSQL name beginning `s2_task65_`, explicit confirmation, and loopback HTTP. The helper creates unique synthetic users/parties without deleting existing rows, and reuses the existing US10 Browser session/CSRF helper. Cookies, session keys and CSRF tokens are not logged. The recorded run used DB `s2_task65_http`, Docker project `s2-task65-http`, API port25865 and DB port25465. Remove only that disposable project/volume after execution. No deployment flags, runtime code, migration or dependencies change.

## Acceptance and limits

This fills the missing raw evidence and distinct Pending/Rejected HTTP gaps in issue80. Team review/merge is still required; this is not P's sign-off and does not recreate Austin's original files. Live TU login, human UI/UAT and production load are not run. Cross-story regression belongs to Task96.
