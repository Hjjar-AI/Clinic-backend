# Verification

[Results/limits](doneCurrent.md) · [Remaining](workCurrent.md) · [Frontend](../../frontend/docs/verification.md). Explicit suite authorization is required; builds/schema work have separate scope. Suites/probes use synthetic storage; the explicitly requested fresh local setup is a separate operation. Record the actual interpreter/dependency profile and do not carry historical passes forward to new pins.

## Isolated commands

```bash
python -B tests/run.py
python -B tests/run_postgres.py
python -B tests/run_postgres.py tests.test_billing_concurrency tests.test_worker_termination
```

SQLite runner skips clinic `.env`/migration modules and uses memory DB/temp storage. PostgreSQL runner owns a disposable private Unix-socket cluster, disables TCP and rejects unowned DB/settings; requires installed binaries/psycopg. Neither touches clinic storage or migration files.

Suites cover auth/CSRF/grants/scope, strict versions/lifecycle, patient registers/history/merge, signing/exact documents, billing/tasks/reminders, import/export and authenticated recovery. PostgreSQL adds actual overlap/stale-writer/payment/receipt/cache races; waiters must reach a DB lock before release. Cache checks use local memory and DB generations, including publication across commit.

Five subprocess SIGKILL checkpoints: invoice before/after commit; full restore after media/before DB commit/after commit. Assert rollback versus exact/bounded replay, lock release, interrupted-key blocking and safety-copy DB/media repair before reconciliation. POSIX only; not every failure/topology.

Ignored `tests/tools/` retains historical helpers/logs/runtimes, including `prepare_runtime.py`, `standalone_model_probe.py` and `runtime/python/bin/python3.12`. That Python 3.12.16 environment belongs to the earlier dependency profile; do not assume it matches current requirements. Select/record the intended interpreter explicitly. Retained tools supplement, not replace, authorized suites.

Launcher-only: `python -B -m unittest tests.test_launcher`; related auth/CSRF: `python -B manage.py test tests.test_launcher tests.test_api --settings=config.settings.testing --noinput`. Ignored `tests/tools/launcher_process_probe.py` exercises real Linux sockets/process groups with controlled servers; it never starts clinic services or reads clinic `.env`/data. Native Windows requires its own check.

`start.sh check` and `manage.py check_runtime --render-pdf` are database-free prerequisite checks. A listening socket or `SELECT 1` health response does not prove current tables/columns or successful login. Test authenticated behavior only within the authorized storage/account scope.

## PDF inspection

```bash
# Frontend: retain actual browser downloads
CLINIC_PDF_ARTIFACT_DIR=/tmp/clinic-browser-pdfs pnpm test:e2e
# Backend: requires PyMuPDF/fontTools; no DB access
python -B tests/pdf_appearance.py --output /tmp/clinic-pdf-review --downloads /tmp/clinic-browser-pdfs
```

Checks: dimensions/pagination/bounds, Arabic glyphs/both embedded fonts, complete rows/decimals/instructions, repeated identity/headers, A6/custom offsets, overflow rejection and 50 mm calibration ruler. No downloads means explicit artifact-check skip. Saved-byte/history/handout invariants have API/browser cases; native dialogs/physical printing remain manual.

## Release checks

Durable procedure, not an active deployment task. Use authorized synthetic topology; record runtime/browser/DB/timezone/results. Exercise login/revocation/cross-role denial; unknown/year-only patient/register/team/merge; appointment overlap/version/lifecycle; draft/sign/amend/re-sign/lock; signed Arabic documents/exact bytes; fractional billing/paid reconciliation; scoped formula-safe exports; authenticated backup/preview/restore/relogin/DB+media reconciliation; stale/disconnected retries without duplicates and reminder occurrence lifecycle. Verify demo off, intended grants, backup space and no unexplained API failures. Require passing critical workflows or recorded owner-approved exceptions.
