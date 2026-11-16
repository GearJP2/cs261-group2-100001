# Task 71: implementation and verification

Verified 2026-11-16 for PR #168.

Joined Parties now come from active memberships and Pending requests in PostgreSQL. Pending users, Hosts, cancelled Parties, and activities that have started cannot use Leave. A native confirmation dialog sends the existing CSRF-protected API request only after confirmation. Success removes the membership card and reloads counts through Party Detail; HTTP errors preserve the card, and ambiguous network results ask the user to reload before proceeding.

Browser checks with synthetic users: Pending/started buttons disabled; Escape cancels without POST; injected 404 preserves the card and displays the API error; real POST 200 removes the card, refreshes member_count=1 and remaining_slots=2, and remains absent after reload; closing returns focus to the page heading.

## Verification

- Added four Django integration tests covering real records, eligibility, escaped/server-rendered data and API persistence.
- Full backend suite: 669 tests, OK (one existing skipped test).
- Ruff lint and formatting, JavaScript syntax and git diff whitespace checks passed.
- Django checks and migration drift check passed; no migration required.
- Runtime smoke checks passed: HTTP, PostgreSQL readiness, template and static CSS.
- Chromium checks passed without JavaScript page errors.

Commands: `python backend/manage.py test backend --top-level-directory backend --noinput`, `ruff check backend scripts`, `ruff format --check backend scripts`, `python backend/manage.py makemigrations --check --dry-run`. Runtime smoke used `scripts.smoke.main()` with BASE_URL set to the isolated server.

Environment: Python 3.12.0, PostgreSQL 17 on an isolated local cluster, Chromium 156 with Playwright. Docker was unavailable, so these are native equivalents of the Makefile checks, not a claimed Docker `make verify` run. No production data or credentials were used in browser fixtures. Human peer review and merge approval remain separate from these checks.
