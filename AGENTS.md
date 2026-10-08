# Backend agent guide

## Workflow

- Before editing, read [current](docs/workCurrent.md)/[completed](docs/doneCurrent.md) work, relevant plans, and applicable `AGENTS.md`; use [README.md](README.md) for setup. Read frontend instructions/handoffs for cross-project changes.
- Keep `README.md`/`AGENTS.md` at root; other documentation, reviews, plans, and handoffs belong in `docs/`. Update local/cross-project references after moves; keep guides compact and link detailed records instead of duplicating them.
- Preserve user changes and completed work. Reviews must identify findings, locations, impact, and corrections; fix requests require authorized implementation and verification, not suggestions alone.
- Keep handoffs current: completions, outstanding work, verification, limitations. Separate confirmed defects from unverified behavior; do not reopen completed findings without evidence.

## Limits

- Unless explicitly requested, do not inspect/review/edit/create migration files or inspect/review test-suite files. The user normally starts with a fresh database. `bootstrap`/`runserver_auto` perform migration work and require authorization.
- No Gradle, builds, compilation, or packaging without explicit permission. Simple development/debugging scripts/tools are allowed, but do not authorize project database changes. Preserve dependency/application versions, pinned requirements, and lockfiles unless version changes are explicitly requested.
- At 20% remaining five-hour usage allowance, finish the current step and stop. Do not claim usage visibility when unavailable.

## Models and contracts

- Django/DRF: `apps/`; shared infrastructure: `core/`; settings: `config/`. API: port `5019`, `/api/v1/`; frontend: `5173`.
- Requested model/logic changes may improve the fresh-database design without generating migrations. Trace services, serializers, endpoints, imports/exports, recovery, and frontend consumers; keep contracts consistent.
- Put business validation/lifecycle transitions in services. Preserve endpoint permissions and shared patient/care-team/historical-author scope; UI permissions never replace backend authorization.
- Preserve immutable signed visit revisions/issued documents, server-authorized signing, expected-version checks, replayable idempotency, and after-commit cache invalidation.
- Preserve session/CSRF handling, response envelopes, frontend opening versions/`If-Match`, and stable operation keys across retries after uncertain responses.
- Archive retains clinical history; pseudonymization retains signed identity snapshots. Keep full authenticated ZIP recovery distinct from catalog-only merge; imports/restores require bound previews/confirmations.
- Patient design: [schema/API/retention](docs/patient-record-schema.md). Preserve year-only/unknown birth, permanent file numbers, unchanged duplicate IDs/dismissible review, optional preview-bound merge, dated team memberships, clinical unknowns, longitudinal/encounter/signed fact ownership, correction reasons and parent versions.
- Consult the [implementation record](docs/backend-fixes-implementation.md) and [workflow checklist](docs/critical-workflow-checklist.md) when changing these contracts.

## Verification and privacy

- Use focused source/reference checks and isolated development probes within these limits. Exclude migrations, test suites, generated output, dependencies, and runtime data from broad searches; do not initialize/seed/restore project data merely to verify code.
- Report checks and remaining uncertainty. Source parsing/SQLite probes do not verify browser/PDF rendering or PostgreSQL concurrency.
- Never commit secrets/runtime data (`.env`, `data/`, `media/`, `backups/`, `staticfiles/`) or log patient records/credentials while debugging.
