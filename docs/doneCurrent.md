# Verification evidence

Updated **2026-11-11**. [Remaining work](workCurrent.md) · [Contracts](contracts.md) · [Check procedures](verification.md). Results belong to the dated runtime/storage profile below; they are not whole-app certification.

## Python 3.14 compatibility and launch (2026-11-11)

Current local profile: Linux, Python **3.14.4**, Django **6.1.2**, DRF **3.18.3**, Node **24.21.0**. Shared requirements match the installed versions; missing Portalocker **4.3.0** and Waitress **3.0.2** were installed with authorization. Applicable direct pins match metadata; `pip check` passed. Python target is now 3.12–3.14; broader suites were not rerun after this upgrade.

| Check | Evidence |
| --- | --- |
| Configuration | Launcher/CSRF settings added; previous local assignments/signing keys preserved. `.env`/`.env.example` contain the same comment drawing. Values were not logged. |
| Native runtime | Locks, WSGI, MIME, both fonts, timezone and in-memory Arabic/Latin PDF passed through `start.sh check`. |
| Isolated launch | Two actual startup/HTTP/shutdown cycles: Vite HTML, API proxy/config, CSRF cookie, credentialed CORS, health and unauthenticated patient denial. In-memory SQLite/temp locks; no schema creation. Both ports released; immediate restart passed. |
| Launcher correction | POSIX SO_REUSEADDR avoids TIME_WAIT false occupancy; occupied-listener detection still rejects a live server. Socket permission failures have their own remedy. Windows binding unchanged. |
| Focused compatibility | All model SELECT queries compiled and synthetic patient JSON round-tripped with SQL execution blocked; billing half-up arithmetic, production CSV/XLSX/formula rejection and python-docx Arabic/Latin round trip passed. |

No current-profile clinical regression suite, browser interaction, PostgreSQL execution or native Windows verification. [Frontend evidence](../../frontend/docs/doneCurrent.md) owns the successful build and editor-task checks.

## Authorized fresh database (2026-11-11)

The old database lacked two model tables/twelve columns; a later launch found the configured file/directory absent. These were resolved by the user's authorized **fresh setup**, not an upgrade or restoration of old data. `serve` now rejects missing normal SQLite files before opening them; in-memory/URI handling remains unchanged.

After confirming the target was absent, `bootstrap` generated **14 ignored local migration files**, applied the schema and seeded default accounts/catalogs/settings/tasks. No `--clean`, demo patients or frontend build. All managed tables/columns were present, SQLite integrity was `ok`, patient count zero. Real launch using this database passed admin login, authenticated `me`, enforced first-login rotation, logout, health, Vite HTML and clean shutdown.

Initial account handoff is private ignored `data/initial-accounts.txt` (0600). Seed output was captured in memory; credentials were not printed to chat/tool output or diagnostic logs. Storage and local migrations remain ignored. Existing storage must never be bootstrapped merely to reproduce these checks.

## Historical regression profile (2026-11-07)

Model review 1–21/R1–R29 and requested billing/idempotency/cache/process-failure checks completed on Python **3.12.16**, Django **5.0.6**, DRF **3.15.1**. Synthetic isolated storage/local-memory cache; no clinic storage or dependency changes during those checks.

| Check | Result and scope |
| --- | --- |
| PostgreSQL 18 | **283 passed**, owned disposable cluster. |
| SQLite | **265 passed, 18 PostgreSQL-only skips**. |
| Concurrency/failure | 15 added cases: billing/version/payment/receipt/cache races and five real SIGKILL checkpoints; lock release, rollback/replay and interrupted-restore DB/media reconciliation covered. |
| PDF | **14 passed**, including 23 browser PDFs across desktop/tablet/mobile and six document kinds. |
| Launcher/API | **54 focused tests**, five real Linux socket/process probes; shutdown/failure/partial-start/timeout/occupied-port and CSRF/custom-origin rejection covered. Windows routing used doubles. |

These passes do not certify the newer pins, shared-cache servers, external writers/storage, host/power loss, every failure point, Windows/macOS, other browser engines, exhaustive accessibility or physical printing. No separate type-check certification. Helpers/logs/artifacts in ignored `tests/tools/` may outlive their matching runtime; temporary logs may disappear. Versioned application migrations were removed by earlier request; fresh local bootstrap later regenerated ignored files. Full backups require format 3/current schema; old storage compatibility is absent.

## Documentation review (2026-11-11)

Reviewed all project Markdown across backend/frontend; strengthened both agent guides, consolidated historical evidence, removed resolved work entries and separated frontend setup from the entry README. Kept contracts/UI invariants and meaningful verification limits. The compact frontend inventory retains all 21 moves and 60 deleted paths; repetitive “Keep” rows/stale line counts were retired. Source verification corrected health monitoring guidance: degraded database status may still use HTTP 200. Local file/heading links and diff checks passed. Documentation-only work; no suites, builds, schema/storage operations or runtime/configuration changes. [Frontend organization](../../frontend/docs/setup.md) owns the editor-task handoff.
