# Backend agent guide

- Before editing, read [current](docs/workCurrent.md), [completed](docs/doneCurrent.md), [contracts](docs/contracts.md) and applicable instructions; verify source. [Setup](docs/setup.md); cross-project changes require frontend handoffs.
- Root Markdown: README/AGENTS only. Remaining work belongs in current, evidence/limits in completed, durable facts in topic guides. Merge duplicates and repair links.
- Finish authorized scope, reuse authorization, preserve unrelated edits. Reviews need source/impact/correction; fixes need implementation/permitted verification. Reopen completed findings only with new evidence.
- Explicit permission required for migration or test-suite inspection/work; Gradle/builds/compilation/packaging; version/dependency/lockfile changes. Production study/exam code is not a test suite. `bootstrap`/`runserver_auto` migrate; probes never authorize clinic schema/data changes.
- If a visible five-hour allowance reaches 20% remaining, finish the current step and stop; never invent visibility.
- Django/DRF: `apps/`, shared `core/`, `config/`; API **5019** `/api/v1/`, frontend **5173**. Model fixes may target fresh DBs without migrations; trace services/serializers/endpoints/import/export/recovery/UI.
- Services own validation/lifecycle. Preserve action grants plus patient/team/historical-author scope, server authority, patient-before-visit locks, opening versions/strict `If-Match`, sessions/CSRF/envelopes and stable uncertain-retry keys.
- Preserve immutable signed revisions/exact issued bytes, authorized signing, durable idempotency and commit-visible cache invalidation. Archive retains history; pseudonymization retains signed identities. Bind previews/consent; distinguish full authenticated recovery from catalog merge.
- Preserve unknown/year-only birth, permanent file numbers, unchanged duplicate IDs/nonblocking review, optional explicit merge, effective dated teams, clinical unknowns, ownership, correction reasons and parent versions. [Contracts](docs/contracts.md) govern behavior; [verification](docs/verification.md) governs checks.
- Use focused production/reference checks and isolated probes; exclude migrations/suites/generated assets/dependencies/runtime data from broad searches. Source/SQLite cannot prove browser/PDF/PostgreSQL behavior; report limits.
- Never commit secrets/runtime data or log patient values/credentials. Never initialize/seed/restore clinic storage merely for verification.
