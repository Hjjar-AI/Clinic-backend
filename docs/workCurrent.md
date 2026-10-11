# Current work

Requested PDF/browser expansion complete (2026-10-11): **174 backend tests**, **110 Node tests**, **77 Vue DOM/import checks**, **60 Chromium cases**, and **6 PDF appearance checks** passed. Real workflows run across desktop/tablet/mobile with isolated synthetic data. [PDF review, workflow matrix, fixes and limits](pdf-workflow-verification.md). No production build, clinic-data, migration or dependency-version changes.

Automated suite implemented and verified on the installed environment: [commands, coverage and limits](testing.md), [completed results](doneCurrent.md). Test tooling and Vue/Vite test transforms explicitly authorized on 2026-10-11; no production build or clinic-data changes for tests. Earlier pending UI/operational checks are superseded only for the scenarios listed in that guide.

Updated: 2026-10-11. Patient schema/workflow expansion complete; see [schema/retention](patient-record-schema.md) and [verification](patient-record-verification.md). Second backend model/logic review fixes complete; see [second-pass findings and verification](backend-second-pass.md). CheckConstraint startup compatibility fixed; see [completed work](doneCurrent.md). No active implementation.

- Pending: pinned Django/DRF on a supported Python interpreter; PostgreSQL concurrency and browser workflows outside the explicit test matrix. The temporary pinned stack on Python 3.14 encounters Django template-context errors; the installed Django 6 suite passes.
- User environment: Python 3.14/Django 6.1.2 differs from pinned requirements. Authorized `bootstrap --with-demo-data` completed (initial migrations, default seed, 10 demo patients); `check --database default` passed. Selected API/browser regressions now pass in the automated suite; see its explicit verification limits.
- Unverified, not confirmed defects: browser workflows outside the listed matrix and PostgreSQL/concurrent writers. Requested Arabic PDF/print checks are complete; see the verification record.
- Fresh schema initialized by the authorized bootstrap on 2026-10-11. User authorized related management commands for this troubleshooting; destructive cleanup, production builds/packaging and application version changes remain outside this scope. Tests and their Vue/Vite transforms were separately authorized.
- Preserve signed history/documents, server signing, shared scope, versioned writes, idempotent replay, after-commit invalidation. Archive retains history; pseudonymization retains signed identities.
- Recovery: full ZIP includes media/replaces managed inventory; catalog restore merges. Imports/restores require matching preview/scope.
- Resume: [implementation record](backend-fixes-implementation.md), [original review](backend-models-logic-review.md), [completed plan](backend-fixes-work-plan.md), and [workflow checklist](critical-workflow-checklist.md). UI coordination: [frontend current work](../../frontend/docs/workCurrent.md).
