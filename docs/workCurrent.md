# Current work

Updated: 2026-10-08. Backend review fixes/documentation complete; no active implementation.

- Unverified, not confirmed defects: PDF/Arabic rendering, frontend browser workflows, PostgreSQL/concurrent writers.
- Fresh schema initialization remains separate; no migrations generated/applied. Migrations, test-suite access, builds/compilation/packaging, version changes require explicit authorization.
- Preserve signed history/documents, server signing, shared scope, versioned writes, idempotent replay, after-commit invalidation. Archive retains history; pseudonymization retains signed identities.
- Recovery: full ZIP includes media/replaces managed inventory; catalog restore merges. Imports/restores require matching preview/scope.
- Resume: [implementation record](backend-fixes-implementation.md), [original review](backend-models-logic-review.md), [completed plan](backend-fixes-work-plan.md), and [workflow checklist](critical-workflow-checklist.md). UI coordination: [frontend current work](../../frontend/docs/workCurrent.md).
