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

Frontend service/DOM/browser tests and instructions are in [frontend testing](../../frontend/docs/testing.md). The browser backend entry point `tests/browser_server.py` uses the isolated settings and temporary SQLite file, creates synthetic users/patients, and listens only at `127.0.0.1:5018`. Playwright owns its lifecycle; normal SIGTERM removes its temporary workspace. It must not be used as a development/production server. Browser-only request quotas are raised for shared synthetic accounts/IP across all viewports; throttle classes remain enabled. Focused HTTP tests separately exercise 429 responses, Retry-After and per-user isolation at controlled limits. Production request quotas are unchanged.

## Coverage tooling

Coverage is optional test tooling; runtime requirements remain unchanged. Install `coverage` in a separate test environment, then:

```bash
python -B -m coverage run --source=apps,core --omit='*/migrations/*' tests/run.py
python -B -m coverage report --omit='*/migrations/*'
```

Measured coverage for the original 134 tests: **69%** of 7,750 backend statements. Node's separate JS measurement was **84.98% lines**, **83.99% branches**, **69.76% functions** in imported production JS. These historical baseline measurements have not been recalculated for the expanded suite. They do not establish whole-system correctness or complete branch coverage.

## Patient workflow expansion (2026-10-11)

`tests/test_patient_http.py` adds **34 HTTP integration tests**, plus three shared renderer regression cases in `tests/test_core.py` and two rate-limit HTTP cases in `tests/test_api.py`. The full **173-test** suite passes on this session's Python 3.14.4 / Django 5.2.9 / DRF 3.15.1 test runtime. Additional packages were installed only in a disposable `/tmp` virtual environment; project requirements and lockfiles were preserved. This is a separate runtime result from the earlier installed Django 6 run below, and does not complete the pinned supported-Python matrix.

- Every longitudinal record kind round-trips through real serializers/endpoints. Corrections and retirement preserve history; parent versions, missing/stale writes, replay, primary-contact conflicts, invalid request shapes and cross-patient references are checked for atomicity.
- Scope and permissions are tested independently: a default receptionist with patient scope can read clinical records but cannot edit them; removing clinical permissions also hides reads and clinical correction history. Unassigned doctors cannot access patient records.
- Verification stamps use the authenticated actor; identity/provenance changes demote old verification. Follow-up owners and visits must belong to the current team/patient; representative date ranges must be valid.
- Care-team HTTP additions/removals retain dated history, bump parent versions and revoke non-author access. Stale requests, replay and unauthorized management are covered.
- Real multipart uploads exercise MIME checks, provenance, checksums, downloads, independent document versions, retained bytes after archive, missing storage, cross-patient routes and cleanup after rejected metadata.
- Merge HTTP tests exercise source/target versions, content digests, requesting-admin binding, required reasons, tampered tokens, authorization, survivor identity and immutable signed snapshots.

All database/file inventory is synthetic and isolated. The browser expansion exposed a confirmed HTTP framing defect: JSON envelopes were emitted for `204 No Content`, causing the Vite proxy to reject document-archive responses. `core/renderers.py` now emits empty bytes for 204/205/304 while preserving ordinary success/error envelopes. Regression tests check the renderer directly and persisted idempotent-replay bytes, because Django’s test client itself strips 204 bodies and can conceal this defect.

## Runtime findings and limits

The earlier installed Python 3.14 / Django 6.1.2 run established the original 134-test baseline; the expansion runtime/results are listed above. A separate temporary pinned Django 5.0.6 / DRF 3.15.1 probe on Python 3.14 ran the original 124 cases but hit two errors inside Django's template `Context.__copy__` when rendering CSRF denials. No runtime dependency was changed to hide this. The pinned stack needs verification on its supported Python runtime; do not treat that probe as a passing compatibility matrix.

Tests identified protected auth actions whose `@action` permission overrides were bypassed by explicit URL mapping. Explicit permission selection now rejects anonymous `me`, `logout`, and `change-password` calls. Default patient CSV/XLSX exports also passed an empty field list and were rejected; absent fields now invoke the service defaults, while explicit invalid fields remain invalid.

SQLite tests exercise sequential stale writes and rollback, not PostgreSQL locking or concurrent writers. PDF tests check actual rendering/bytes and issuance contracts. Requested Arabic/font/pagination/print checks and browser workflows now pass; see [the detailed verification record](pdf-workflow-verification.md). No production build, project database mutation or migration change was performed for this suite. Latest counts are in [completed work](doneCurrent.md).

## PDF and complete browser workflows (2026-10-11)

Latest full suite: **174 backend tests passed**. Recovery now includes a deterministic full-microsecond signed-timestamp regression. The separate PDF inspector passed **6 checks**, covering five long template fixtures and all 18 actual browser PDF/print artifacts. [Commands, embedded fonts, review samples, browser matrix and corrections](pdf-workflow-verification.md).

## Task and notification HTTP expansion (2026-10-11)

Added **19 endpoint tests** in `tests/test_task_notification_http.py`. Full **193 backend tests passed** on Python 3.14.4 / Django 6.1.2 / DRF 3.18.3, using the existing clinic interpreter with isolated test settings. Runtime versions/requirements were unchanged.

- Tasks: real serializers, optional null due dates, protected actor/lifecycle fields, invalid-create atomicity, permission grants independent of role, own/unassigned/foreign scope, self-assignment and reassignment rules, reminder resets, `If-Match`/missing/conflicting/stale versions, terminal metadata and reason validation, invalid transitions/edits, completion/reorder/delete replay, atomic rejected reordering, and scoped search/status/overdue behavior.
- Notifications: cursor pagination and user-wide unread counts, unread filtering, foreign retrieve/delete denial and scoped mark-read no-op, repeated reads, bulk read/delete retaining unread/foreign rows, read-only content endpoints and anonymous action denial.

Focused command:

```bash
python -B manage.py test tests.test_task_notification_http --settings=config.settings.testing --noinput
```

No backend production change was necessary. The corresponding frontend regressions exposed task creation and stale-list/availability defects; [coverage and corrections](../../frontend/docs/testing.md). These checks use synthetic in-memory SQLite and do not establish PostgreSQL concurrent-writer behavior or pinned-runtime compatibility.
