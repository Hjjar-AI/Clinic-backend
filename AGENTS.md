# Backend agent guide

- Before work, read `workCurrent.md`, `doneCurrent.md`, relevant work/plan files, and additional applicable `AGENTS.md`; use `README.md` for setup. For cross-project changes, also read the frontend handoff files.
- Do not inspect, review, edit, or create migration files unless explicitly requested. The user normally starts with a fresh database. `bootstrap` and `runserver_auto` perform migration work; do not use them without authorization.
- Do not inspect or review test-suite files unless explicitly requested to work on tests.
- Do not run Gradle, builds, compilation, or packaging unless explicitly allowed. Simple development/debugging scripts and tools are allowed; do not treat their availability as permission to alter the project database.
- Do not change dependency or application versions unless explicitly requested.
- When the five-hour usage allowance reaches 20% remaining, finish the current step and stop; do not claim usage visibility if unavailable.
- Preserve user changes. Keep these handoffs compact, update completed work and outstanding items, and distinguish verified behavior from unverified assumptions.
- Django/DRF code lives in `apps/`, shared infrastructure in `core/`, settings in `config/`. Local API: port `5019`, prefix `/api/v1/`; sibling frontend: port `5173`.
- Keep business validation and lifecycle transitions in services; preserve endpoint permissions and shared patient/care-team/historical-author scope.
- Preserve immutable signed visit revisions and issued documents, server-authorized signing, expected-version checks, replayable idempotency, and cache invalidation after commit.
- Archive preserves clinical history; pseudonymization retains signed identity snapshots. Keep full authenticated ZIP recovery distinct from catalog-only merge, and preserve preview/confirmation binding for imports and restore.
- Never commit secrets or runtime data (`.env`, `data/`, `media/`, `backups/`, `staticfiles/`). Do not log patient records or credentials during debugging.
