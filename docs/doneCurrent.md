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
