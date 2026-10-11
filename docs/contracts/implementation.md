# Backend implementation by source area

All 27 original logic findings and listed second-pass defects have source corrections. IDs below preserve traceability; these are completed corrections, not an active backlog. [Patient schema/API](patients.md), [test commands/file map](../testing/guide.md), [results](../doneCurrent.md), [open checks](../workCurrent.md).

## Clinical and operational contracts

- Clinical revisions/issued documents reject ordinary ORM/QuerySet changes/deletion; validated full recovery explicitly uses raw serialization/database operations.
- Authored visits retain doctor patient scope; care teams grant record scope; action permissions remain required. Receptionist defaults unchanged.
- Prescriptions/referrals require final/locked signed revisions; open amendments block issuance until re-signing. Prescription previews bind visit/patient version/template.
- Mutations use observed `version`/shared-parser `If-Match`; editors keep opening versions, actions may use last-observed versions.
- Authorized read-only history: `GET /visits/<id>/revisions/`, `GET /visits/<id>/issued-documents/`; no mutation endpoints.
- Patient archive/restore: explicit POST; archive preserves linked records. Pseudonymization retains signed identities/narratives/audit/historical access.
- Follow-ups distinguish `completed`/`missed`/`cancelled`/`waived`; bulk overdue closure means missed, cancelled/waived never count as completed adherence.
- Billing: single full payment, default SYP, two-decimal half-up rounding; partial payments/refunds/credit notes were not inferred requirements.
- Existing working-hour/arrived-edit policies retained; historical dates allowed, completed appointments cannot move.
- Restore previews bind digest/scope. Full patient recovery requires complete related data/revokes sessions; catalog recovery preserves clinical records/current users.
- Portable recovery: full ZIP. JSON has all logical records, no bytes; full recovery rejects missing referenced files. Reject incomplete legacy schemas before mutation; retain installation HMAC key.
- Imports: UTF-8 CSV/XLSX; convert formulas to values. Invalid/empty replacements cannot retire catalogs.

## Original finding map

| Files / finding | Implemented change |
| --- | --- |
| `apps/backup/backup_creator.py, backup_validation.py` — 1 | Shared canonical JSON/HMAC payload serialization and verification. |
| `apps/backup/backup_creator.py, backup_restore.py, backup_validation.py` — 2–3 | Full managed application/auth/content-type/audit inventory, archived records, original IDs/timestamps, labs, signed ZIP manifest, per-member checksums, bounded archives, reference validation, complete logical recovery and media compensation. Catalog-only restore merges without replacing clinical history. |
| `apps/visits/models.py, services.py` — 4 | Append-only `VisitRevision` snapshots at signing and amendment completion; reason, signer, time, patient identity, clinical rows, labs, scale definitions/answers, attachment inventory. |
| `apps/visits/services.py; apps/prescriptions/; apps/referrals/` — 5 | Server-authorized signing; append-only `IssuedDocument` with exact issued bytes, checksum, revision, actor, snapshot, signature/stamp; referral issuance uses POST. Issuance locks and rechecks visit version/state. |
| `apps/visits/serializers.py, services.py, lab_validation.py` — 6–7 | Bounded typed clinical JSON and row normalization before replacement; valid references, lengths, null handling and final-section validation; pending labs do not need fabricated values. |
| `apps/clinical/serializers.py; apps/visits/scale_validation.py` — 8 | Finite numeric scores, valid steps, required answers, retired-definition restrictions and persisted validated field defaults. |
| `apps/visits/models.py; apps/clinical/services.py` — 9 | Self-contained diagnosis/medication snapshots, including controlled classification; document content reads finalized revisions. |
| `core/access.py, permissions.py; scoped views/dashboard` — 10 | Shared patient/visit/appointment/invoice scope; care-team access and historical author access; permission-filtered dashboard sections; clinical patient subresources require visit permission. |
| `apps/accounts/models.py, services.py; core/middleware.py` — 11–12 | Login outside request-wide transactions, durable failed counters, anonymous-login CSRF, dummy hashing, server-controlled password-change gate, effective-permission reporting, versioned password changes and role groups seeded only on creation. |
| `apps/visits/services.py; apps/reports/visit_statistics.py` — 13 | Versioned follow-up outcomes, actor and time; overdue bulk closure records missed follow-ups; new due dates reset completion. |
| `apps/patients/services.py; versioned lifecycle services` — 14 | Locked/versioned destructive actions, archived-state rechecks, archive metadata, explicit patient archive/restore, preserved dependent history and active-parent checks for new records. |
| `core/middleware.py, models.py; covered views` — 15 | Durable idempotency records, canonical request digest, saved successful response replay, multipart boundary-independent fingerprints, expanded endpoint coverage and retained frontend operation keys after uncertain network failures. |
| `core/cache_utils.py; model signals` — 16 | Cache invalidation after commit, captured generation publication, random generation tokens and protected previews/idempotency records during general cache clearing. |
| `apps/appointments/services.py, views.py` — 17 | Canonical appointment duration, validation for inactive schedules, reminder reset, datetime overlap intervals including the prior day, consistent duration bounds and scoped calendar filters. |
| `apps/billing/models.py, services.py` — 18 | `InvoiceLine`, server-derived totals, explicit currency, two-decimal half-up rounding, paid actor/time, payment method supplied on payment, immutable issue identity/clinic snapshot and itemized PDF context. Legacy total-only clients receive one service line. |
| `history-bearing models; apps/patients/services.py` — 19–20 | Protected historical parent relationships; patient archive keeps dependencies; identity restriction explicitly preserves signed history and is described as pseudonymization rather than complete anonymization. |
| `apps/reports/` — 21 | Authoritative explicit report periods, empty month filling, period-aware visit average, stable concept grouping with saved labels, latest-assessment risk and validated summary dates. |
| `core/management/commands/send_*_reminders.py` — 22 | Clinic-local business dates, reminder catch-up windows across midnight, occurrence-specific dedupe, updated timestamps and suppression of empty audit updates. |
| `apps/import_export/services.py, views.py` — 23 | Shared preview/execution parsers for CSV/XLSX, no truncation, national-ID duplicate rules, phone warnings, mapping/policy-bound medication preview, validated row outcomes and guarded replacement. |
| `apps/clinical/services.py; settings/template services` — 24 | Canonical catalog persistence, versioned catalogs/scales/templates/settings, dedicated retirement/reactivation, writable ordering/controlled flags and normalized medication identity constraint. |
| `apps/visits/serializers.py; services/model constraints` — 25 | Visit serializers delegate to services; database enum/version/range constraints; audited task reorder and canonical reactivation; validated demo records are signed through the normal service. |
| `core/file_utils.py; visit attachments; reconcile_media` — 26 | Attachments require editable visit state and expected version; verified MIME/size/checksum, cleanup on persistence failure, retained signed inventory and media recovery. `reconcile_media` reports missing/old orphaned uploads and deletes only with explicit `--delete`. |
| `apps/exports/; apps/settings/services.py` — 27 | Spreadsheet text-cell protection, validated export columns, canonical clinical JSON export mapping, atomic bounded settings updates and correctly stored demo labs. |

## Source-specific hardening

| Location | Defect / impact → correction |
| --- | --- |
| `core/mutation.py`; accounts/patients/visits/appointments/billing/tasks views | Versions accepted booleans/floats, could overflow, or ignored `If-Match` → shared positive-integer parser; quoted headers accepted; conflicting body/header rejected. Task/user services also validate versions. |
| `patients/views.py` | Documents used obsolete doctor/creator checks; care-team/historical authors lost access, including archived-patient history → shared patient scope and explicit view/manage permissions. Upload requires an active scoped patient. |
| `patients/services.py`, `serializers.py`; `core/signals.py` | Generic document metadata writes and deletion bypassed optimistic locking → document versions exposed; locked, validated metadata/archive services; version changes audited without recording description text. |
| `patients/services.py`, `views.py` | Care-team changes raced duplicate/archive checks and ignored patient versions; malformed IDs could fail unexpectedly → lock/version active patient, validate IDs/roles/member, bump patient version, audit membership change, trigger existing after-commit cache invalidation; return current parent version. |
| `patients/services.py` | Direct service updates could alter lifecycle/ownership and persist invalid choices/lengths; malformed birth years raised type errors → editable-field allowlist, complete model validation, typed year check. |
| `tasks/services.py` | Updates could overwrite protected fields, skip model validation or accept boolean versions → allowlist, shared mutation checks, model validation for create/update/transitions. |
| `tasks/services.py`; `core/access.py`, `visits/services.py` | Task reordering locked nullable user joins and used caller-dependent lock order; overdue visits locked an unnecessary outer `DISTINCT` → join-free task rows locked once in PK order; outer visit DISTINCT removed; overdue locks ordered by PK. PostgreSQL rationale: [SELECT restrictions](https://www.postgresql.org/docs/current/sql-select.html); actual PostgreSQL concurrency remains unchecked. |
| `core/lifecycle.py`; scheduling/tasks/billing services | Unhashable status values raised type errors; cancellation reasons were stringified indiscriminately or exceeded column limits → typed status/reason validation, bounded reasons, required cancellation/no-show reasons. |
| `appointments/services.py` | Direct create/update scheduling treated date/time inputs inconsistently and skipped model validation → normalize local date/time inputs; validate complete models before writes. |
| `billing/models.py` | SQLite rejected valid fractional totals (`0.10 + 0.20 = 0.30`) and some fully discounted bills → round monetary expressions to two places in both constraints, preserving rejection of inconsistent totals/excess discounts. |
| `billing/services.py` | Extreme/fractional money could overflow or depend on later serializer checks; generic updates exposed protected metadata; referenced visit state could be stale → bounded two-place finite amounts/final totals, editable-field allowlist, reload/lock referenced visit. |
| `clinical/models.py`, `visits/scale_validation.py` | Scale definitions accepted infinite ranges/off-step defaults; finite extremes could overflow answer step arithmetic → model validation of finite ranges/steps/default alignment; answer/definition conversion and increment overflow rejected. Restore also invokes model `clean()`. |
| `accounts/views.py` | Doctor lookup exposed stamp data, preferences, permissions and account state → only `id`, `username`, `full_name`, `role`. Existing picker consumers use these fields. |
| `backup/backup_validation.py`, `backup_restore.py` | Non-ASCII signatures could raise type errors; malformed counts were accepted/crashed; empty service restore scope silently succeeded → validate hexadecimal HMAC shape, count types/inventory and nonempty scope. |
| `backup/backup_creator.py`, `backup_restore.py` | Signed ZIP inventory could omit referenced files; file existence did not prove record checksum/size correctness → complete backup creation verifies clinical references; recovery verifies referenced bytes against record size/checksum, including existing-storage JSON recovery. |
| `backup/backup_restore.py` | Medication merge used case-sensitive identity despite Lower/Trim uniqueness → match the same database expressions, preserve existing IDs, increment versions and validate merged/new catalogs. |
| Frontend patient components/services; `apiClient.js` | Care-team UI used nonexistent name/removal fields and lacked parent versions; nested document versions could overwrite patient versions → correct member mapping, explicit care-team versions/refresh, isolated nested document registry and correct id-less parent responses. |

## Existing guards retained

| Sources | Important behavior |
| --- | --- |
| `apps/appointments/services.py` | String times normalized; timezone-bearing/invalid times rejected; reopen availability rechecked through update/actions; completed bookings cannot move; canonical integer durations reject boolean/zero/negative/oversized inputs; reminder flags read-only. |
| Appointment/billing creation | Scoped patients required; doctors cannot book another doctor's schedule; supplied visits must exist/be active; invoice finite values and effective issue/due dates validated. |
| Account/permission services | Active superuser grants, inactive denial, Django direct/group cache clearing; atomic user create and last-active-admin demotion/deactivation checks with stable evaluated locks. |
| Task services | Actor-aware reassignment, unique valid reorder IDs, current locked state before invoice/task delete guards. |
| Patient models/services | Name-only updates refresh normalized search; doctor eligibility validated; default registration/admission uses clinic-local date. |
| `core/pagination.py` | Invalid limits/negative offsets bounded. |

## Runtime-discovered corrections

| Sources | Failure → retained correction |
| --- | --- |
| `core/constraints.py`, eight model files | Django 6 rejected native `check=` → factory selects Django 5.0 `check` / 5.1+ `condition`, preserving all 30 constraint predicates/cloning. |
| Bootstrap management command | Missing SQLite parent directory prevented command checks → create parent before checks, leave memory/URI paths alone; corrected 5019 server hint. |
| `apps/accounts/views.py` | Explicit URL mappings bypassed decorator permissions → explicitly reject anonymous `me`, logout and change-password. |
| Patient CSV/XLSX export view/service | Absent field list was converted to invalid empty selection → omitted fields use defaults; explicit invalid columns still rejected. |
| `core/renderers.py`, persisted idempotent responses | 204 JSON body broke Vite proxy after archive committed → empty bytes for 204/205/304; test actual renderer/replay because Django test client strips bodies. |
| `apps/backup/backup_creator.py` | Default JSON encoding truncated signed/paid datetime microseconds → backup-specific full ISO precision, signed snapshot regression. |
| `core/pdf_utils.py`, PDF templates | System-font fallback/bidi/pagination defects → bundled Cairo/Inter, shared font configuration, numeric isolation, complete decimal cells and flowing long sections; [PDF details](../testing/pdf.md). |

Verification: original and second-pass isolated SQLite/HTTP/recovery probes exercised constraints, scope, versions, signing, multipart replay, import parity, exact issued bytes and tampered-media rejection. Early missing phone/MIME/DRF boundaries were excluded or fail-closed substitutes; they never established full HTTP compatibility. Later tests/browser workflows cover explicit scenarios with real APIs. PostgreSQL locking/concurrent writers, supported pinned-runtime compatibility and production builds remain unverified. No migration file inspection is implied by this record; authorized bootstrap is recorded separately.
