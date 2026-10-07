# Backend models and logic review

Reviewed: 2026-10-07.

**Implementation status:** the findings below are the original review record. The authorized fixes have now been implemented; see [implementation details, decisions, and verification](backend-fixes-implementation.md). The original verification limitations at the end describe the review pass, not the subsequent fix pass.

 Scope: application models, services, serializers, views, permissions, audit, reporting, imports, reminders, and backup/restore.

No migration files or test-suite files were inspected or changed. No builds, packaging, dependency/version changes, or compilation tasks were run. This pass adds this report; the implementation fixes listed below were made in the earlier pass and are present in the current checkout. The current Git baseline already contains those fixes.

## Assessment and recommended order

The app has a useful service layer, explicit lifecycle definitions, optimistic version fields, decimal invoice calculations, scale-definition snapshots, and soft deletion. The highest priority is reliable recovery and preservation of signed clinical history. Starting with a fresh database makes structural improvements easier, but does not address these logic defects by itself.

1. Repair backup/restore completeness, signatures, and validation.
2. Preserve clinical revisions and issued documents; strengthen signing and nested-input validation.
3. Unify access rules and fix authentication transaction behavior.
4. Make mutations, reminders, and cache publication consistent.
5. Improve invoice structure, report definitions, and import previews.

P0 = data-loss/recovery defect; P1 = significant integrity or access issue; P2 = correctness or maintainability improvement. Findings described as reproduced used isolated probes with stubbed persistence/dependencies, not full HTTP or production-database execution. Other findings come from tracing source paths; concurrency risks need confirmation on the intended database.

## Findings and concrete recommendations

### 1. P0 — A newly generated JSON backup fails signature verification

Evidence: [creator](../apps/backup/backup_creator.py#L137), [verifier](../apps/backup/backup_restore.py#L62).

The creator signs the serialized inner data, then returns an envelope containing `signature` and `data`. The JSON restore verifier computes its HMAC over the complete envelope. These are different byte sequences. A probe calling the current creator and verifier reproduced `Backup signature verification failed` with an empty logical backup.

Recommendation: sign and verify the same precisely specified payload bytes. Use one shared serialization/signing function, reject missing/invalid signatures, and define how existing archives are interpreted without silently trusting unsigned data. ZIP and standalone JSON must follow the same contract.

### 2. P0 — “Full” restore does not restore the full backup and deletes additional records

Evidence: [restore implementation](../apps/backup/backup_restore.py#L128), [backup contents](../apps/backup/backup_creator.py#L188), [execute endpoint](../apps/backup/views.py#L84).

Execution reads `backup.json` and rebuilds patients, visits, diagnoses, medications, visit attachments, and scale responses. It never restores the included `clinic.db` or media members. Deleting patients cascades into appointments, invoices, patient documents, care-team membership, and visit-linked prescription signatures. Those records are not recreated. On a clean environment, attachment database paths are restored without restoring their files. Preview only advertises replacement of four categories.

Recommendation: make complete disaster recovery and selective logical import separate operations. A complete restore must restore all supported entities and media consistently. A selective restore must preserve unrelated records or explicitly include their removal in the preview. Do not report a successful full recovery from the current partial reconstruction.

### 3. P1 — Backup coverage, authenticity, and compatibility checks are incomplete

Evidence: [JSON selection](../apps/backup/backup_creator.py#L137), [patient serialization](../apps/backup/backup_creator.py#L20), [preview](../apps/backup/backup_restore.py#L87).

Logical backups exclude archived patients, archived visits/attachments, and retired catalog entries. They omit `Visit.lab_values` entirely. Patient/visit creation and modification times are serialized but not restored. Missing DOB becomes the fabricated year `1998`. Unknown visit statuses are treated as finalized. Preview computes compatibility but execution never rejects unsupported format versions. The ZIP signature authenticates `backup.json`, not the database, manifest, or media members.

Recommendation: define an explicit backup inventory; include archived history, labs, original identifiers/timestamps, and every required entity. Restore missing DOB as unknown and reject unknown lifecycle values. Validate format, shape, lengths, cross-references, expanded archive size, and member checksums before mutation. Sign a manifest covering every member. Use a consistent database snapshot mechanism; direct copying after a WAL checkpoint can race with subsequent writes.

### 4. P1 — Clinical amendments overwrite signed history

Evidence: [visit update](../apps/visits/services.py#L109), [nested replacements](../apps/visits/models.py#L184), [audited fields](../core/signals.py#L24).

`final → amended` permits updates to the original visit. Diagnoses, medications, and scale responses are deleted and recreated. The audit snapshot records workflow/risk/version fields but not the main complaint, history, treatment, notes, clinical JSON, lab values, or full nested records. Therefore previous clinical content cannot be reconstructed reliably from this audit trail.

Recommendation: add immutable `VisitRevision` snapshots at finalization and amendment completion, including scalar fields, diagnoses, medications, labs, scale definitions/answers, author, signer, date, and amendment reason. Keep optimistic `version` for concurrency and a separate revision number for history. Point generated clinical documents at a finalized revision.

### 5. P1 — Signing and document issuance need a stronger contract

Evidence: [visit serializer](../apps/visits/serializers.py#L39), [visit transitions](../apps/visits/services.py#L177), [prescription service](../apps/prescriptions/services.py#L22), [signature storage](../apps/prescriptions/services.py#L122), [referrals](../apps/referrals/views.py#L13).

Clients can supply another active user's `signed_by_id` and a manual signing date. Finalization does not set signer/date from the authenticated actor. Prescriptions and referrals allow any non-draft status, including a visit currently being amended. Signature storage updates one row per user/visit, overwriting earlier signatures; neither the exact issued PDF nor its complete immutable issuance record is retained. Referral reason is supplied in a GET query string, which can enter browser/proxy logs.

Recommendation: authorize signing explicitly, set signer and signed timestamp on the server, and generate documents from a specified finalized revision. Add append-only `IssuedDocument` records with actor, revision, snapshot, checksum, generated time, signature/stamp, and optional stored PDF. Use POST for referral issuance and place the reason in its body.

### 6. P1 — Nested visit input is not validated as structured clinical data

Evidence: [nested serializer fields](../apps/visits/serializers.py#L41), [diagnosis/medication setters](../apps/visits/models.py#L184), [clinical JSON use](../apps/exports/base.py#L67).

The write fields are generic `ListField`s with no child serializers. Diagnosis and medication setters assume each row is a dictionary and trust foreign-key IDs and lengths. Invalid shapes can raise attribute errors; invalid references may fail at database constraint checking. Arbitrary `clinical_data` can be a list/string even though exports call `.get()` on it.

Recommendation: add typed input serializers/normalizers for diagnosis and medication rows. Validate row counts, object shape, reference eligibility, field lengths, and custom-versus-catalog rules before deleting existing relations. Require a bounded object schema for clinical JSON. Reuse the same validation for imports and restore.

### 7. P1 — Null clinical fields can pass completeness validation

Evidence: [lab normalizer](../apps/visits/lab_validation.py#L9), [finalization checks](../apps/visits/services.py#L35).

The normalizers/checks use `str(value)`. JSON `null` becomes nonempty text `"None"`; final lab validation accepts null name and value when date/status are provided. This was reproduced. Medication completeness checks use the same pattern.

Recommendation: handle null as missing, enforce expected primitive types, and reject oversized input instead of silently truncating clinical values. Distinguish pending labs from complete results rather than inventing values to satisfy finalization.

### 8. P1 — Scale validation accepts invalid scores and new uses of retired definitions

Evidence: [response normalizer](../apps/visits/scale_validation.py#L6), [field validation](../apps/clinical/serializers.py#L41).

`float('NaN')` passes both `< minimum` and `> maximum` checks and makes the total score NaN. Slider values are not checked against the configured step. New responses resolve scales with `all_objects`, so retired scales can be selected. Isolated probes reproduced all three behaviors. Missing answers fall back to defaults, which can make an unanswered assessment look completed. Separately, field validation assumes a missing default equals the supplied minimum but does not put that value in `attrs`; the model still defaults to zero, potentially violating its range constraint.

Recommendation: require finite numeric values, validate slider increments, persist the validated default, allow retired definitions only for an existing historical snapshot, and represent unanswered questions explicitly. Add a completion rule before treating an assessment as scored/final.

### 9. P1 — Historical diagnoses and medications can change with catalog edits

Evidence: [visit getters](../apps/visits/models.py#L149), [setters](../apps/visits/models.py#L184), [catalog updates](../apps/clinical/services.py#L27).

Display getters fall back to current catalog fields if custom/snapshot text is blank. Medication controlled status always comes from the current catalog. Editing a catalog entry can change the display or controlled classification of an earlier finalized visit without incrementing its version.

Recommendation: populate immutable code/name/dosage/brand/controlled snapshots on every saved visit row. Retain optional catalog references for searching and grouping. Historical documents should consume snapshots, never mutable catalog labels.

### 10. P1 — Access policies differ between related endpoints

Evidence: [visit object permission](../core/permissions.py#L221), [visit queryset](../apps/visits/views.py#L59), [dashboard](../apps/dashboard/views.py#L13), [patient timeline](../apps/patients/views.py#L167), [care-team model](../apps/patients/models.py#L150).

Object permission allows a doctor to access visits they authored, while the visit queryset requires the doctor to be the patient's current doctor. Reassignment can therefore remove an author's historical access. Care-team membership does not grant access anywhere in these policies. The dashboard requires authentication only and returns clinical risk/follow-up data and task descriptions even if a user's relevant permissions were removed. Patient timeline/risk endpoints require patient-view permission without separately requiring visit-view permission.

Recommendation: define shared `accessible_patients/visits/appointments/invoices` querysets and one object-access policy used by lists, details, creation, dashboards, exports, and reminders. Decide explicitly whether authors retain access after reassignment and whether care-team membership grants access. Gate sensitive dashboard sections and clinical patient subresources using their corresponding permissions.

### 11. P1 — Failed-login counters conflict with request-wide transactions

Evidence: [login failure path](../apps/accounts/services.py#L18), [counter mutation](../apps/accounts/models.py#L103), [database settings](../config/settings/base.py#L180), [exception delegation](../core/exceptions.py#L55).

`ATOMIC_REQUESTS` is enabled. A wrong password increments the database counter and then raises DRF `AuthenticationFailed`. The default DRF exception handler marks an active request transaction for rollback, so the counter increment and resulting lockout can be rolled back along with the failed request. This follows the transaction wiring and the [official DRF handler implementation](https://github.com/encode/django-rest-framework/blob/master/rest_framework/views.py); full HTTP reproduction was not possible without installed DRF.

Recommendation: put the login endpoint outside request-wide atomic handling and give security-state updates their own short committed transaction. Keep account lockout updates durable on failed responses. Also use a dummy password hash check for unknown usernames to reduce observable timing differences, and verify login-specific CSRF protection for anonymous session login.

### 12. P1 — Forced password changes and permission reporting are incomplete

Evidence: [user serializer](../apps/accounts/serializers.py#L7), [user updates](../apps/accounts/services.py#L110), [session middleware](../core/middleware.py#L88).

`force_password_change` is writable in the generic user serializer, and no backend gate limits a flagged account to password-change/session endpoints. Password changes and some security-state changes do not increment the user version. Permission output is assembled from groups/direct grants, so it can disagree with an active superuser's `has_perm()` result. `_apply_role_group()` rewrites permissions for an existing role group whenever a user is created or changes role.

Recommendation: make forced-change state server-controlled, enforce it on the backend, version relevant user changes, and expose one authoritative effective-permissions calculation. Seed role groups explicitly and avoid rewriting existing group permissions as a side effect of creating a user. Validate permission-update payloads as a list of strings before set operations.

### 13. P1 — Follow-up completion can lose edits and inflate adherence figures

Evidence: [single/bulk completion](../apps/visits/services.py#L251), [follow-up statistics](../apps/reports/visit_statistics.py#L60).

Single completion accepts no expected version and does not increment it. Bulk completion marks every overdue follow-up completed without recording actual contact, actor, outcome, or completion date. It uses `QuerySet.update()`, bypassing save audit and cache signals. A missed follow-up becomes indistinguishable from a completed one in adherence figures. Changing follow-up date through a visit edit does not automatically reset a previously completed flag.

Recommendation: distinguish completed, missed, cancelled, rescheduled, and waived follow-ups. Prefer a linked `FollowUp` record with due date, outcome, completion actor/time, and version. Until then, lock/version single changes, reset completion on a new due date, and make bulk closure an explicit auditable outcome rather than “completed”.

### 14. P1 — Destructive actions and archived objects do not share a version contract

Evidence: [patient removal/anonymization](../apps/patients/services.py#L167), [appointment mutations](../apps/appointments/services.py#L171), [visit mutations](../apps/visits/services.py#L109).

Several deletion/archive/anonymization actions accept no expected version. Some mutation paths reload through `all_objects` after a view fetched an active instance, but never recheck active/deleted state. A concurrent archive can therefore leave another request editing or transitioning a now-archived object. Patient dependency checks omit care-team records, and the “use archive” error does not correspond to a separate patient archive action.

Recommendation: use the same lock/version/active-state checks for edit, transition, archive, restore, and anonymize. Define a real archive action that keeps readable history and rejects new clinical/financial records. Recheck active patients under the mutation transaction when attaching new records.

### 15. P1 — Idempotency blocks retries without recovering the successful result

Evidence: [middleware](../core/middleware.py#L29).

The stored value is a boolean. A retry after a successful write whose response was lost receives 409 rather than the original result. Keys are scoped to the user but not request method/path/payload. Cache expiry/eviction and global cache clearing can remove the protection. Options, scales, and templates are absent from the enforced prefixes even though they are mutable resources.

Recommendation: store an operation record with user, method, route, payload digest, processing state, resulting resource, and response/status. Return the saved successful result for the same request; reject reuse with different data. Keep durable records for important creates/issuances and bound key length. Treat in-progress operations separately from completed requests.

### 16. P1 — Cache invalidation can publish stale data as current

Evidence: [cache utility](../core/cache_utils.py#L38), model-specific save signals, [bulk follow-up update](../apps/visits/services.py#L258).

Signals invalidate cache groups before the surrounding transaction commits. Another request can read old committed data and publish it under the new version. `set_grouped_key()` obtains the version at write time, allowing a query begun before invalidation to be stored in the newer group; an isolated interleaving reproduced that mechanism. Bulk updates bypass invalidation entirely.

Recommendation: invalidate after commit using `transaction.on_commit()`. Capture the cache generation before querying and only publish into that generation, or discard the result if it changed. Explicitly invalidate after bulk mutations. Keep idempotency and preview records outside the scope of a general settings cache-clear action.

### 17. P2 — Appointment scheduling rules still need consistency

Evidence: [update](../apps/appointments/services.py#L171), [calendar](../apps/appointments/services.py#L340), [availability endpoint](../apps/appointments/views.py#L194).

The earlier fixes address the main reopen/reschedule problems. Remaining issues: cancelled/no-show schedule edits skip availability but also skip duration validation and reminder reset; the legacy `duration` alias may affect checks without being persisted; duration bounds differ between model/service and availability API; calendar doctor filters can fall back to an unfiltered accessible queryset; cancellation filtering differs by branch. Occupied intervals use time-only endpoints, so an existing cross-midnight interval loses its date component.

Recommendation: normalize scheduling input once, persist only canonical keys, validate every requested schedule even when non-occupying, and share availability constants. Apply requested doctor/date/status filters after access scoping. Represent intervals as datetimes. Keep a documented working-hours and past-booking policy, including whether arrived appointments can be moved. Confirm race handling on the intended database; SQLite does not provide the row locks assumed by the schedule sentinel.

### 18. P2 — Invoice structure is too limited for a durable billing record

Evidence: [invoice model](../apps/billing/models.py#L7), [creation/update/transition](../apps/billing/services.py#L51).

Invoices have one supplied total, tax, and discount, without itemization, currency, payment records, or explicit paid actor/time. Payment method is free text and must already be present before issue because ordinary edits are blocked afterward. Issued patient details are read from the mutable patient record. Status supplied during creation/update is ignored rather than clearly rejected or declared read-only.

Recommendation: add `InvoiceLine` records and derive totals server-side. Choose currency and rounding policy explicitly. Add payment records if partial/multiple payments are needed; otherwise retain a simpler model with validated method, paid actor/time, and a clear pay action. Snapshot billed patient/clinic details on issue. Keep financial correction as cancellation/credit rather than editing an issued record.

### 19. P2 — Physical deletion can remove clinical and financial history

Evidence: [appointment patient/doctor FKs](../apps/appointments/models.py#L16), [invoice patient FK](../apps/billing/models.py#L15), [signature FKs](../apps/prescriptions/models.py#L5).

Several history-bearing relationships use `CASCADE`. Normal endpoints mostly use soft deletion, but restore, management commands, or a later admin interface can still physically delete parents and their history. This is already material in the current restore path.

Recommendation: use `PROTECT` for clinical/financial parents where history must survive; use nullable `SET_NULL` only with sufficient immutable identity snapshots. Reserve cascades for dependent rows whose deletion is truly intended. Do not change these relationships independently of the restore redesign.

### 20. P2 — Archival and anonymization need separate meanings

Evidence: [anonymize](../apps/patients/services.py#L185), [audit contents](../core/signals.py#L24).

Current anonymization changes the patient identity, archives it, clears doctor/creator and also removes family history/important notes. It does not scrub visit narratives, document contents, attachment names, or identity-bearing audit history. It should not be described as complete anonymization. Clearing clinician links also changes historical access.

Recommendation: separate archive, reversible identity restriction/pseudonymization, and irreversible erasure. Define which retained clinical data must remain and how authorized history is accessed. Scope an anonymization operation across all identity-bearing resources and record its purpose/result without reproducing removed identity in the new audit entry.

### 21. P2 — Reports use inconsistent periods and mutable grouping labels

Evidence: [monthly visits](../apps/reports/visit_statistics.py#L18), [diagnoses/medications](../apps/reports/visit_statistics.py#L38), [patient acquisition](../apps/reports/patient_statistics.py#L27), [report view](../apps/reports/views.py#L19).

Monthly series always add a rolling “today minus N months” restriction, even with an explicit older date range. Months with zero rows are omitted. Average visits per patient ignores the selected date range. Top diagnoses/medications group by both catalog and custom text and display catalog labels first, while visit displays prefer custom values; one clinical concept can be split and historic labels can change. High-risk patients are selected from any past high-risk visit, so they do not mean “currently high risk”. Monthly-summary parameters are parsed without safe range validation.

Recommendation: make explicit date filters authoritative, fill empty calendar periods, and return definitions for every KPI. Group on a stable catalog/concept identifier or a defined custom normalized key, with historical display snapshots. Define high risk as latest assessment or clearly label it “ever recorded high risk”. Validate report month/year and distinguish all-time patient metrics from period metrics.

### 22. P2 — Local dates and reminder windows are inconsistent

Evidence: [appointment job](../core/management/commands/send_appointment_reminders.py#L14), [task job](../core/management/commands/send_task_reminders.py#L14), dashboard/report services.

Several business dates use `timezone.now().date()` or host `datetime.now()` instead of the clinic's local date. Appointment hourly reminders query only one date, missing windows crossing local midnight. Day reminders select one exact due day, so an outage can skip them completely. Many reminder flags are updated without updating `updated_at`, and general save auditing records events even when audited business fields did not change.

Recommendation: use clinic-local dates consistently and timezone-aware datetimes for windows. Query the full reminder interval, define catch-up behavior, and keep dedupe keys tied to the actual schedule occurrence. Avoid auditing scheduler bookkeeping as a clinical edit; use a separate delivery event if needed.

### 23. P2 — Imports can disagree with previews and silently discard valid records

Evidence: [patient preview/import](../apps/import_export/services.py#L57), [diagnosis preview/import](../apps/import_export/services.py#L162), [medication mapping](../apps/import_export/views.py#L246).

Patient import treats a shared phone as a duplicate and skips the row, although family members can share phones and the normal patient model permits them. Patient fields are truncated, while normal creation uses a different validation path. Diagnosis preview permits a two-column row that execution rejects for lacking a third column. Medication preview is a raw sample; it is not bound to the final column map or overwrite choice. Catalog replace/overwrite retires everything before processing, even if every row is invalid. Row-level validation/errors are much weaker than the patient importer. Empty medication files can index a nonexistent first row.

Recommendation: share one validated row parser between preview and execution. Make national-ID matches strong duplicates and phone matches reviewable warnings. Bind previews to mapping, merge policy, target doctor, and digest. Require at least one valid record and clearly preview retirement effects before replace/overwrite. Use row savepoints, length/type validation, stable outcomes, and safe empty-file handling.

### 24. P2 — Catalog writes ignore accepted fields and bypass concurrency controls

Evidence: [diagnosis service](../apps/clinical/services.py#L11), [medication service](../apps/clinical/services.py#L46), [catalog serializers](../apps/clinical/serializers.py#L11).

Diagnosis creation/update ignores submitted ordering/activity fields. Medication creation ignores `is_controlled`, ordering, and activity. Medication update has weaker duplicate handling than creation. Catalogs, scales, templates, and clinic settings have no version contract even though editing them affects current clinical workflows. Serializer and service persistence paths differ.

Recommendation: explicitly define writable fields and persist or reject each one; make retirement/reactivation dedicated actions. Use one service path for each resource. Add version checks where concurrent edits matter, preserve immutable definition snapshots, and introduce a normalized medication-identity rule if duplicate catalog entries are undesirable.

### 25. P2 — Multiple write paths bypass the service rules

Evidence: [visit serializer create/update](../apps/visits/serializers.py#L96), [service lifecycle](../apps/visits/services.py#L50), [task model reactivation](../apps/tasks/models.py#L90).

The visit serializer independently creates/updates rows and nested data without the service's lifecycle, finalization, and optimistic-lock checks. Existing views currently call services, but another view or script using `serializer.save()` can bypass the rules. Similar direct model helpers and demo/restore writers implement their own behavior.

Recommendation: make serializers validation/representation adapters and route all ordinary clinical mutations through canonical services. Keep explicit, separately validated restore/seed interfaces for exceptional operations. Put crucial status/version/range invariants into database constraints where appropriate.

### 26. P2 — File and document operations are not covered by clinical immutability

Evidence: [attachments endpoint](../apps/visits/views.py#L210), [attachment deletion](../apps/visits/views.py#L241), [file storage](../core/file_utils.py#L58).

Attachments can be added or archived on finalized/locked visits without a revision policy. File bytes are saved before the database row; a later transaction failure can leave orphaned storage. File size and MIME metadata partly use client properties rather than the validated detected values. Document relationships are not fully covered by the logical backup.

Recommendation: decide whether attachments form part of the signed revision or are separately append-only administrative documents. Record who added/retired them and why. Add storage cleanup on failed persistence and orphan reconciliation, persist verified metadata/checksums, and include document inventory/media in recovery.

### 27. P2 — Export and settings paths need small correctness improvements

Evidence: [CSV/Excel exports](../apps/exports/patient_export.py#L14), [report export](../apps/exports/report_export.py#L9), [settings update](../apps/settings/services.py#L75), [PDF data](../apps/exports/base.py#L134).

Exports place untrusted strings directly into spreadsheet cells; leading formula characters need a deliberate text-cell policy. User-selected unsupported CSV columns can produce an empty export instead of a validation error. Clinical formulation/MSE export reads attributes not present on `Visit`, so those sections are blank even if the corresponding information lives in clinical JSON. Settings update writes keys sequentially; a later validation error can return 400 after earlier changes were saved. Theme/clinic strings and demo-generation counts lack a clear bounded schema. Demo lab data is written to `clinical_data['lab_values']` while normal visits use `Visit.lab_values`.

Recommendation: preserve user text as text in spreadsheet output, reject invalid column selections, and map export fields to the canonical storage schema. Validate all settings before one atomic save, bound values/counts, and make demo data use the same model contract as real data.

## Earlier implementation fixes present in this checkout

These are implementation changes from the previous pass, not unresolved suggestions:

- Rescheduling parses string times and rejects timezone-bearing/invalid time input.
- Reopening cancelled/no-show appointments rechecks availability, including ordinary updates and transition actions.
- Completed appointments cannot be moved.
- Appointment slot generation rejects zero, negative, boolean, oversized, and noninteger durations.
- Appointment reminder flags are read-only and excluded from service assignment.
- Appointment creation checks patient scope and prevents doctors booking on another doctor's schedule; invoice creation checks patient scope.
- Invoice amounts reject non-finite decimals; missing/archived supplied visits are rejected; issuance revalidates due dates against its effective issue date.
- Invoice/task deletion reloads and locks current state before enforcing lifecycle rules.
- User permissions recognize active superusers, reject inactive users, and clear Django's group/direct caches too.
- User creation is atomic; last-active-admin protection applies to demotion/deactivation using evaluated row locks in stable order.
- Task reassignment checks the actor, and reorder input rejects invalid/duplicate identifiers.
- Patient name changes using `update_fields` update normalized search text; doctor-object eligibility is checked; default admission date uses clinic-local date.
- Custom offset pagination clamps negative offsets and invalid limits.

## Suggested model design before the fresh database

| Model/change | Purpose and suggested minimum fields |
| --- | --- |
| `VisitRevision` | Visit, revision number, immutable clinical snapshot, author, signer, signed timestamp, amendment reason, previous revision. Unique `(visit, revision_number)`. |
| `IssuedDocument` | Document type, finalized visit revision, generated actor/time, immutable patient/clinician/clinic snapshot, template identifier, content checksum, optional stored PDF and signature/stamp. Append-only. |
| Clinical row snapshots | Snapshot diagnosis code/names and medication name/dose/brand/controlled status; keep nullable catalog references separately. |
| `FollowUp` | Visit/patient, due date or time, status, outcome, assigned clinician, completed actor/time, version. Distinguish contact outcome from closure. |
| `InvoiceLine` | Invoice, description/service snapshot, quantity, unit price, discount/tax policy, computed line amount. Server-derived invoice totals. |
| `Payment` (if needed) | Invoice, amount, currency, method, paid time, actor, reference, reversal relationship. Omit if only a single full payment is a firm requirement. |
| `WorkflowEvent` | Resource, from/to status, reason, actor, time, resource version. Use for explainable lifecycle history; avoid duplicating full clinical data here. |
| `IdempotencyOperation` | User, key, method, route, request digest, processing/completed state, result reference/response, expiry. Unique scoped key. |
| Archive metadata | Archived actor/time/reason and version; separate from irreversible identity removal. Active/deleted consistency constraint where applicable. |
| Database invariants | Enumerated lifecycle checks, version >= 1, required signing/payment timestamps for corresponding states, validated numeric bounds, and deliberate deletion protections. Existing invoice/range/task constraints are a useful starting point. |

Do not split every JSON field into its own model automatically. Keep variable clinical narrative/scale definitions as validated, bounded JSON snapshots; use relational rows for independently queried, scheduled, paid, or audited entities. Keep year-only DOB if that is the information the clinic actually collects; do not fabricate a full birth date.

## Decisions worth making explicitly

- Does a doctor retain access to visits they authored after patient reassignment? What does care-team membership grant?
- Which clinical data may receptionists see? Current defaults grant visit viewing and creation.
- Is an amendment an editable working copy of the last signed revision, and which revision may be issued while that copy is open?
- Are pending labs allowed on a finalized visit, and how are later results attached without rewriting signed history?
- Are follow-ups tracked as actual clinical contact, administrative reminders, or both?
- Are invoices itemized, single-currency, and paid once, or do partial payments/refunds need to exist?
- Does archived history remain accessible to the original care team, current care team, administrators, or some combination?
- Is recovery intended to reproduce an entire installation, or import selected clinical records into another installation?

## Verification performed and limitations

- Parsed Python syntax for 160 backend source files, excluding migration and test-suite paths.
- Temporary isolated probes passed overlap/adjacent-slot checks, invalid-duration guards, reopened-booking conflict checks, string-time rescheduling, completed-appointment guards, invoice arithmetic/non-finite rejection, and permission/cache-clearing guards.
- Temporary isolated probes reproduced the JSON-signature mismatch, null lab completeness bypass, NaN/off-step scale acceptance, selection of a retired scale for a new response, and stale cache publication mechanism.
- Persistence/query dependencies in those probes were stubbed. They do not establish cross-role HTTP behavior, transactional correctness on PostgreSQL, SQLite concurrency behavior, document rendering, or end-to-end backup recovery.
- The environment lacks DRF, phonenumbers, pandas, python-magic, openpyxl, Faker, and python-dotenv. Full application/API verification was therefore unavailable; dependencies were not installed or modified.
- No project database was opened or changed. No migration files or test-suite files were read or created. No build/compilation/packaging tasks were run.
