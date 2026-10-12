# Verification

Explicit test authorization is required to inspect/work/run suites; builds/schema work are separate. Use synthetic isolated storage; never substitute a clinic database. [Recorded evidence](doneCurrent.md), [remaining checks](workCurrent.md), [frontend verification](../../frontend/docs/verification.md).

## Isolated commands

```bash
python -B tests/run.py
python -B tests/run_postgres.py  # owned temporary cluster; needs PostgreSQL binaries + psycopg
python -B manage.py test tests --settings=config.settings.testing --noinput
python -B -m coverage run --source=apps,core --omit='*/migrations/*' tests/run.py
python -B -m coverage report --omit='*/migrations/*'
```

Runner fixes isolated settings/refuses non-memory DB; testing skips clinic .env/migration modules, creates model schema in memory and uses synthetic secrets/hashers/local cache/temp media/backups/static. Optional coverage tooling does not change runtime requirements. Focused modules may be supplied to manage.py test. Never substitute a development clinic database.

| Existing coverage / ownership | Interpretation |
| --- | --- |
| Core/API/accounts | Strict versions/lifecycle/constraints/normalization, actual session+CSRF/lockout/revocation/grants, envelopes/pagination/idempotency/failure reuse, real renderer empty-response bytes and throttles. |
| Patient HTTP | All register kinds/parent versions/reasons/history/provenance/verification, actor/scope/clinical permission, team revocation, document MIME/checksum/archive/download, duplicate/merge digest/versions/signed retention. |
| Visit/document services | Draft/sign/amend/lock, immutable revisions/exact issuance, preview stale/actor binding and renderer failure. |
| Operations/tasks/notification HTTP | Scheduling intervals/rebooking/reminders, decimal billing, task assignment/lifecycle/reorder/replay/null dates/refresh and scoped notification actions. |
| Catalog/import/recovery/report | Identity/version/retirement/scales, CSV/XLSX/formula protection/preview/scope/transactional replacement, full signed ZIP/media/time precision/relogin, scoped periods/revenue/audit/cache rollback. |
| Browser fixture | `tests/browser_server.py` owns only temporary localhost 5018 and synthetic accounts/storage; used by frontend 5174 tests. Cleanup/fixture quotas do not establish production capacity. |

SQLite verifies sequential behavior/rollback. `run_postgres.py` creates an unprivileged private Unix-socket cluster with TCP disabled, rejects replacement settings and removes its storage; no existing database or migration files are accessed. Its three simultaneous-writer cases exercise appointment overlap and patient/task opening-version races. SQLite explicitly skips them. Transaction-boundary tests exercise real receipt/mutation rollback, permission changes, cache rollback, receipt expiry, interrupted recovery reconciliation and streaming cleanup. Recovery receipt tests exercise restored-admin HTTP replay and pre-media failure. Anonymous denial and explicit-grant matrices cover 14 endpoint families. These checks do not certify arbitrary worker termination or every DB/cache profile.

## PDF inspection

```bash
# From frontend, retain browser PDFs:
CLINIC_PDF_ARTIFACT_DIR=/tmp/clinic-browser-pdfs pnpm test:e2e
# From backend, optional isolated inspection tooling:
python -B tests/pdf_appearance.py --output /tmp/clinic-pdf-review --downloads /tmp/clinic-browser-pdfs
```

Inspector prohibits database access, requires optional PyMuPDF/fontTools; without downloads it explicitly skips browser-artifact check. Checks cover the five legacy A4 templates plus A6 blank/custom preprinted prescriptions: physical dimensions/multipage/nonblank/page bounds/Arabic glyphs/embedded fonts/text mapping/row retention/repeated headers/complete decimals/referral closing. Chromium Type3 font resources are valid inspected embedding. Paper regressions cover complete medication/instruction tails, per-sheet summary/body pairing, measured offsets, stationery exclusion, field overflow and repeat issuance. Use `--kinds prescription,preprinted` to inspect a paper-only browser artifact directory. Manual first/second/final PNG review checked joining/readability/pagination of exercised samples; not every input/printer.

Renderer resolves bundled Cairo/Inter together; font config/bidi isolation/numeric cells/flowing visit containers were corrected. Existing issued bytes remain unchanged. Other recorded corrections: full backup timestamp microseconds, visit unknowns/clean saves, native button events/input step, PNG signature output and invoice currency. Latest inspection dates/runtimes stay only in completed record; temporary artifacts are not durable evidence.

## Release checks

Record build/tester/timezone/browser/DB profile/results; use clean and authorized production-like synthetic environments. Critical workflow:

1. Login/identity/grants, forced password/session expiry/revocation and cross-role API denial.
2. Unknown/year-only patient/search/duplicate warning, register corrections/team scope/protected files/history and optional preview-bound merge.
3. Appointment availability/overlap/version/lifecycle/reschedule, active-clinician eligibility and scoped future shortcut.
4. Draft → sign → reject direct edits → reasoned amendment → re-sign → lock; approved-risk visibility retained during amendment.
5. Signed prescription/referral, actual current signature/version/Arabic PDF/exact issued bytes and working-export labels.
6. Fractional invoice issue/pay/rejected material edits; labelled currency reconciliation agrees with paid-only source.
7. Filtered scoped CSV/XLSX/PDF/Word, text-cell protections and generation metadata.
8. Authentic full backup/digest/member inventory; preview/consent/safety restore/relogin/exact records/media, catalog-only separation and interrupted-receipt reconciliation.
9. Stale writes, uncertain disconnect/retry without duplicates, empty archive/replay bodies through proxy, reminder stop/reopen occurrences and final frontend matrix.

Verify demo disabled, intended roles, sufficient backup space and no unexplained API failures. Hidden UI is not API authorization evidence. Release requires passing critical steps or recorded owner-approved exceptions; source completion alone is insufficient. Production bundles, MySQL/MariaDB, Redis/Memcached, arbitrary worker failures, other engines/accessibility and physical printing remain open. Supported pinned runtime and disposable PostgreSQL results are recorded in completed.
