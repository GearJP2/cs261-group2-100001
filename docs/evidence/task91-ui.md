# Task 91: implementation and verification

Verified 2026-11-16 for PR #166.

Review history now uses completed, non-cancelled Parties and eligible participants from PostgreSQL. Review status belongs to (Party, reviewer, reviewee), survives reload, and never uses browser-local flags. The form submits through the existing CSRF-aware API helper; real HTTP errors remain errors. Star ratings use keyboard-accessible radio inputs and a native dialog. Pending submissions lock the form.

Browser checks with synthetic users: real POST 201; reload disables the saved target; another Party remains reviewable; changing accounts in the same browser preserves reviewer isolation; injected 404 displays the API error without marking a review saved; Escape closes the dialog.

## Verification

- Added four Django integration tests covering real records, eligibility, escaped/server-rendered data and API persistence.
- Full backend suite: 669 tests, OK (one existing skipped test).
- Ruff lint and formatting, JavaScript syntax and git diff whitespace checks passed.
- Django checks and migration drift check passed; no migration required.
- Runtime smoke checks passed: HTTP, PostgreSQL readiness, template and static CSS.
- Chromium checks passed without JavaScript page errors.

Commands: `python backend/manage.py test backend --top-level-directory backend --noinput`, `ruff check backend scripts`, `ruff format --check backend scripts`, `python backend/manage.py makemigrations --check --dry-run`. Runtime smoke used `scripts.smoke.main()` with BASE_URL set to the isolated server.

Environment: Python 3.12.0, PostgreSQL 17 on an isolated local cluster, Chromium 156 with Playwright. Docker was unavailable, so these are native equivalents of the Makefile checks, not a claimed Docker `make verify` run. No production data or credentials were used in browser fixtures. Human peer review and merge approval remain separate from these checks.
