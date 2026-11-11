# Backend agent guide

## Start and scope

- Read [remaining work](docs/workCurrent.md), [evidence](docs/doneCurrent.md), [contracts](docs/contracts.md) and applicable topic guides before edits. Check git status and source; preserve unrelated work. [Setup](docs/setup.md) · [Operations](docs/operations.md).
- Finish authorized scope and reuse existing authorization within that scope. Explicit permission is required for migration or test-suite inspection/work, builds/compilation/packaging (including Gradle), and version/dependency/lockfile changes. Production study/exam code is not a test suite. Documentation cleanup does not authorize any of these operations.
- `bootstrap`/`runserver_auto` migrate; bootstrap also seeds. Never initialize, seed or restore clinic storage merely for verification. A runtime probe is not permission for schema/data changes; confirm the intended settings/database before any authorized storage operation.
- If a visible five-hour allowance reaches 20% remaining, finish the current step and stop; never invent visibility. Reopen completed findings only with new evidence.

## Implementation boundaries

- Django/DRF: feature `apps/`, shared `core/`, configuration `config/`; API **5019** `/api/v1/`, frontend **5173**. Services own validation/lifecycle. Model fixes may target fresh DBs without migrations; trace services, serializers, endpoints, import/export, recovery and UI. Cross-project changes need a frontend handoff.
- Preserve effective action grants plus patient/team/historical-author scope, server authority, patient-before-visit locks, opening versions/strict `If-Match`, sessions/CSRF/envelopes and stable uncertain-retry keys.
- Preserve immutable signed revisions/exact issued bytes, authorized signing, durable idempotency and commit-visible cache invalidation. Archive retains history; pseudonymization retains signed identities. Bind previews/consent; full authenticated recovery differs from catalog merge.
- Preserve unknown/year-only birth, permanent file numbers, unchanged duplicate IDs/nonblocking review, optional explicit merge, effective-dated teams, clinical unknowns, ownership, correction reasons and parent versions. [Contracts](docs/contracts.md) own detailed behavior.

## Verification and privacy

- Use focused source/reference checks and isolated probes; exclude migrations, suites, dependencies, generated assets and runtime storage from broad searches. Never commit secrets/runtime data or log patient values/credentials.
- Follow [verification](docs/verification.md). Record date, interpreter/dependency profile, storage scope, result and limits. Historical suite passes do not certify newer pins. Source/SQLite checks cannot prove browser/PDF/PostgreSQL behavior; process/TCP readiness cannot prove schema or login readiness.
- Reviews identify source, impact and correction; fixes include implementation and permitted verification. Do not repeat successful checks without a new change, failure or unresolved concern.

## Documentation ownership

- Root Markdown: README/AGENTS only. `workCurrent` owns actionable remaining work; `doneCurrent` owns dated evidence/limits; topic guides own durable setup, operations and contracts. READMEs are entry points.
- Remove resolved tasks and superseded troubleshooting narratives. Keep unique decisions, meaningful counts and their historical scope; avoid repetitive file/line inventories and duplicate result tables. Repair local links/anchors after moves. Documentation-only edits need reference/diff checks, not builds, suites or storage operations.
