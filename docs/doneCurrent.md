# Verification evidence

Updated **2026-11-18**. [Remaining work](workCurrent.md) · [Contracts](contracts.md) · [Check procedures](verification.md). Results belong to the dated runtime/storage profile below; they are not whole-app certification.

## Workflow maintenance (2026-11-18)

Implemented the approved workflow-only plan in both repositories: Linux static validation, verified full-SHA external action/reusable-workflow references, weekly GitHub-Actions-only grouped Dependabot PRs, pnpm-store/pip-download caches, immediate checkout SHA records and success/failure summaries. Automatic cancellation is scoped by workflow/event/branch or PR; scheduled/manual checks use unique run groups, and release serialization/manual browser behavior remains intact. Existing action major selections, application runtimes, commands, matrices, artifact contracts, reusable inputs and release permissions were preserved. The backend compatibility definition is pinned to the published frontend commit resolved during verification; application source inputs remain independent.

Linux Python **3.14.4**, PyYAML **6.0.3**, checksum-verified actionlint **1.7.7**: all **12 workflows**, the backend composite action and both new helper sources passed static validation. **34 embedded Python blocks** parsed without execution; **seven Bash blocks** passed `bash -n`. Read-only baseline comparisons checked original commands/triggers/matrices/permissions/artifact/reusable interfaces, cache paths/setup order, `always()` summary exception paths and concurrency separation. Isolated temporary validator probes accepted inert Python without executing it and rejected mutable references, duplicate keys, malformed Python and composite run steps without shell. Upstream GitHub API tag resolution verified seven action commit pins and the published frontend reusable workflow commit; the downloaded actionlint archive matched the embedded official checksum. Diff and documentation reference checks passed. Temporary verification material is under `/tmp/clinic-workflow-hardening/` and `/tmp/clinic-verify-workflow-changes.py`.

No application suite inspection/execution/changes, app builds/compilation/packaging, browser run, workflow dispatch, pushes, releases/tags, repository-setting changes, migrations, application dependency/lockfile changes or clinic-storage access. Only CI-tool/action references were added or pinned. Hosted cache behavior, Windows jobs, Dependabot PR creation, summary rendering, scheduled runs and coordinated pinned workflow execution remain unverified; automation documentation owns operation and limits.

## Logic review corrections (2026-11-18)

Implemented the approved source-only fix plan. Retention recognizes both legacy and current microsecond/UUID backup filenames. Browser-opening serving now uses `MAX_REQUEST_BODY_SIZE`, preserving the separate upload RAM threshold. XLSX datetimes serialize to the accepted space-separated, whole-second format before patient date parsing. Diagnosis/medication exports annotate and allow `usage_count` ordering with the same relations as their list endpoints. Clinic defaults use `get_or_create` to preserve configured settings. Dashboard high-risk rows include approved suicide/violence risk annotations, consumed by the coordinated frontend; [contracts](contracts.md#review-contract-handoff-2026-11-18) record the shape.

Linux Python **3.14.4** source-only checks passed: **six changed Python modules** parsed with AST, without application imports or bytecode generation. Extracted production functions with synthetic inputs/doubles verified XLSX datetime conversion including fractional seconds, accepted text dates/invalid-date rejection, both backup filename formats/unrelated-file rejection, approved-risk serialization, preservation of existing/default creation of missing clinic settings, and catalog export preparation/usage-count ordering in both directions while rejecting unsupported fields. The serving request-limit selection was checked with AST. No backup retention, seed, serving or application commands ran; query doubles do not verify ORM SQL. Both repositories passed diff whitespace and changed-document reference checks. Frontend checks are in its [evidence](../../frontend/docs/doneCurrent.md#logic-review-corrections-2026-11-18).

No suite inspection/execution/changes, builds/compilation/packaging, browser work, migration inspection/changes, dependencies/lockfiles, or clinic-storage access. Runtime HTTP/upload behavior, backup deletion, real database ordering, rendered UI/date-picker behavior and packaged deployment remain unverified. Deliver backend/frontend together for the approved-risk response change.

## Review fixes and contract handoff (2026-11-18)

Implemented reference/checksum receipts for exact issued PDFs and private generated artifacts using existing fields, legacy buffered replay, current authorization and exclusive reference-aware cleanup. Split context/password/idempotency handling; standardized string error codes/JSON security failures and API 404; added explicit human-activity idle sessions with 401 expiry. Collection reads use common items/metadata and explicit per-page inputs. Upload hashing and macro detection use seekable temporary files; the **2.5 MiB** memory threshold is separate from the total HTTP request cap.

Added scoped approved risk/timeline selectors, paged revision/issued-document histories, exact saved-document downloads and next-appointment IDs. Moved reviewed visit/billing/appointment/account/audit/patient-history queries and invoice rendering out of views. Added configurable frontend/private-response paths, explicit HTTP/LAN versus HTTPS/proxy settings, Waitress proxy trust and immutable bundled static serving. No schema or model-field changes; fresh-only setup, signed evidence, lifecycle/locking and receptionist draft permissions remain intact. [Contracts](contracts.md#review-contract-handoff-2026-11-18) own wire behavior; frontend owns screens and longer client waits.

Source-only Linux Python **3.14.4** checks: **232 production modules** parsed with AST, **701 local module references** resolved; no app imports, database or runtime execution for verification. Frontend source/formatting-rollback evidence is in its [log](../../frontend/docs/doneCurrent.md#review-fixes-and-missing-workflows-2026-11-18). No tests/builds, compilation/packaging, migration inspection/changes, dependency/version changes, deployment or clinic-storage operations. Concurrency, replay after process failure, memory, session timing, PDF/UI appearance and actual hosting remain unverified. Deliver both repositories together.

## GitHub workflows and Linux bundle (2026-11-17)

Added automatic Windows/Linux SQLite/native/HTTP checks and an owned Linux PostgreSQL job; manual executable packaging checks out an exact frontend SHA, gates packaging on frontend/backend regressions and uploads checksummed archives. Public sibling repositories use the ordinary job token, with no custom secret/variable setup. [Automation](automation.md) and [bundle guide](bundles.md) own usage and platform limits.

Follow-up: added Monday regression/audit schedules, manual cross-repository compatibility, reusable downloaded-archive checks and manual draft-release preparation. A tar.gz made from the previously verified Linux bundle passed SHA-256, extraction into a path containing spaces, source/platform provenance, native/PDF/HTTP/frontend checks and shutdown. Isolated `/tmp` probes rejected checksum corruption, ZIP/tar traversal, mismatched tag commits and mixed frontend revisions, and generated notes for a valid synthetic pair/tag. No project tag/release was created. Actionlint, YAML/inline-Python/helper syntax and documentation references passed. CI-only pip-audit was installed in `/tmp`; the SQLite requirements audit reported pdfkit `PYSEC-2026-2860` (two raw entries for one unique advisory). The workflow includes each shared requirements chain once and retains the raw report. Reports/logs: `/tmp/clinic-workflows-{archive-verification,backend-dependency-audit}.*`. No app version/dependency/lockfile changes or clinic storage access. Hosted cross-run downloads, Windows extraction, other audit profiles, scheduling, reusable compatibility and draft creation remain unverified; no deployment or local browser work occurred.

Linux Python **3.14.4**, Django **6.1.2**, DRF **3.18.3**, WeasyPrint **70.0**: SQLite **310 run, 18 skipped, zero failures**; PostgreSQL 18 **310 passed**, including concurrency/process-failure coverage. Corrected a stale launcher test rejecting supported Python 3.14 and covered both unsupported boundaries plus all supported minor versions. The first default-system-Python probe lacked project dependencies; verification used the configured project interpreter. Native/PDF and disposable HTTP start/access-denial/stop checks passed.

PyInstaller **6.22.3**, psycopg **3.3.9**, Redis client **8.1.0** and tzdata were installed only in `/tmp` for packaging verification. A first frozen check caught missing dynamic `magic` inclusion; the corrected Linux executable built and passed locks/MIME/fonts/time zones, in-memory Arabic/Latin PDF, HTTP config, anonymous patient denial, packaged HTML/font retrieval and shutdown from outside the source directory. Application code/templates/frontend assets are staged without clinic configuration, databases, media, backups, suites or application migration directories. Production serving preserves PostgreSQL/shared-cache guards and requires external configuration/data paths; schema setup/upgrades remain separate.

All workflow files passed actionlint **1.7.7**, YAML/Python source checks and diff/reference checks. No application dependency/lockfile/version changes or clinic storage operations. Isolated suites used synthetic temporary schema/storage without application migration inspection/changes. GitHub-hosted execution, Windows binaries, authenticated packaged deployment, exhaustive layout/PDF appearance, native dialogs and physical printing remain unverified. Frontend unit/build/component evidence belongs in its [log](../../frontend/docs/doneCurrent.md). Temporary logs/artifacts: `/tmp/clinic-workflows-*`; they may disappear.

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
