# Automated tests

## Safe entry point

From the backend with its environment activated:

```bash
python -B tests/run.py
```

Equivalent Django invocation:

```bash
python -B manage.py test tests --settings=config.settings.testing --noinput
```

`tests/run.py` fixes the test settings and rejects a settings override. `config/settings/testing.py` prevents `.env` loading, uses synthetic secrets, an in-memory SQLite database, local memory cache and temporary media/backups/static directories. The runner refuses a non-memory database. Current models create the test schema with migration modules disabled; project migration files are neither inspected nor changed. Recovery/import/reminder tests only operate on synthetic inventory. Test passwords/hashers are confined to test settings.

## Coverage map

| Area | Tests |
| --- | --- |
| Shared contracts | Mutation versions/If-Match, lifecycle transitions, constraint compatibility, Arabic identifiers/phones/search, dates, clinical JSON/labs, database checks |
| Accounts/HTTP | Real session login and CSRF, lockout, password changes/revocation, permissions, anonymous denial, scoped patient reads, envelopes/pagination/sorting, idempotency replay/payload mismatch/failure reuse |
| Patients | Unknown/year-only demographics, permanent file numbers, duplicates, corrections/version history, scoped teams, archive/restore, longitudinal records/follow-ups, explicit preview-bound merge and signed-snapshot retention |
| Visits/documents | Draft/sign/amend/lock, server signing, immutable revisions, follow-up, issued bytes/checksums/identity retention, preview ownership/staleness, renderer failure and actual PDF generation |
| Operations | Scheduling overlaps/adjacent slots/working bounds/rebooking/reminders, fractional billing and immutable paid snapshots, task lifecycle/roles/reordering and scoped notifications |
| Catalog/import/recovery | Catalog identity/version/retirement, scale answers/snapshots/ranges, real CSV/XLSX import/formula safety, preview/digest binding, transactional replacement, signed ZIP/media authentication/counts/scope/path protection, catalog merge/full recovery/session revocation |
| Reports/commands | Patient/dashboard/date scope, unknown demographics, zero-filled monthly series, paid-only revenue, cancelled appointments, filtered/formula-safe CSV, after-commit cache invalidation/rollback, audit protection, reminder dedupe and read-only media reconciliation |

Frontend service/DOM/browser tests and instructions are in [frontend testing](../../frontend/docs/testing.md). The browser backend entry point `tests/browser_server.py` uses the isolated settings and temporary SQLite file, creates synthetic users/patients, and listens only at `127.0.0.1:5018`. Playwright owns its lifecycle; normal SIGTERM removes its temporary workspace. It must not be used as a development/production server.

## Coverage tooling

Coverage is optional test tooling; runtime requirements remain unchanged. Install `coverage` in a separate test environment, then:

```bash
python -B -m coverage run --source=apps,core --omit='*/migrations/*' tests/run.py
python -B -m coverage report --omit='*/migrations/*'
```

Measured coverage for the final 134 tests: **69%** of 7,750 backend statements. Node's separate JS measurement was **84.98% lines**, **83.99% branches**, **69.76% functions** in imported production JS. These are baseline measurements, not whole-system correctness or complete branch coverage; no 100% claim or arbitrary threshold is imposed.

## Runtime findings and limits

The installed Python 3.14 / Django 6.1.2 environment is the primary verified runtime. A separate temporary pinned Django 5.0.6 / DRF 3.15.1 probe on the same Python 3.14 interpreter ran the original 124 cases but hit two errors inside Django's template `Context.__copy__` when rendering CSRF denials. No runtime dependency was changed to hide this. The pinned stack needs verification on its supported Python runtime; do not treat that probe as a passing compatibility matrix.

Tests identified protected auth actions whose `@action` permission overrides were bypassed by explicit URL mapping. Explicit permission selection now rejects anonymous `me`, `logout`, and `change-password` calls. Default patient CSV/XLSX exports also passed an empty field list and were rejected; absent fields now invoke the service defaults, while explicit invalid fields remain invalid.

SQLite tests exercise sequential stale writes and rollback, not PostgreSQL locking or concurrent writers. PDF tests check actual rendering/bytes and issuance contracts; Arabic visual quality, font/static asset resolution and print appearance remain unverified. No production build, project database mutation or migration change was performed for this suite. Latest counts are in [completed work](doneCurrent.md).
