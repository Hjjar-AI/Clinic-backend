# Completed work

Updated: 2026-10-11.

- Automated test suite (2026-10-11): **134 tests passed** under Python 3.14 / installed Django 6.1.2. Isolated settings/runner block clinic environment/data access; migration modules disabled. Covers core validation, auth/CSRF/versions/replay, patient history/team/merge, signed visits/documents, schedules/billing/tasks, imports/authenticated recovery/media, reports/exports and commands. Real PDF bytes from Arabic HTML tested; typography/font assets unverified. Fixed explicitly mapped auth action permissions and absent export-column defaults. Cross-project browser suite: 21 Chromium cases passed. Separate pinned Django 5.0.6 / DRF 3.15.1 probe on Python 3.14 encountered two Django template-context errors; not a passing pinned-runtime matrix. PostgreSQL concurrency/production build remain unverified. [Commands, coverage and limits](testing.md).

- Fixed bootstrap SQLite startup when `data/` is absent: create the database parent directory before Django's command checks, without treating in-memory/URI databases as filesystem paths. Corrected the server hint to `127.0.0.1:5019`. With explicit user authorization, ran `bootstrap --with-demo-data` successfully: generated/applied initial migrations, seeded defaults, created 10 demo patients; `check --database default` reported no issues. Generated account credentials saved privately in ignored `data/bootstrap-credentials.txt` (0600), not printed in tool output. No destructive cleanup, test-suite work, builds, or dependency/version changes. Browser/API/PDF/PostgreSQL behavior remains unverified.

- Fixed startup `CheckConstraint(check=...)` TypeError in user's Django 6.1.2 environment: shared native-constraint factory selects `check` for pinned Django 5.0 and `condition` for Django 5.1+, used by all 30 check constraints across eight model files. Isolated app loading passed using the user's environment with database connections forbidden; native constraint cloning/serialization passed, AST comparison confirmed unchanged rules, and `git diff --check` passed. Pinned Django 5.0 branch/full bootstrap not executed; no migration/test-suite access, project database operations, builds, or dependency/version changes.

- Patient expansion: optional year-only birth, permanent numbers/nonblocking duplicate IDs and optional preview-bound merge, structured identifiers/contacts/representatives/allergies/ongoing medications/follow-ups, dated team history, document provenance, immutable corrections, tri-state clinical facts, configurable completeness; coordinated frontend/API/import/export/recovery. 89 isolated service/ORM/recovery assertions passed; pinned HTTP/browser/PostgreSQL checks pending. [Schema/retention](patient-record-schema.md), [verification](patient-record-verification.md).

- Second backend review: strict versions, document/care-team access and writes, service validation, stable lock queries, fractional billing constraints, scale bounds, doctor lookup privacy, backup integrity/catalog merge; coordinated frontend versions/member fields. Passed 101 isolated backend assertions (system Django 5.2.9; missing integration boundaries excluded), 10 frontend version assertions and source syntax checks. Pinned HTTP/browser/PostgreSQL verification remains pending. See [second-pass record](backend-second-pass.md).

- Enhanced/compacted both root agent guides: agreed limits, docs/handoff locations, review/fix workflow, verification boundaries, model/API and CSS/layout/RTL conventions.

- Moved both projects' handoffs to `docs/`; retained root `README.md`/`AGENTS.md`, updated local/cross-project links. Compacted other Markdown, preserving technical content/verification history.

- Created both READMEs and compact `AGENTS.md`/`workCurrent.md`/`doneCurrent.md`; checked links without running setup.
- Fixed all 27 findings: clinical validation/history, signing/issuance, backups/restore, access/authentication, concurrency/idempotency/cache, follow-ups, scheduling, billing, catalogs, imports, reports, reminders, exports, settings, and files.
- Integrated frontend versions/retries, referral POST, CSRF bootstrap, import previews/restore scope; see [frontend completed work](../../frontend/docs/doneCurrent.md).
- Passed isolated SQLite/real HTTP probes (Django 5.0.6/DRF 3.15.1), source/changed JS/Vue syntax, model constraints, backup round trips/media-tampering checks.
- No migration/test-suite access/changes, builds/compilation/packaging, project DB/dependency/version changes. Verification: `/tmp`/in-memory database.

Full record and limits: [backend-fixes-implementation.md](backend-fixes-implementation.md). Outstanding: [workCurrent.md](workCurrent.md).
