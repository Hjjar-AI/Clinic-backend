# Backend tests by source area

Latest installed-runtime outcomes and compatibility limits: [completed](../doneCurrent.md); [open checks](../workCurrent.md). Synthetic inventory only; tests never load clinic `.env`, database, media, backups or external cache.

## Commands (activated backend environment)

```bash
python -B tests/run.py
python -B manage.py test tests --settings=config.settings.testing --noinput
python -B manage.py test tests.test_task_notification_http --settings=config.settings.testing --noinput
python -B -m coverage run --source=apps,core --omit='*/migrations/*' tests/run.py
python -B -m coverage report --omit='*/migrations/*'
```

Coverage is optional isolated test tooling, not a runtime-requirements change. `tests/run.py` fixes settings/refuses overrides and non-memory databases. Testing settings disable `.env`/migration modules, create current model schema in memory, use synthetic secrets/hashers/local cache and temporary media/backups/static. Import/recovery/reminder fixtures are isolated. Migration files are not inspected or changed.

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

## Detailed file contracts

| Test / supporting files | Coverage and interpretation |
| --- | --- |
| `tests/test_patient_http.py` | All longitudinal serializers/endpoints; reasons/history/parent versions, missing/stale/replayed writes, primary-contact conflicts/request shape/cross-patient atomicity; separate scope and clinical permissions, receptionist read versus edit, unassigned denial; server verification actor/demotion/provenance, follow-up owners/links/date ranges; dated care-team add/remove and access revocation; multipart MIME/checksum/provenance/download/document versions/archive bytes/missing storage/rejected metadata cleanup; merge actor/digest/versions/reason/tampered token/survivor/signed snapshots. |
| `tests/test_core.py`, `tests/test_api.py` | Empty 204/205/304 actual-renderer and persisted-idempotency bytes (Django client strips 204 bodies); 429/Retry-After/per-user isolation. Explicit auth action permissions and default export field regressions. |
| `tests/test_task_notification_http.py` | Task protected actor/lifecycle fields/null dates/invalid-create atomicity, grants independent of role, own/unassigned/foreign scope, assignment/reminder resets, body/header version conflicts, terminal metadata/reasons/invalid transitions, completion/reorder/delete replay, atomic reorder rejection, scoped search/status/overdue; notifications cursor/unread counts/filtering/foreign denial/no-op reads/bulk read-delete/read-only content/anonymous denial. |
| Recovery tests / `backup_creator.py` | Signed full ZIP/model/media/digest/count/path/scope validation, transactional replacement and session revocation, exact issued bytes/payment/signed datetime microseconds; catalog merges do not replace clinical history. |
| `tests/browser_server.py` | Only Playwright-owned `127.0.0.1:5018`, temporary SQLite/media and synthetic accounts/patients including independent panel users per viewport. SIGTERM cleans workspace; never use as clinic server. Increased fixture quotas preserve throttle classes/production rates. [Frontend commands/matrix](../../../frontend/docs/testing/guide.md). |
| `tests/pdf_appearance.py` | Separate DB-forbidden inspector, five long templates plus 18 actual browser PDFs, embedded fonts/Arabic/A4/bounds/pages/rows/decimals/print; [commands and sample limits](pdf.md). |

Original coverage baseline: **69% of 7,750 backend statements** before expansions; not recalculated and not a whole-system correctness claim. SQLite proves sequential conflicts/rollback, not PostgreSQL locking/concurrent writers. Pinned Django 5.0.6 / DRF 3.15.1 on Python 3.14 produced two template `Context.__copy__` errors rendering CSRF denials; verify on supported Python rather than change versions to hide the failure. Early source/stub probes are not equivalent to this real HTTP matrix. No production build or clinic-data changes for tests.
