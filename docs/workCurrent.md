# Remaining backend work

| Area / files | Remaining action |
| --- | --- |
| `requirements.txt`, supported Python runtime | Verify pinned Django 5.0.6 / DRF 3.15.1 on Python 3.10–3.12. Python 3.14 probe hit two Django template-context errors; installed Django 6 results do not establish pinned compatibility. |
| Transactional services, `core/access.py`, `core/cache_utils.py`, billing constraints | Verify PostgreSQL concurrent writers, lock order, scheduling/idempotency/cache races and decimal expressions; SQLite sequential tests do not establish these. |
| Coordinated frontend | N6 section highlighting / N7 background loading and broader browser matrix remain open; [frontend current](../../frontend/docs/workCurrent.md). Repeat full browser/component suites after final calendar correction. |
| Deployment/release | Production bundle, other browser engines/LTR, exhaustive accessibility/visual coverage and physical printers remain unverified. [Release checklist](testing/release-checklist.md). |

No backend implementation task is active. Clinical/history/recovery/patient changes and requested tests are implemented; [contracts](contracts/implementation.md), [latest verification](doneCurrent.md). Authorized bootstrap initialized the fresh schema/defaults and ten demo patients; do not repeat it merely for verification. Test tooling is authorized; migration files, production builds, destructive cleanup and version changes need explicit requests. [Rules](../AGENTS.md).
