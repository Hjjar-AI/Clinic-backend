# Completed and verified

As of **2026-11-07**. Model review 1–21, R1–R29 and requested billing/idempotency/cache/process-failure checks are complete. Current behavior: [contracts](contracts.md); pending items: [current](workCurrent.md).

| Check | Latest evidence |
| --- | --- |
| Backend PostgreSQL 18 | **283 passed**, owned disposable cluster; Python 3.12.16/Django 5.0.6/DRF 3.15.1. |
| Backend SQLite | **265 passed, 18 PostgreSQL-only skips**. |
| Concurrency/failure | 15 added cases: billing/version/payment/receipt/cache races and five real SIGKILL checkpoints. Waiting retries verify lock release, rollback or replay; interrupted restore verifies safety-copy inventory/media repair before reconciliation. |
| PDF | **14 passed**, including 23 actual browser PDFs across desktop/tablet/mobile and all six required document kinds. |
| Local launcher | 54 focused launcher/API tests passed; five real Linux process probes passed using temporary sockets/stub servers (shutdown/failure/partial start/timeout/occupied port). CSRF checks cover custom frontend origin, denied foreign origin/missing token. Shell syntax/help and isolated native lock/MIME/font/PDF checks passed. Windows process routing uses test doubles; native Windows execution remains unverified. No clinic config/storage, dependency install, schema or build changes during verification. |
| Frontend | [Frontend evidence](../../frontend/docs/doneCurrent.md) owns Node/Vue/browser results. |

Tests use synthetic isolated storage; cache is local-memory. Evidence does not certify shared-cache servers, external/distributed writers/storage, Windows/macOS, host/power loss, every failure point, physical printing, other browser engines or comprehensive accessibility. No production bundle/type-check certification. Schema/deployment tasks were removed, not verified.

Testing migration scripts were deleted by request; package markers remain. Models/full backups require the current schema/format 3; old DB/full-backup compatibility is absent. Clinic storage already exists: never bootstrap/reseed for verification. Helpers, runtimes, logs and artifacts persist in ignored `tests/tools/`; no clinic-storage or project dependency/version changes accompanied these checks.

## Environment and launch review — 2026-11-11

Reviewed backend `.env`/`.env.example`, settings consumers, backend wrappers/launcher and frontend forwarding wrappers. Private `.env` lacked launcher settings/explicit CSRF origins; added these and machine-specific Python/Node paths while verifying that every previous assignment remained unchanged. Separate signing keys are present; values were not logged. Expanded the template's grouped clinic/security/hours/upload/retention/demo settings to match supported options. Corrected private comments: `PDF_FONT_DIR` is consumed, and the scheduler uses `BACKUP_CHECK_INTERVAL_HOURS`. Launch scripts already avoid installation, migration and seeding; no script changes were necessary.

The user's existing comment drawing is now present in both `.env` and `.env.example`; matching prefixes and `git diff --check` verify the comment-only template addition.

`clinicon` is a Bash activation alias for `/home/mhmmd/Envs/clinic`. Its Python is **3.14.4** (supported: 3.10–3.12); ten packages differ from the exact requirements pins, including Django **6.1.2** versus **5.0.6** and DRF **3.18.3** versus **3.15.1**. Waitress and Portalocker are absent. Node **24.21.0** is installed through nvm but absent from this execution session's PATH; explicit private `CLINIC_NODE` resolves discovery.

Shell syntax/help and private configuration/key consistency checks passed. Actual `./start.sh --no-browser` and preflight attempts correctly stopped at unsupported Python before starting servers. A separate database-free `check_runtime --render-pdf` using the designated environment passed MIME/fonts/timezone/in-memory synthetic PDF and failed locking/WSGI imports. No full server startup, HTTP/UI flow, shutdown or native Windows execution was certified in this initial review. No test suites, builds, dependency/environment changes, schema operations or clinic data changes were performed during that review. The follow-up below resolves the launch blocker.

## Python 3.14 compatibility and launch — 2026-11-11

At the user's request, current shared requirements now match all ten newer installed package versions, including Django 6.1.2/DRF 3.18.3/pandas 3.0.6. The current dependency profile and launcher select Python 3.12–3.14 (3.14 recommended); it replaces the old Python 3.10–3.12 profile. Installed only the two missing pinned dependencies, Portalocker 4.3.0 and Waitress 3.0.2, into the designated `clinicon` environment. All applicable direct pins match installed metadata; `pip check` reports no broken requirements. Existing condition/check constraint compatibility already handles Django 6.1, so no model/schema changes were required.

`./start.sh check` passes on Linux/Python 3.14.4, including locks/WSGI/MIME/fonts/timezone and an in-memory synthetic Arabic/Latin PDF. Two real `./start.sh --no-browser` cycles passed Vite HTML (200), proxied config/envelope/CSRF cookie/credentialed CORS (200), backend health (200), denied unauthenticated patient access (403), graceful process shutdown and immediate restart. Both listening ports were released. These cycles used `DATABASE_NAME=:memory:` and temporary operation locks, without schema creation or clinic storage access. The check exposed POSIX TIME_WAIT false positives; launcher preflight now uses SO_REUSEADDR on POSIX, while permission failures report a separate remedy. Windows binding behavior remains unchanged.

Additional probes passed all model SELECT query compilation and a synthetic patient JSON serialization round trip with SQL execution explicitly blocked, production billing half-up arithmetic, production CSV/XLSX parsing/formula rejection, and a python-docx Arabic/Latin round trip. Shell syntax and `git diff --check` pass. Vite required no frontend source changes.

Limits: no test-suite inspection/execution, migrations/schema work, builds, clinic data changes, full authenticated clinical workflows, browser interaction, PostgreSQL execution or native Windows verification. Missing frontend `dist` produces the expected staticfiles warning; local Vite serves the UI. Historical suite results at the top of this page remain evidence for the earlier dependency profile, not this upgrade. [Remaining checks](workCurrent.md).

## Existing-database login failure — 2026-11-11

The user's real-launch output shows successful Waitress/Vite startup followed by login failure: an account save triggers the required durable cache-generation update, but `core_cachegeneration` is absent. Prior isolated startup checks did not establish compatibility of clinic storage. A SQLite connection opened with `mode=ro` and `PRAGMA query_only=ON` inspected table/column metadata only, without querying account/patient values or issuing schema/data writes.

Missing current tables: `core_cachegeneration`, `core_recoveryoperation`. Missing columns: `patients_patientfollowup.{completed_revision_id,method,outcome_at,outcome_by_id}`, `patients_patient.primary_identifier_id`, `visits_visit.follow_up_id`, `appointments_appointment.reminder_generation`, `tasks_usertask.reminder_generation`, `notifications_notification.{category,entity_id,entity_type,occurrence}`. This inventory is a minimum incompatibility finding; it does not certify existing types, constraints, indexes or historical-data reconciliation. A complete data-preserving schema repair needs separate authorization; no migration/bootstrap/seed/reset was run and cache-generation guarantees were not weakened.

Other output: pre-login protected-resource 403 responses do not explain the login 500. The missing `dist` warning concerns absent production assets while Vite serves development assets. Vite's public-CSS warning traces to the existing `src/main.js` import of `../public/static/css/app.css`; frontend source was not changed in this diagnosis. [Pending repair](workCurrent.md).

## Missing-database startup — 2026-11-11

The latest pasted output fails during `serve` system checks with SQLite `unable to open database file`. Environment/path metadata confirms the configured normal SQLite path is `backend/data/clinic.db`; neither it nor its parent directory currently exists. The normal root-level `clinic.db`/`db.sqlite3` alternatives are also absent. No database contents were read. This is a later filesystem condition than the earlier successful read-only schema inventory; its cause is unknown.

`serve` now rejects a missing normal SQLite file before native checks/Django system checks can open or implicitly create it, with a remedy naming `DATABASE_NAME`, existing-storage recovery and explicitly authorized fresh setup. In-memory/URI paths retain their existing behavior. Running the real command with the current missing path returns the intended concise CommandError; `data/` remains absent and `git diff --check` passes. No migrations, restoration, initialization, seeding, tests or clinic data changes. Selection/recovery of the intended database remains [pending](workCurrent.md).

## Authorized fresh database — 2026-11-11

The user confirmed fresh setup after the missing-database finding. Rechecked that the intended SQLite file was still absent, then ran the existing `bootstrap` command under `clinicon` without `--clean`, `--with-demo-data` or `--with-frontend`. It generated 14 ignored local application migration files, applied the schema, and seeded default accounts/catalogs/settings/tasks. This was requested application setup, not database initialization for a diagnostic probe. No previous database was overwritten or restored.

Initial passwords were generated/supplied in memory; seed output was captured in memory and credentials were never printed to tool/chat output or diagnostic logs. The private handoff is ignored `data/initial-accounts.txt`, mode 0600. Default accounts require password change on first login. The SQLite file and generated migrations remain ignored as required; signing keys/environment assignments were preserved.

All managed model tables/columns are present, SQLite `integrity_check` returns `ok`, and patient count is zero. A real `./start.sh --no-browser` launch using the configured fresh database passed Vite HTML, CSRF bootstrap, admin login (200), authenticated `me` (200), required password-change flag, logout (200), health (200), graceful shutdown and released ports. No browser interaction, broader clinical suite or PostgreSQL/native Windows verification was performed. The earlier missing-file/schema blockers are resolved by this fresh setup; they were not upgrades of the old database. [Current scope](workCurrent.md).
