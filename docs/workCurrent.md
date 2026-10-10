# Current work

Updated: 2026-10-11. Patient schema/workflow expansion complete; see [schema/retention](patient-record-schema.md) and [verification](patient-record-verification.md). Second backend model/logic review fixes complete; see [second-pass findings and verification](backend-second-pass.md). CheckConstraint startup compatibility fixed; see [completed work](doneCurrent.md). No active implementation.

- Pending: API regression under pinned Django/DRF (temporary dependency download unavailable); browser care-team/document/conflict flows.
- User environment: Python 3.14/Django 6.1.2 differs from pinned requirements. Authorized `bootstrap --with-demo-data` completed (initial migrations, default seed, 10 demo patients); `check --database default` passed. Broader API/browser compatibility remains unverified.
- Unverified, not confirmed defects: PDF/Arabic rendering, frontend browser workflows, PostgreSQL/concurrent writers.
- Fresh schema initialized by the authorized bootstrap on 2026-10-11. User authorized related management commands for this troubleshooting; destructive cleanup, test-suite access, builds/compilation/packaging, and version changes remain outside this scope.
- Preserve signed history/documents, server signing, shared scope, versioned writes, idempotent replay, after-commit invalidation. Archive retains history; pseudonymization retains signed identities.
- Recovery: full ZIP includes media/replaces managed inventory; catalog restore merges. Imports/restores require matching preview/scope.
- Resume: [implementation record](backend-fixes-implementation.md), [original review](backend-models-logic-review.md), [completed plan](backend-fixes-work-plan.md), and [workflow checklist](critical-workflow-checklist.md). UI coordination: [frontend current work](../../frontend/docs/workCurrent.md).
