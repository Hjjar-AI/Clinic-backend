# Backend models and logic review

Reviewed: 2026-10-07.

**Historical review; fixes implemented.** See [implementation details, decisions, and verification](backend-fixes-implementation.md). Limitations below concern this review, not later fixes.

Scope: models, services, serializers, views, permissions, audit, reporting, imports, reminders, backup/restore.

Report-only pass: no migration/test-suite access, builds/packaging/compilation, or dependency/version changes. Earlier implementation fixes listed below were already in the checkout/Git baseline.

## Assessment and recommended order

Strengths: service layer, explicit lifecycles, optimistic versions, decimal billing, scale snapshots, soft deletion. Prioritize recovery/signed history; a fresh database simplifies structural changes but does not fix logic defects.

1. Repair backup/restore completeness, signatures, and validation.
2. Preserve clinical revisions and issued documents; strengthen signing and nested-input validation.
3. Unify access rules and fix authentication transaction behavior.
4. Make mutations, reminders, and cache publication consistent.
5. Improve invoice structure, report definitions, and import previews.

P0: data loss/recovery; P1: integrity/access; P2: correctness/maintainability. Reproductions used isolated stubbed persistence/dependencies, not full HTTP/production DB. Others are source-traced; confirm concurrency on the intended database.

## Findings and concrete recommendations

### 1. P0 — A newly generated JSON backup fails signature verification

Evidence: [creator](../apps/backup/backup_creator.py#L137), [verifier](../apps/backup/backup_restore.py#L62).

- **Issue:** Creator signs inner serialized `data`, returning `signature`/`data`; verifier HMACs the whole envelope. An empty-backup probe reproduced `Backup signature verification failed`.
- **Recommendation:** Share canonical signing/serialization bytes across JSON/ZIP; reject missing/invalid signatures and define legacy interpretation without trusting unsigned archives.

### 2. P0 — “Full” restore does not restore the full backup and deletes additional records

Evidence: [restore implementation](../apps/backup/backup_restore.py#L128), [backup contents](../apps/backup/backup_creator.py#L188), [execute endpoint](../apps/backup/views.py#L84).

- **Issue:** `backup.json` reconstructs patients, visits, diagnoses, medications, attachments, scales, but ignores `clinic.db`/media. Patient cascades delete appointments, invoices, documents, care teams, prescription signatures without rebuilding them. Clean recovery restores file paths without bytes; preview mentions only four replacement categories.
- **Recommendation:** Separate full disaster recovery from selective logical import. Full recovery restores all supported entities/media consistently; selective import preserves unrelated records or previews their removal. Partial reconstruction must not report full success.

### 3. P1 — Backup coverage, authenticity, and compatibility checks are incomplete

Evidence: [JSON selection](../apps/backup/backup_creator.py#L137), [patient serialization](../apps/backup/backup_creator.py#L20), [preview](../apps/backup/backup_restore.py#L87).

- **Issue:** Backups omit archived patients/visits/attachments, retired catalogs, `Visit.lab_values`; timestamps serialize but do not restore. Unknown DOB becomes `1998`, unknown statuses become finalized; execution ignores unsupported versions. ZIP authenticates only `backup.json`, excluding database/manifest/media.
- **Recommendation:** Inventory all entities/history/labs/original IDs/timestamps; preserve unknown DOB, reject unknown states. Before mutation validate format/shape/lengths/references/expanded size/checksums; sign every member via manifest. Use consistent database snapshots: post-WAL-checkpoint copying races with writes.

### 4. P1 — Clinical amendments overwrite signed history

Evidence: [visit update](../apps/visits/services.py#L109), [nested replacements](../apps/visits/models.py#L184), [audited fields](../core/signals.py#L24).

- **Issue:** `final → amended` overwrites the visit and replaces diagnoses/medications/scales. Audit retains workflow/risk/version, excluding complaint/history/treatment/notes/clinical JSON/labs/full nested data; previous clinical content is unrecoverable.
- **Recommendation:** Snapshot immutable `VisitRevision` at finalization/amendment completion: scalars, diagnoses, medications, labs, scale definitions/answers, author/signer/date/reason. Separate optimistic `version` from history revision number; documents reference finalized revisions.

### 5. P1 — Signing and document issuance need a stronger contract

Evidence: [visit serializer](../apps/visits/serializers.py#L39), [visit transitions](../apps/visits/services.py#L177), [prescription service](../apps/prescriptions/services.py#L22), [signature storage](../apps/prescriptions/services.py#L122), [referrals](../apps/referrals/views.py#L13).

- **Issue:** Clients choose another active user's `signed_by_id`/manual date; finalization does not derive signer/time from actor. Any non-draft visit—including amendments—can issue. Per-user/visit signatures overwrite; exact PDF/complete issuance history is absent. GET referral reasons enter browser/proxy logs.
- **Recommendation:** Authorize signing and set signer/time server-side. Issue from specified finalized revisions; append-only `IssuedDocument` stores actor/revision/snapshot/checksum/time/signature/stamp/optional PDF. Use POST body for referral reason.

### 6. P1 — Nested visit input is not validated as structured clinical data

Evidence: [nested serializer fields](../apps/visits/serializers.py#L41), [diagnosis/medication setters](../apps/visits/models.py#L184), [clinical JSON use](../apps/exports/base.py#L67).

- **Issue:** Generic `ListField`s lack child serializers; setters assume dictionaries and trust IDs/lengths, causing attribute/constraint errors. `clinical_data` permits list/string although exports call `.get()`.
- **Recommendation:** Typed serializers/normalizers must validate counts, objects, eligible references, lengths, custom/catalog rules before replacing relations. Require bounded clinical JSON objects; share validation with imports/restore.

### 7. P1 — Null clinical fields can pass completeness validation

Evidence: [lab normalizer](../apps/visits/lab_validation.py#L9), [finalization checks](../apps/visits/services.py#L35).

- **Issue:** `str(value)` converts JSON `null` to nonempty `"None"`; lab finalization accepts null name/value with date/status (reproduced). Medication completeness uses the same pattern.
- **Recommendation:** Treat null as missing, enforce primitive types, reject oversize values rather than truncate. Distinguish pending labs from completed results; never fabricate finalization values.

### 8. P1 — Scale validation accepts invalid scores and new uses of retired definitions

Evidence: [response normalizer](../apps/visits/scale_validation.py#L6), [field validation](../apps/clinical/serializers.py#L41).

- **Issue:** `float('NaN')` evades `< minimum`/`> maximum` and poisons totals; slider steps are unchecked; `all_objects` allows new retired-scale responses (all reproduced). Defaulted missing answers appear completed. Missing field default is assumed minimum but omitted from `attrs`, leaving model zero and possibly violating range.
- **Recommendation:** Require finite/on-step scores, persist validated defaults, restrict retired definitions to existing historical snapshots, represent unanswered items explicitly, and enforce completion before scoring/finalization.

### 9. P1 — Historical diagnoses and medications can change with catalog edits

Evidence: [visit getters](../apps/visits/models.py#L149), [setters](../apps/visits/models.py#L184), [catalog updates](../apps/clinical/services.py#L27).

- **Issue:** Blank custom/snapshot text falls back to mutable catalog labels; controlled status always uses current medication catalog. Catalog edits change finalized history/display/classification without version increments.
- **Recommendation:** Save immutable code/name/dosage/brand/controlled snapshots on every clinical row; retain optional catalog references for search/grouping. Historical documents read snapshots.

### 10. P1 — Access policies differ between related endpoints

Evidence: [visit object permission](../core/permissions.py#L221), [visit queryset](../apps/visits/views.py#L59), [dashboard](../apps/dashboard/views.py#L13), [patient timeline](../apps/patients/views.py#L167), [care-team model](../apps/patients/models.py#L150).

- **Issue:** Object permission allows visit authors but querysets require current patient doctor, losing historical access after reassignment. Care teams grant nothing. Authentication-only dashboards expose risk/follow-ups/task descriptions despite removed permissions; patient timeline/risk require patient-view but not visit-view.
- **Recommendation:** Share `accessible_patients/visits/appointments/invoices` and object policies across lists/details/create/dashboard/exports/reminders. Explicitly decide author/care-team scope; gate sensitive dashboard sections/clinical subresources with corresponding permissions.

### 11. P1 — Failed-login counters conflict with request-wide transactions

Evidence: [login failure path](../apps/accounts/services.py#L18), [counter mutation](../apps/accounts/models.py#L103), [database settings](../config/settings/base.py#L180), [exception delegation](../core/exceptions.py#L55).

- **Issue:** With `ATOMIC_REQUESTS`, wrong-password counters increment before DRF `AuthenticationFailed`; the [official DRF handler implementation](https://github.com/encode/django-rest-framework/blob/master/rest_framework/views.py) rolls back active request transactions, potentially undoing lockout. Source-traced; HTTP reproduction lacked installed DRF.
- **Recommendation:** Exclude login from request-wide transactions; commit security updates in short transactions, durable even on failure. Dummy-hash unknown users to reduce timing differences; verify anonymous session-login CSRF.

### 12. P1 — Forced password changes and permission reporting are incomplete

Evidence: [user serializer](../apps/accounts/serializers.py#L7), [user updates](../apps/accounts/services.py#L110), [session middleware](../core/middleware.py#L88).

- **Issue:** Generic serializer accepts `force_password_change`; no backend gate limits flagged users to password/session endpoints. Password/security changes may skip version increments. Group/direct permission output disagrees with active-superuser `has_perm()`; `_apply_role_group()` rewrites existing role grants on create/role change.
- **Recommendation:** Server-control/enforce forced changes, version security updates, compute authoritative effective permissions. Seed roles explicitly; user creation must not rewrite existing group permissions. Validate permission payloads as string lists before set operations.

### 13. P1 — Follow-up completion can lose edits and inflate adherence figures

Evidence: [single/bulk completion](../apps/visits/services.py#L251), [follow-up statistics](../apps/reports/visit_statistics.py#L60).

- **Issue:** Single completion neither checks nor increments version. Bulk marks every overdue item completed without contact/actor/outcome/date; `QuerySet.update()` bypasses audit/cache signals, inflating adherence. New due dates do not reset completion.
- **Recommendation:** Distinguish completed/missed/cancelled/rescheduled/waived. Prefer linked `FollowUp` with due date/outcome/actor/time/version; meanwhile lock/version updates, reset new dates, and record bulk closure as explicit auditable outcome, not completion.

### 14. P1 — Destructive actions and archived objects do not share a version contract

Evidence: [patient removal/anonymization](../apps/patients/services.py#L167), [appointment mutations](../apps/appointments/services.py#L171), [visit mutations](../apps/visits/services.py#L109).

- **Issue:** Delete/archive/anonymize lack consistent expected versions. Mutations reload `all_objects` without active/deleted rechecks, allowing concurrent edits/transitions after archive. Dependency checks omit care teams; “use archive” references no dedicated patient action.
- **Recommendation:** Share lock/version/active-state checks across edit/transition/archive/restore/anonymize. Add explicit archive preserving readable history while blocking new clinical/financial records; recheck active parents when adding new records within the transaction.

### 15. P1 — Idempotency blocks retries without recovering the successful result

Evidence: [middleware](../core/middleware.py#L29).

- **Issue:** Boolean idempotency records return 409 after successful responses are lost; keys lack method/path/payload scope and disappear on expiry/eviction/global clearing. Mutable options/scales/templates are uncovered.
- **Recommendation:** Persist user/method/route/payload digest/state/resource/response/status; replay identical successes, reject changed payload reuse. Make important creates/issuances durable, bound key length, distinguish processing from completed operations.

### 16. P1 — Cache invalidation can publish stale data as current

Evidence: [cache utility](../core/cache_utils.py#L38), model-specific save signals, [bulk follow-up update](../apps/visits/services.py#L258).

- **Issue:** Pre-commit invalidation lets another request cache old committed data under new generation. `set_grouped_key()` selects generation at publication; isolated interleaving reproduced stale-query promotion. Bulk updates skip invalidation.
- **Recommendation:** Invalidate with `transaction.on_commit()`; capture generation before query and publish only there or discard changed-generation results. Invalidate bulk changes explicitly; protect idempotency/preview records from settings cache clears.

### 17. P2 — Appointment scheduling rules still need consistency

Evidence: [update](../apps/appointments/services.py#L171), [calendar](../apps/appointments/services.py#L340), [availability endpoint](../apps/appointments/views.py#L194).

- **Issue:** Earlier reopen/reschedule fixes exist. Cancelled/no-show edits skip availability plus duration/reminder checks; legacy `duration` affects validation without persistence. Bounds differ across model/service/API; doctor filters can fall back to unfiltered accessible results; cancellation branches differ. Time-only intervals lose cross-midnight dates.
- **Recommendation:** Normalize once/persist canonical keys; validate all requested schedules, including non-occupying ones; share bounds. Apply doctor/date/status filters after access scope; use datetimes. Document working hours/past bookings/arrived edits. Verify target-database races: SQLite lacks sentinel row locks.

### 18. P2 — Invoice structure is too limited for a durable billing record

Evidence: [invoice model](../apps/billing/models.py#L7), [creation/update/transition](../apps/billing/services.py#L51).

- **Issue:** Supplied total/tax/discount lack itemization/currency/payment records/paid actor/time. Free-text method must precede issue because edits then lock. Issue reads mutable patient identity; creation/update silently ignore status.
- **Recommendation:** Add `InvoiceLine`, server totals, explicit currency/rounding. Support payments only if partial/multiple required; otherwise validate method and record actor/time through pay action. Snapshot billed patient/clinic on issue; reject/read-only status explicitly; correct issued finance by cancellation/credit, not editing.

### 19. P2 — Physical deletion can remove clinical and financial history

Evidence: [appointment patient/doctor FKs](../apps/appointments/models.py#L16), [invoice patient FK](../apps/billing/models.py#L15), [signature FKs](../apps/prescriptions/models.py#L5).

- **Issue:** History-bearing relationships use `CASCADE`. Soft-delete endpoints do not prevent restore/management/future-admin physical parent deletion from erasing history; current restore already triggers this.
- **Recommendation:** Use `PROTECT` for clinical/financial parents; nullable `SET_NULL` only with sufficient immutable identities. Cascade only intended dependents; coordinate relationship changes with restore redesign.

### 20. P2 — Archival and anonymization need separate meanings

Evidence: [anonymize](../apps/patients/services.py#L185), [audit contents](../core/signals.py#L24).

- **Issue:** Anonymization rewrites identity/archives, clears doctor/creator/family history/important notes, but retains identity-bearing narratives/documents/attachment names/audit. Clearing clinicians changes historical access; this is not complete anonymization.
- **Recommendation:** Separate archive, reversible identity restriction/pseudonymization, irreversible erasure. Define retained clinical data/authorized access; comprehensive anonymization must scope all identity resources and audit purpose/result without copying removed identity.

### 21. P2 — Reports use inconsistent periods and mutable grouping labels

Evidence: [monthly visits](../apps/reports/visit_statistics.py#L18), [diagnoses/medications](../apps/reports/visit_statistics.py#L38), [patient acquisition](../apps/reports/patient_statistics.py#L27), [report view](../apps/reports/views.py#L19).

- **Issue:** Monthly series imposes rolling “today minus N months” even on old explicit ranges; omits zero months. Visit average ignores period. Diagnosis/medication grouping splits catalog/custom concepts and prefers mutable catalog labels unlike visits. Any historic high-risk visit counts as current; summary month/year parsing is unsafe.
- **Recommendation:** Make explicit periods authoritative, fill empty months, define each KPI. Group stable concept/catalog IDs or normalized custom keys with historical labels. Define latest-assessment risk or label “ever recorded high risk”; validate month/year and separate all-time/period metrics.

### 22. P2 — Local dates and reminder windows are inconsistent

Evidence: [appointment job](../core/management/commands/send_appointment_reminders.py#L14), [task job](../core/management/commands/send_task_reminders.py#L14), dashboard/report services.

- **Issue:** `timezone.now().date()`/host `datetime.now()` replace clinic-local dates. Hourly appointment windows miss local midnight; exact-day reminders miss outages. Flags skip `updated_at`; auditing records unchanged business fields.
- **Recommendation:** Use clinic-local dates/aware datetime intervals, full-window queries, defined catch-up, occurrence-specific dedupe. Update bookkeeping timestamps; suppress empty clinical audit edits or use separate delivery events.

### 23. P2 — Imports can disagree with previews and silently discard valid records

Evidence: [patient preview/import](../apps/import_export/services.py#L57), [diagnosis preview/import](../apps/import_export/services.py#L162), [medication mapping](../apps/import_export/views.py#L246).

- **Issue:** Patient import skips shared phones despite valid family sharing, truncates fields, diverges from normal validation. Diagnosis preview accepts two columns but execution requires three. Medication preview is raw/unbound to mapping/overwrite; retirement precedes validation. Weak row errors and empty-file first-row indexing risk losing valid catalogs.
- **Recommendation:** Share validated preview/execution parsers; national ID is strong duplicate, phone a warning. Bind digest/mapping/merge policy/doctor; require valid records and preview retirements before replacement. Use savepoints, bounded typed rows, stable outcomes, safe empty-file handling.

### 24. P2 — Catalog writes ignore accepted fields and bypass concurrency controls

Evidence: [diagnosis service](../apps/clinical/services.py#L11), [medication service](../apps/clinical/services.py#L46), [catalog serializers](../apps/clinical/serializers.py#L11).

- **Issue:** Diagnosis writes ignore ordering/activity; medication create ignores `is_controlled`/ordering/activity, update has weaker duplicate handling. Catalogs/scales/templates/settings lack versions; serializer/service persistence differs.
- **Recommendation:** Persist or reject every accepted field; dedicated retire/reactivate actions and canonical services. Version concurrent edits, preserve definition snapshots, optionally constrain normalized medication identity.

### 25. P2 — Multiple write paths bypass the service rules

Evidence: [visit serializer create/update](../apps/visits/serializers.py#L96), [service lifecycle](../apps/visits/services.py#L50), [task model reactivation](../apps/tasks/models.py#L90).

- **Issue:** Visit serializer writes rows/nested data without service lifecycle/finalization/optimistic locks. Current views use services, but `serializer.save()` elsewhere bypasses rules; direct helpers/demo/restore have separate behavior.
- **Recommendation:** Use serializers as validation/representation adapters and canonical services for ordinary clinical writes. Keep separately validated exceptional restore/seed interfaces; enforce crucial status/version/range invariants in database constraints.

### 26. P2 — File and document operations are not covered by clinical immutability

Evidence: [attachments endpoint](../apps/visits/views.py#L210), [attachment deletion](../apps/visits/views.py#L241), [file storage](../core/file_utils.py#L58).

- **Issue:** Final/locked visits permit attachment add/archive without revision policy. Bytes precede database rows, orphaning files on transaction failure. Size/MIME partly trust client metadata; logical recovery omits document relationships.
- **Recommendation:** Define signed-revision attachments versus append-only administrative documents; audit actor/reason for additions/retirements. Clean failed storage/reconcile orphans, persist verified metadata/checksums, and recover document inventory/media.

### 27. P2 — Export and settings paths need small correctness improvements

Evidence: [CSV/Excel exports](../apps/exports/patient_export.py#L14), [report export](../apps/exports/report_export.py#L9), [settings update](../apps/settings/services.py#L75), [PDF data](../apps/exports/base.py#L134).

- **Issue:** Spreadsheet exports allow formula-leading untrusted text; unsupported CSV columns can silently empty output. Formulation/MSE read nonexistent `Visit` attributes instead of clinical JSON. Sequential settings writes partially persist before 400; strings/demo counts are unbounded. Demo labs use `clinical_data['lab_values']` instead of `Visit.lab_values`.
- **Recommendation:** Keep spreadsheet text literal, reject invalid columns, map canonical clinical storage. Validate bounded settings/counts before atomic save; demo data must follow real model contracts.


## Earlier implementation fixes present in this checkout

Already implemented in the earlier pass:

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

Keep variable narratives/scale definitions as validated bounded JSON snapshots; relational rows suit independently queried/scheduled/paid/audited entities. Do not automatically model every JSON field. Retain year-only DOB when that is collected; never fabricate full dates.

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
- Stubbed persistence/queries do not verify cross-role HTTP, PostgreSQL transactions, SQLite concurrency, document rendering, or end-to-end recovery.
- Missing DRF, phonenumbers, pandas, python-magic, openpyxl, Faker, python-dotenv prevented full app/API checks; dependencies remained uninstalled/unchanged.
- No project database access/changes, migration/test-suite reads/creation, builds/compilation/packaging.
