# Verification

[Results/limits](doneCurrent.md) · [Remaining](workCurrent.md) · [Frontend](../../frontend/docs/verification.md). Explicit test authorization required; builds/schema work separate. Synthetic storage only.

## Isolated commands

```bash
python -B tests/run.py
python -B tests/run_postgres.py
python -B tests/run_postgres.py tests.test_billing_concurrency tests.test_worker_termination
```

SQLite runner skips clinic `.env`/migration modules and uses memory DB/temp storage. PostgreSQL runner owns a disposable private Unix-socket cluster, disables TCP and rejects unowned DB/settings; requires installed binaries/psycopg. Neither touches clinic storage or migration files.

Suites cover auth/CSRF/grants/scope, strict versions/lifecycle, patient registers/history/merge, signing/exact documents, billing/tasks/reminders, import/export and authenticated recovery. PostgreSQL adds actual overlap/stale-writer/payment/receipt/cache races; waiters must reach a DB lock before release. Cache checks use local memory and DB generations, including publication across commit.

Five subprocess SIGKILL checkpoints: invoice before/after commit; full restore after media/before DB commit/after commit. Assert rollback versus exact/bounded replay, lock release, interrupted-key blocking and safety-copy DB/media repair before reconciliation. POSIX only; not every failure/topology.

Ignored `tests/tools/` stores helpers/logs/runtimes. `prepare_runtime.py` restores checksum-verified Linux x64 Python 3.12.16/existing pins/PDF tools; `standalone_model_probe.py` supplements suites. Local interpreter: `tests/tools/runtime/python/bin/python3.12`.

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
