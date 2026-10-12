# Remaining backend work

| Work | Remaining action |
| --- | --- |
| Existing database schema | Apply `CacheGeneration`, `RecoveryOperation` and task/appointment reminder-generation fields only under explicit schema/migration authorization. Project schema was not changed. |
| R1–R29 integration | Verify real HTTP replay after permission removal, restored-admin receipts/relogin, spreadsheet consumers, working PDFs and coordinated UI. [Contracts](contracts.md), [completed probes](doneCurrent.md). |
| Deployment runtime | Verify pinned Django 5.0.6/DRF 3.15.1 on Python 3.10–3.12; actual PostgreSQL/MySQL/MariaDB and Redis/Memcached behavior remains unverified. Python 3.14/pinned-runtime failures do not establish supported compatibility. |
| Concurrency/recovery | Verify scheduling/idempotency/cache/billing lock behavior, PostgreSQL advisory gates and worker termination. Other DB profiles require common POSIX `OPERATION_LOCK_DIR`; rehearse interrupted recovery reconciliation and receipt expiry on authorized disposable storage. [Operations](operations.md). |
| Coordinated release | Frontend open findings, final full browser/component rerun, other engines/LTR/accessibility/physical printing and production bundles remain open. [Frontend current](../../frontend/docs/workCurrent.md), [release checks](verification.md#release-checks). |

R1–R29 source corrections are complete. Earlier authorized bootstrap initialized schema/defaults and ten demo patients; do not repeat it for verification. No new schema/test/build/version action is authorized by this record; [rules](../AGENTS.md).
