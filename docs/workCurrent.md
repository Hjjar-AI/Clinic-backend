# Remaining backend work

| Area / files | Remaining action |
| --- | --- |
| New schema / existing database | Apply `CacheGeneration`, `RecoveryOperation` and task/appointment reminder-generation fields only under explicit schema/migration authorization. No project schema was changed. |
| Corrected R1–R29 integration | Verify real HTTP replay permissions, restored-admin receipts/relogin, supported pinned runtime, spreadsheet consumers/working PDFs and frontend rendering. 43 synthetic source/SQLite checks are recorded in [completed](doneCurrent.md), not complete application verification. |
| Recovery/catalog operation gate | Validate PostgreSQL advisory locking and worker termination; for MySQL/MariaDB use configured common POSIX `OPERATION_LOCK_DIR`. All workers/jobs participate; quiesce external writers. Rehearse interrupted recovery reconciliation and 30-day receipt cleanup in authorized disposable deployment. |
| `requirements.txt`, supported Python runtime | Verify pinned Django 5.0.6 / DRF 3.15.1 on Python 3.10–3.12. Python 3.14 probe hit two Django template-context errors; installed Django 6 results do not establish pinned compatibility. |
| DB/cache deployment profiles | Actual PostgreSQL/MySQL/MariaDB and Redis/Memcached connection/schema/runtime checks remain unverified; install matching profile and configure an authorized disposable environment. |
| Transactional services, `core/access.py`, `core/cache_utils.py`, billing constraints | Verify PostgreSQL concurrent writers, lock order, scheduling/idempotency/cache races and decimal expressions; SQLite sequential tests do not establish these. |
| Coordinated frontend | N6 section highlighting / N7 background loading and broader browser matrix remain open; [frontend current](../../frontend/docs/workCurrent.md). Repeat full browser/component suites after final calendar correction. |
| Deployment/release | Production bundle, other browser engines/LTR, exhaustive accessibility/visual coverage and physical printers remain unverified. [Release checklist](testing/release-checklist.md). |

R1–R29 source corrections are complete; no pending model-review implementation item remains. Clinical/history/recovery/patient changes and earlier requested tests are implemented; [contracts](contracts/implementation.md), [latest verification](doneCurrent.md). Authorized bootstrap initialized the fresh schema/defaults and ten demo patients; do not repeat it merely for verification. Test tooling is authorized; migration files, production builds, destructive cleanup and version changes need explicit requests. [Rules](../AGENTS.md).
