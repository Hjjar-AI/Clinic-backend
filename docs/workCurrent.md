# Remaining backend work

| Work | Remaining action |
| --- | --- |
| Existing database schema | Apply `CacheGeneration`, `RecoveryOperation` and task/appointment reminder-generation fields only under explicit schema/migration authorization. Project schema was not changed. |
| Integration limits | Remaining consumer-specific spreadsheet/PDF cases and production-like coordinated release checks. Real permission-sensitive replay, restored-admin receipts and failure reconciliation now have passing suites. [Evidence](doneCurrent.md). |
| Deployment profiles | MySQL/MariaDB and Redis/Memcached remain unverified. Python 3.12 with pinned Django/DRF and disposable PostgreSQL 18 passed; that does not verify the deployed profile. |
| Concurrency/recovery | Extend simultaneous-writer coverage to billing/idempotency/cache and real worker termination. Appointment overlap, patient/task stale writers, PostgreSQL operation gates, reconciliation and receipt expiry are exercised. Other DB profiles require common POSIX `OPERATION_LOCK_DIR`. [Operations](operations.md). |
| Coordinated release | Frontend open findings, final full browser/component rerun, other engines/LTR/accessibility/physical printing and production bundles remain open. [Frontend current](../../frontend/docs/workCurrent.md), [release checks](verification.md#release-checks). |

R1–R29 source corrections are complete. Earlier authorized bootstrap initialized schema/defaults and ten demo patients; do not repeat it for verification. Test suites were explicitly authorized; schema/build/version work remains separate; [rules](../AGENTS.md).
