# Backend models and cross-model logic review

Reviewed and expanded 2026-10-12. Consolidated review only; no production implementation changed. Includes the original R1–R9 and expanded R10–R29; this file is the single review record.

## Scope and evidence

Read the backend/frontend instructions, current/completed records, implementation and patient contracts, and recovery/deployment notes. Inspected all application model modules and shared base models, plus model-related services, serializers, views, signals, routes, validators, exports and operational jobs. Checked frontend API/version/retry handling and feature services against the affected backend contracts. Focus was ownership, state transitions, version boundaries, access, historical consistency, failure recovery and data fidelity. This covers the model-related areas below; it is not exhaustive execution coverage of every input, endpoint or deployment.

No migrations or test-suite files inspected; no test suite, builds, compilation, schema changes or clinic-data access performed. Existing `.env.example` modification was preserved. AST parsing passed for 173 production Python files, excluding migrations/test suites and migration-performing startup commands; this does not establish runtime correctness. Scale-step arithmetic was checked in a standalone Python calculation without importing Django settings. An openpyxl probe was unavailable, so spreadsheet findings remain source-only. Concurrent/failure schedules below are source-derived risks, not reproduced PostgreSQL/cache failures. Historical verification records were not treated as verification of these findings.

## Area-by-area coverage

| Area / main production sources | Relationships and logic reviewed | Findings / outcome |
| --- | --- | --- |
| Shared models: `core/models.py`, `constraints.py`, `mutation.py`, `lifecycle.py` | Soft deletion, default/base managers, permanent history, version types, allowed transitions, historical actor FKs | Retain current architecture; R2/R3/R11/R28 and design suggestions |
| Patient profile: `patients/models.py`, `services.py`, `serializers.py`, `completeness.py` | Identity normalization, year-only birth, number permanence, verification, correction reasons, summaries, completeness | R5/R19/R20; nullable-age and history suggestions |
| Longitudinal records: `patients/record_models.py`, `record_services.py`, `record_views.py` | Identifiers, contacts, representatives, allergies, medications, follow-up relations, retirement, patient versions and scope | R3/R4/R19/R20; policy choices labelled |
| Care teams and reconciliation: `patients/merge_services.py`, `core/access.py` | Dated access, source/survivor lock order, preview digest, moved records, active identifier/contact conflicts, unchanged immutable history | R6/R8/R19; future-dated membership/access-broadening suggestions |
| Visits: `visits/models.py`, `services.py`, `serializers.py`, validators/views | Draft/final/amended/locked, signing authority, revisions, nested replacement, labs, scales, follow-up bridge, attachments | R1–R4/R7–R9/R17/R18 |
| Catalogs/scales/templates: `clinical/` models/services/serializers/views | Retirement/reactivation, normalized medication identity, snapshot labels/controlled flags, fields/defaults/steps, bounded template JSON | R17/R18/R27; import/export fidelity limitation |
| Scheduling: `appointments/` models/services/serializers/views | Doctor and patient eligibility, occupancy, intervals, rescheduling, reopen/cancel/archive, scope, availability/calendar/next | R15/R16/R21/R22; concurrent booking remains unverified |
| Billing: `billing/` models/services/serializers/views | Lines/totals, rounding, patient/visit consistency, issue identity snapshot, payment metadata, immutable-after-issue service policy | R13; snapshot/currency/constraint suggestions |
| Accounts/security: `accounts/` and relevant middleware | Password gate, sessions/CSRF, lockout counters, active admin protection, roles/groups/direct grants, versioned account edits, recovery command | R8/R10/R24; recovery/login race suggestions |
| Tasks: `tasks/` models/services/serializers/views | Assignment, scope, completion/cancellation/reopen metadata, reorder locking, reminders | R21; reorder/access-race suggestions |
| Notifications/jobs: `notifications/`, reminder/scheduler commands | Recipient scope, read/delete ownership, dedupe keys, retirement, catch-up windows, timestamps and retention | R21/R22; message/recipient/retention suggestions |
| Prescription/referral: `prescriptions/`, `referrals/` | Approved revision requirement, previews, signature/stamp input, exact issued bytes/checksum, final write checks | R9/R10/R28; historical snapshot safeguards retained |
| Reports/dashboard: `reports/`, `dashboard/` | Patient/visit/task/appointment scopes, explicit periods, denominators, latest risk, physician attribution, permission-filtered cards | R1/R6/R7/R13; R16 consistency and metric suggestions |
| Clinical exports: `exports/`, `core/spreadsheets.py`, PDF context | Patient/visit/report/catalog CSV/XLSX, current versus signed facts, headers, text cells, PDF/Word data ownership | R14/R20; historical-output and round-trip suggestions |
| Imports: `import_export/`, upload validators | CSV/XLSX parsing, normalization, row outcomes, duplicate warnings, mapping/file/policy binding, replacement transactions | R27; current-state preview and field-fidelity suggestions |
| Full/catalog recovery: `backup/` | Signed inventory/media, field/reference validation, raw recovery bypass, IDs/timestamps, media compensation, safety copy, sessions and audit actor | R12/R24–R27; semantic validation/retention suggestions |
| Cache/audit: `cache_utils.py`, `signals.py`, feature signals | After-commit generations, settings publication, audit field coverage/privacy, bulk operations and request actor | R11/R24/R26; stronger clinical correction history suggestion |
| Files and hosting: file/upload/image/PDF helpers, `config/urls.py` | MIME/macro checks, bounded uploads, UUID paths/checksums, protected downloads, orphan reconciliation, debug media routing | R23; file/outer-rollback and scanner verification suggestions |
| Settings/system/configuration | Atomic settings version, completeness configuration, timer/default contracts, health/cache clear, external DB/cache profiles | R22/R25/R26; supported-runtime/DB-profile limits remain |
| Frontend contract consumers | Shared API client's observed versions, `If-Match`, idempotency/retry bookkeeping; patient/visit/scale/billing/import/recovery/prescription/referral/task services | R9/R12/R28; no frontend implementation or rendered verification |

The backup/import/report apps without their own models were still reviewed: they mutate, serialize or aggregate other apps' models. A row without a new defect is coverage, not a runtime guarantee.

## Priority index

| Priority | Entries | Reason |
| --- | --- | --- |
| First | R1/R2/R8/R10/R11/R12/R14/R25/R26/R29 | Clinical authority/history, authorization, replay after failure, file/DB recovery integrity |
| Next | R3/R5/R6/R7/R9/R13/R15/R16/R19/R20/R21/R24/R27/R28 | Cross-model consistency, attribution, scope, evidence and freshness |
| Bounded edge/configuration cases | R4/R17/R18/R22/R23 | Completion policy, oversized scales, numeric extremes, development timer/media behavior |

Priorities express impact, not proof of runtime reproduction. R4 includes an explicit policy choice; R8/R9/R25/R26/R27/R29 require concurrent or injected-failure verification. R23 applies to network-accessible DEBUG deployments, not the documented production topology.

## Model inventory and ownership

| Models | Intended fact owner / boundary |
| --- | --- |
| `Patient`, `PatientIdentifier`, `PatientContact`, `PatientRepresentative` | Current identity/contact/representation facts; explicit verification and correction history; patient parent version |
| `PatientCareTeam` | Dated assignment/access, independent of compatibility `Patient.doctor` and retained historical-author scope |
| `PatientAllergy`, `PatientMedication` | Longitudinal clinical facts and source/provenance; clinical action permission |
| `PatientFollowUp` | Action lifecycle and evidence; legacy encounter bridge needs a clearer single owner |
| `PatientCorrection`, `PatientMerge`, `PatientDuplicateReview` | Immutable corrections/merge manifests; mutable duplicate-review decisions with ordered pairs |
| `PatientDocument`, `VisitAttachment` | Stored clinical file identity/provenance/checksum; scoped download and retained media |
| `Visit`, `VisitDiagnosis`, `VisitMedication`, `VisitScaleResponse` | Working encounter facts and saved catalog/scale definitions; guarded replacement while editable |
| `VisitRevision` | Approved immutable clinical snapshot, signer/time/reason and identity at signing |
| `IssuedDocument`, `PrescriptionSignature` | Exact immutable issued artifact versus auxiliary signature record; revision linkage and issuance actor |
| `DiagnosisOption`, `MedicationOption`, `ClinicalScale`, `ScaleField`, `ClinicalNoteTemplate` | Current reusable definitions; retirement preserves encounter snapshots; scale edits use parent versions |
| `Appointment` | Doctor schedule occupancy and attendance lifecycle; patient reference does not imply completed clinical encounter |
| `Invoice`, `InvoiceLine` | Invoice/line monetary facts, issue identity, currency and full-payment lifecycle; no inferred partial-payment/refund system |
| `User`, `UserTask`, `Notification`, `ClinicSetting` | Principal/security state, assigned work, per-recipient delivery state and versioned clinic configuration |
| `AuditLog`, `IdempotencyOperation` | Bounded audit metadata and durable operation identity/result; recovery and after-commit failure boundaries need strengthening |
| Abstract/shared bases | `TimeStampedModel`, `SoftDeleteModel`, `ImmutableModel`, `PatientRecord`, `ClinicalPatientRecord`; managers/querysets provide application guards |

Reports, imports, recovery, referrals, dashboard, exports and system modules have no independent clinical fact model; their consistency depends on consuming/mutating the owners above.

## Findings: source-confirmed behavior and explicit policy gaps

### R1 — High: unsigned amendments change the high-risk patient report

Location: `apps/reports/visit_statistics.py:86–92`; `apps/visits/services.py:128–184`.

The latest-assessment query excludes only `draft`. An `amended` visit contains editable, unsigned replacement fields, while its last approved facts remain in `VisitRevision`. Open an amendment to a signed High assessment and save Low without re-signing: the patient disappears from the high-risk list. Conversely an unsigned High amendment can enter it. Document issuance correctly blocks this state, but the risk report does not use the same historical boundary.

Correction: define whether this report represents approved assessments or working assessments. For approved results, select the latest signed revision, including the last approved revision of an encounter currently under amendment. Simply excluding amended encounters loses their existing approved assessment. If working assessments are intentional, return their approval state explicitly and preserve approved risk visibility separately.

### R2 — High: visit follow-up outcomes can overwrite terminal history

Location: `apps/visits/services.py:210–224`; compare `apps/patients/record_services.py:119–125`.

`complete_follow_up` checks the due date and supplied outcome but not the existing outcome. A completed follow-up can subsequently become missed, cancelled or waived; actor/time are overwritten and the bridge row receives the replacement. Even repeating completed with the new current version changes completion metadata. The standalone follow-up service explicitly rejects changing a terminal outcome. Expected versions prevent stale writes but do not enforce a lifecycle.

Correction: share one follow-up transition policy. Make repeated identical outcomes a no-op; reject terminal replacement through the ordinary action, or introduce an explicit reason-bearing correction retaining previous outcome/actor/time.

### R3 — Medium: legacy follow-up edits leave conflicting fields

Location: `apps/patients/record_services.py:127–131`; `apps/patients/follow_up_services.py:17–23`; `apps/visits/services.py:141–148`.

The legacy guard blocks due-date/source/status changes but allows `completed_visit`, title, notes and outcome reason. Attach a completed visit to a completed legacy action, then change its follow-up date through an amendment: the visit service resets the outcome to pending, and the bridge sets the action to pending without clearing `completed_visit`. Its old outcome reason also survives because the bridge only assigns that field for nonpending states. The saved action can therefore say pending while referencing a completed visit and retaining a completed outcome reason. The model has no constraint preventing this combination.

Correction: clearly separate visit-owned bridge fields from independently editable action fields. Reset completion linkage/reason when scheduling resets, or create a new action and retire the previous occurrence to preserve history. Apply the same invariants during bridge synchronization as during ordinary record writes.

### R4 — Medium: completion evidence may be an unsigned draft or archived visit

Location: `apps/patients/record_services.py:98–106,129–132`.

Relation validation in the service uses `_base_manager` and checks patient ownership. `completed_visit` is only required to accompany status completed; the service does not require an active, signed final/locked encounter. The generated API serializer limits selection through the default active manager, so active drafts are an API concern; archived references are a direct-service boundary concern. Ownership checks are useful but insufficient to define what completion evidence means.

Correction: distinguish retaining an existing historical reference from assigning new evidence. If completed-visit means an approved completed encounter, validate active/approved state when attaching it and consider linking its signed revision. If drafts are deliberately valid, document that meaning and expose their state to consumers.

### R5 — Medium: nonclinical editors can reset clinical summaries

Location: `apps/patients/services.py:104–118`; writable fields in `apps/patients/serializers.py:39`.

The clinical permission check exempts the value `unknown`. A scoped editor with `edit_patient` but without `edit_visit` can change a previously recorded allergy/medication summary to unknown. Positive longitudinal records remain, since the consistency check only rejects `none_known`. Signing subsequently snapshots that unknown summary together with the positive records. This bypasses the protection applied to other clinical assertions.

Correction: require clinical permission for actual changes to any clinical-summary value, including unknown. Permit unchanged echoed values so ordinary demographic forms continue working. Define whether unknown is allowed alongside active positive records, and validate that policy consistently.

### R6 — Medium: doctor reports attribute work using compatibility ownership

Location: `apps/reports/patient_statistics.py:52–63`; `apps/reports/doctor_performance.py:5–22`; compare `docs/contracts/patients.md:22`.

The patient contract makes care-team membership authoritative and `Patient.doctor` compatibility display/create input only. Both reports still group patients by that field. Doctor performance also counts all visits on those patients against the compatibility doctor instead of their actual author. Assign a patient to doctor A and have team doctor B author visits: A receives B's visit count. Ending A's membership or adding B does not correct the attribution. Patients created using care-team IDs without a legacy doctor disappear from these groupings.

Correction: define separate metrics for currently assigned patients, patients treated in the period and visits authored/signed. Use dated care-team membership for assignment and author/signer for encounter work. Group by user ID as well as display name to avoid combining distinct doctors sharing names. Do not substitute the current team for historical encounter authorship.

### R7 — Medium: overdue bulk closure includes archived patients

Location: `apps/visits/services.py:227–251`; `core/access.py:27–29`; compare `apps/patients/follow_up_services.py:27–32`.

Standalone actions are selected through active `accessible_patients`, but legacy visit follow-ups are selected through `accessible_visits`, which intentionally includes archived-patient history. Thus archiving a patient removes their standalone actions from bulk closure but leaves their visit follow-ups eligible for mutation. This differs from the active follow-up register and reporting scope.

Correction: share one explicit operational follow-up scope for the register, reports and bulk action. Preserve archived history access separately. If closing archived follow-ups is intended, make that an explicit scope rather than an implicit side effect of history access.

## Findings: concurrency gaps inferred from source

### R8 — High: access revocation is not rechecked after visit locking

Location: `apps/visits/views.py:128–158`; `apps/visits/services.py:19–27,110–132,162–184`; compare `apps/patients/record_services.py:73–75`.

Visit scope is checked before entering the mutation service. The service acquires the patient lock but does not re-evaluate scope afterwards. A team-only doctor passes the endpoint access check; another transaction removes their membership and commits; the doctor subsequently acquires the patient lock and edits/signs the encounter. Membership removal bumps the patient version, not the visit version, so the supplied encounter version can still pass. PatientRecordService already demonstrates the stronger pattern by checking access after the patient lock.

Correction: recheck required action permission and current scope against the locked parent before encounter mutations and signing. Preserve the documented independent historical-author access. Apply the same reasoning to other scope-dependent services; this finding is specifically traced for visits, not a claim that every endpoint is exploitable.

### R9 — Medium: prescription patient-version binding ends before issuance

Location: `apps/prescriptions/services.py:78–95`; `apps/prescriptions/views.py:51–57`; `apps/prescriptions/issuance.py:18–29`.

Preview retrieval validates the patient version before PDF generation. Final persistence locks and validates the visit/revision only. A patient edit can commit during rendering without changing the visit version, and issuance still succeeds against the old preview. Signed identity snapshots remain intentionally historical, so this is a broken preview freshness contract, not evidence that immutable clinical history itself is corrupted.

Correction: use the patient-before-visit lock order at final issuance and compare the freshly loaded patient version for snapshots that bind it. Recheck scope there too. Keep exact issued bytes and revision identity unchanged. Alternatively deliberately remove patient-version binding if the product contract requires only signed-revision freshness, and update preview semantics consistently.

## Expanded findings: source-confirmed behavior

### R10 — High: idempotent replay bypasses current endpoint authorization

Location: `core/middleware.py:89–100`; `apps/patients/services.py:333–349`; prescription generation and other covered mutation endpoints.

A completed operation is returned directly from middleware; the view's current action and object permissions never run. For example, a team-only doctor can generate a prescription on another author's encounter, lose their care-team membership, then replay the same request/key and receive the stored PDF although the endpoint would now deny access. Care-team removal does not revoke the session. This is a sequential authorization gap, separate from R8's concurrent mutation gap. The response may already have been seen originally, but replay still treats the operation key as authorization to retrieve protected bytes after scope removal.

Correction: separate authorization to execute from authorization to retrieve a stored result. Recheck the current action/resource scope before returning sensitive replay bodies; if replay must remain available after revocation, define a restricted operation receipt rather than implicitly granting access to the original clinical payload.

### R11 — High: crashed processing operations remain stuck; expiry is unused

Location: `core/models.py:108–121`; `core/middleware.py:84–95,112–123`; production references to `IdempotencyOperation`/`expires_at`.

The processing row is committed before the mutation transaction. A killed worker after reserving a key leaves state processing; subsequent requests return request-in-progress forever. There is no lease/heartbeat/reconciliation path, and `expires_at` is never checked or swept in production source. Completed response bodies also accumulate indefinitely, including backup/PDF bytes. Exception cleanup handles ordinary raised exceptions but cannot handle process termination.

Correction: define operation states and a crash-recovery protocol. Preserve transactionally recorded completion for ordinary writes, safely recover abandoned reservations, and give independently committed backup/recovery actions an explicit completion receipt. Add bounded retention for completed operations and responses. Do not blindly delete a stale processing row and rerun an independently committed destructive action.

### R12 — High: full restore deletes the idempotency operation tracking itself

Location: `apps/backup/backup_restore.py:227–238`; `apps/backup/views.py:128–138`; `core/middleware.py:104–117`.

Full recovery raw-deletes all idempotency rows, including the processing row for the restore request. The middleware's later completed-response update matches no row and silently records nothing. The preview token is deleted and sessions are revoked. If the success response is lost, the client cannot retrieve the committed operation's result using its key; after relogin it encounters an invalid preview instead. Catalog-only restore does not execute this deletion.

Correction: keep destructive-operation receipts outside the replaced application inventory, with an explicit initiating-principal/install identity and secure replay rules. Account for the restored auth namespace and preserve a recoverable success receipt before consuming the preview. Merely keeping the old FK-backed row can misattribute it to a different restored user; coordinate with R24.

### R13 — Medium: revenue reconciliation adds different currencies together

Location: `apps/reports/services.py:30–52`; `apps/billing/models.py:54`; `apps/billing/services.py:65–69`.

Invoices explicitly allow independent currency codes. Reconciliation sums every paid invoice's `final_amount` into a single currency-less `paid_amount`. A paid SYP invoice and a paid USD invoice are therefore added as if their units matched. Paid-only filtering is correct; the aggregation unit is not.

Correction: aggregate paid totals by currency and return labelled amounts. If one clinic currency is required instead, enforce it in invoice creation/update and document that restriction. Any conversion would need an explicit rate/date policy; do not invent live exchange-rate behavior.

### R14 — High: some spreadsheet exports omit the existing text protections

Location: `apps/exports/visit_export.py:10–43`; `apps/exports/clinical_data_export.py:10–17,40–47,74–85`; compare `core/spreadsheets.py:1–12` and protected patient/report exports.

Visit CSV writes patient names/complaints directly; visit XLSX and catalog XLSX write names, codes and other editable strings without `csv_cell`/`text_cells`. Catalog metadata sheets also include request-supplied filters without protection. Values beginning with formula syntax therefore reach spreadsheet consumers as formula candidates; in XLSX, `=`-prefixed strings are not explicitly forced to text. The current implementation record's broad spreadsheet-protection claim does not hold for these files. The optional openpyxl probe could not run in the available interpreter; no spreadsheet was generated or opened during this review.

Correction: reuse `csv_cell` for untrusted CSV strings and `text_cells` on every relevant XLSX sheet before save, including metadata sheets. Retain actual numeric/date cells and all existing columns. Validate exported cell types and consumer behavior later under explicit verification authorization.

### R15 — Medium: appointment reopening/rescheduling permits inactive doctors

Location: `apps/appointments/services.py:33–63,255–289,298–330`; compare creation eligibility at `139`.

Creation requires an active doctor/admin, but rescheduling and reopening only lock the user row's ID and check slot availability. An administrator can deactivate a doctor, then reopen or move an existing appointment onto that inactive account's schedule. `full_clean` checks FK existence, not active status or clinician role. The same issue applies after the doctor account changes to a nonclinical role. Creation also validates its already-loaded user before locking rather than reloading eligibility under the lock.

Correction: return/reload the locked clinician and validate current active/role eligibility whenever moving or reoccupying a slot. Preserve historical appointments on inactive clinicians and cancellation/closure operations; do not require reassigning historical authors merely to retain their records.

### R16 — Medium: the next-appointment shortcut differs from appointment scope and time semantics

Location: `apps/appointments/views.py:274–294`; compare `core/access.py:32–41`.

The shortcut checks patient access, then queries unscoped `Appointment.objects`. A doctor with patient access can receive the date/time of another doctor's booking even though normal appointment lists/calendar restrict doctors to their own schedule. It also filters only `appointment_date >= today`, so an earlier scheduled appointment today can be returned ahead of an actually future appointment.

Correction: use the same authorized appointment queryset, then filter future local date/time. If any-doctor patient appointment hints are an intentional separate permission, make that contract explicit instead of inheriting it accidentally from patient access.

### R17 — Medium: scale creation permits definitions that encounters reject

Location: `apps/clinical/services.py:88–95`; `apps/visits/scale_validation.py:22–26`.

The add-field service has no active-question limit, while encounter responses reject any definition above 100 questions. Repeated successful field additions can create an active scale that cannot be newly answered. Parent versioning serializes edits but does not enforce this shared bound.

Correction: enforce the same active-field limit while holding the scale lock, and report it in scale metadata/UI. Preserve previously snapshotted definitions; apply the rule to new definition edits and recovery validation deliberately.

### R18 — Medium: relative tolerance admits off-step numeric scale values

Location: `apps/clinical/models.py:102–105`; `apps/visits/scale_validation.py:65–67`.

Step alignment uses `math.isclose(increments, round(increments), abs_tol=1e-7)` with its nonzero default relative tolerance. At large allowed finite increment counts, the relative tolerance exceeds the desired fractional tolerance. A standalone calculation confirms increments `1000000000.25` are accepted against integer `1000000000`. A definition with minimum 0, maximum 2000000000 and step 1 therefore admits a noninteger default/answer. This is an edge case; typical small score ranges are not shown to fail.

Correction: explicitly choose absolute alignment tolerance with `rel_tol=0`, and document/bound meaningful score magnitudes. Retain overflow/finite/range checks and use the same rule for field defaults and answers.

### R19 — Medium: primary-identifier synchronization omits part of the unique identity

Location: `apps/patients/services.py:95–102`; `apps/patients/record_models.py:29–40`; related primary-value synchronization in `record_services.py:150–157`.

Identifier uniqueness includes issuing country, but profile synchronization's `get_or_create` omits that field. Two active national identifiers with the same value and blank issuer, but different valid countries, are allowed by record services/the model. A subsequent ordinary profile update with that national ID can raise MultipleObjectsReturned, since `_sync_identifier` runs on every update. Retiring/correcting one identifier also identifies the primary using value/type alone, so it may clear the profile value while another matching active identifier remains.

Correction: define an explicit primary-identifier record or use the full documented identity tuple consistently. For the existing compatibility projection, specify which country/issuer it represents; avoid arbitrary first-match behavior or retiring distinct identifiers as a side effect of a profile correction.

### R20 — Medium: profile emergency contacts and structured contacts diverge

Location: `apps/patients/services.py:133–135,153–185`; `apps/patients/record_services.py:15,70–171`; `apps/exports/base.py:124` and `word_generator.py:43–45`.

Patient creation copies the legacy emergency-contact fields into a structured primary emergency contact. Later profile edits do not update that row, and contact-record edits do not update the profile projection. Change the phone through either path and the other path retains the old value. PDF/Word contexts read the legacy emergency contact and also enumerate current structured contacts, so the same report may carry contradictory emergency details.

Correction: choose a canonical contact owner and make the legacy fields a deliberate projection, or remove them from writable forms while supporting older reads. Do not silently overwrite multiple contacts; bind any projection to an explicit primary emergency record and retain correction history.

### R21 — Medium: reminder resets can reuse an already-read notification

Location: `apps/notifications/services.py:36–42,60–66`; `apps/notifications/signals.py:24–31,47–54`; both `send_*_reminders` commands.

Resetting reminder flags and retiring related notifications removes only unread rows. Reopen a completed task at the same due date, or reopen/reschedule an appointment back to the same date/time after its reminder was read: the old dedupe key still exists. The job's `get_or_create` returns that read notification and sets the reminder-sent flag without producing a new unread reminder. The reset flag and notification lifecycle no longer describe the same delivery occurrence.

Correction: distinguish retries of one delivery from a new lifecycle occurrence. Add an occurrence/generation identifier that changes on explicit reopen/reschedule, while keeping retries within that occurrence deduplicated. Preserve read notification history rather than deleting it to make a unique key available.

### R22 — Medium: the development scheduler can miss hour-before reminders

Location: `config/settings/base.py:64`; `core/management/commands/run_scheduler.py:27–44`; `send_appointment_reminders.py:57–78`; clinic reminder default in `apps/settings/services.py:76`.

The development loop defaults to two hours between runs, while the hour reminder defaults to a one-hour future window. Run at 08:00: an appointment at 09:30 is outside that window; the next run at 10:00 excludes it because it is already past. The separate day reminder may still exist, but the hour reminder is missed. The documented production hourly timers mitigate the default mismatch; delayed/failed runs still require an explicit catch-up policy.

Correction: validate polling frequency against the shortest reminder window, or persist due reminder events and process them with a documented late-delivery rule. Generate message timing from the actual due interval; catch-up tasks/appointments currently use the configured offset in text even when the actual interval differs.

### R23 — Conditional high: DEBUG raw-media routing bypasses download authorization

Location: `config/urls.py:14–15`; `apps/patients/serializers.py:105–115`; protected patient/visit download endpoints; production media deny rule in `docs/setup/deployment.md`.

When DEBUG is enabled, URL configuration serves MEDIA_ROOT through Django's static file view with no application authentication/scope check. A known patient-document/attachment media path can be fetched directly, bypassing the protected download API. UUID filenames reduce guessing but are not access control; patient document metadata exposes the relative filepath to authorized consumers. The documented production Nginx topology denies raw media, so this finding specifically affects shared/network-accessible debug use.

Correction: preserve protected downloads in development too, or enforce a clearly local/private debug boundary and explicitly prevent public raw clinical media routing. Keep nonclinical public assets separate from patient storage.

### R24 — Medium: restore audit actor can become a different restored account

Location: `apps/backup/views.py:129–137`; `apps/backup/backup_restore.py:230–247`.

Full restore replaces accounts with backup IDs. The post-restore audit action chooses the current request's old user ID whenever a restored row with that numeric ID exists. It does not establish that the restored row represents the initiating person. Restoring another installation/account inventory with a colliding ID attributes the new restore event to that different restored account. If no matching ID exists, the initiating identity is lost entirely.

Correction: capture a bounded initiating-principal identity before replacement in the recovery receipt/audit details. Link a restored account only after an explicit identity match, otherwise retain a system event with the captured initiating actor. Do not retain credentials/session secrets in that snapshot.

### R28 — Medium: referrals bypass the shared version parser

Location: `apps/referrals/views.py:18–23`; `apps/referrals/services.py:26–33`; compare `core/mutation.py:18–43`.

Referral issuance applies `int()` to the body version and ignores `If-Match`. Boolean/fractional values can be coerced to a matching integer (for example True/1.9 to version 1), while a header-only request is rejected and conflicting header/body versions are not detected. Other versioned mutations use the strict shared parser. The ordinary frontend currently supplies a proper body version, so the discrepancy chiefly affects direct/alternate clients.

Correction: parse the request with `request_version`, pass an already validated integer to the service, and preserve the final visit/revision recheck. Validate reason as bounded text rather than accepting arbitrary values by stringification.

## Additional risks: concurrent operation and failure recovery

### R25 — High: full restore has no exclusive boundary with normal writes or another restore

Location: `apps/backup/backup_restore.py:215–247`; `apps/backup/views.py:111–138`; `core/middleware.py:104–108`; maintenance state is only reported in `apps/system/views.py:42`.

Restoration replaces files before opening its DB replacement transaction and does not acquire an application-wide maintenance/recovery lock. Normal readers/writers and another restore can remain active. A reader can observe old database metadata with replaced bytes; an upload/write can race the inventory replacement; two restores can interleave media writes and compensation. Transactions protect the individual DB replacement, not the shared file store or all previously started requests. The source and operations guide do not establish a quiescence protocol for this HTTP action.

Correction: design an exclusive restore protocol covering workers, writes, media consumers and scheduler jobs, with explicit handling of requests already in flight. Acquire it before the safety snapshot and media replacement; release it only after a verified durable completion receipt. Test on the actual deployment/storage/database topology. This is inferred from missing coordination, not a reproduced loss of clinic data.

### R26 — High: post-commit cache failure can roll back media after DB restore has committed

Location: `apps/backup/backup_restore.py:225–255`; `core/cache_utils.py:6–8`.

Recovery's broad exception/compensation block surrounds the DB atomic block and its after-commit invalidation callbacks. Those callbacks call `cache.set` without isolating failures. If the DB commit succeeds and a cache callback then raises, the surrounding except branch deletes newly restored files and restores old bytes even though the database has already committed the restored inventory. New checksums/references can therefore be paired with old/missing files. This requires an injected/shared-cache failure to reproduce; it was not run. Django documents that callback failures do not roll back the committed transaction, and ordinary nonrobust callback exceptions stop subsequent callbacks. [Django 5.0 transaction documentation](https://docs.djangoproject.com/en/5.0/topics/db/transactions/#exception-handling).

Correction: distinguish precommit failure from failure after a successful durable commit. Only compensate files when DB replacement truly rolled back. Handle post-commit cache publication as a separately retryable/reportable operation, preserving the committed inventory/media and reliable operation receipt. Apply the same post-commit error reasoning to ordinary idempotent writes.

### R27 — Medium: destructive catalog previews do not bind current inventory or versions

Location: `apps/import_export/views.py:178–209,288–308`; `apps/import_export/services.py:198–239`.

Catalog preview tokens bind user/file/category/mapping/policy but not the catalog inventory or versions represented in the preview's retirement counts. Create or edit a catalog entry after preview, then execute replacement: parsing is rerun and all current entries outside the file are retired, including additions the user never previewed. Parsing also precedes the row locks, so an intervening edit can be overwritten without a version conflict. File integrity binding is sound; current-database impact binding is incomplete.

Correction: bind the relevant inventory/version digest in replacement previews and recheck it under a consistent catalog write lock before applying changes. For merge mode, explicitly choose row-version conflict handling instead of silently replacing newer editable content. Preserve the existing refusal of invalid/empty replacements and file/mapping checks.

### R29 — High: post-commit cache failure can erase a successful mutation receipt

Location: `core/middleware.py:104–123`; `core/cache_utils.py:6–8`; patient/appointment/billing/task/catalog save signals.

For ordinary covered writes, the mutation and completed idempotency response are committed inside the same outer atomic block. Cache invalidation callbacks then run. If one raises, the middleware's generic except deletes the operation row and rethrows, although both the mutation and completed receipt were already committed. The client receives a failure, retains its key for an uncertain retry, and the missing receipt allows the mutation to execute again. A create can therefore produce duplicates after a post-commit cache outage. This is distinct from a worker dying before completion (R11) and from full restore's deliberate row deletion (R12). The transaction semantics are the same documented after-commit boundary described in R26; this failure path was not injected at runtime.

Correction: preserve completed receipts across post-commit failures and make cache publication failures separately retryable. Cleanup may remove truly uncommitted/abandoned reservations, but must not unconditionally delete a completed operation. Do not move invalidation before commit; that reintroduces rolled-back cache publication problems.

## Model/design suggestions, separate from defects

1. **Keep the service-centered architecture.** Protected parent relationships, immutable revision/document snapshots, explicit versions, decimal invoice lines and dated care-team history are valuable. A broad model rewrite would risk these working contracts.
2. **Choose one owner for follow-up lifecycle facts.** The two-way-looking visit/register structure currently has one-way synchronization and overlapping writable fields. A canonical action with a visit projection, or a strictly read-only legacy bridge, would remove several inconsistencies above.
3. **Make clinical authority explicit in report queries.** Reports over editable rows should intentionally choose working state or signed revision facts. Extend this review principle to diagnoses, medications and performance reports rather than silently changing all counts to signed-only.
4. **Strengthen model-level invariants where practical.** Candidates include completed-visit/status consistency, active/retired metadata consistency and signed-state/signature metadata. Cross-patient references and lifecycle transitions still need service validation; simple database checks cannot express every relationship. Any schema work requires a separately authorized migration request.
5. **Define effective dated membership centrally.** Scope currently checks only `ended_at IS NULL`, ignoring `started_at`. This is not an evidenced ordinary API defect because current membership creation uses now, but future-dated memberships from recovery/direct integrations would grant early access. Decide whether future scheduling is supported or prohibit it at those boundaries.
6. **Treat ORM immutability as an application guard.** `ImmutableModel` blocks ordinary save/update/delete paths, but raw recovery intentionally bypasses it. Mutable visit child setters also depend on callers using the service. Restrict their use to the canonical service; consider stronger database enforcement only if the threat/operational requirements justify it, preserving explicit recovery behavior.
7. **Keep unknown distinct from zero in reporting.** Average age currently returns zero when no birth years are known. Consider nullable/unknown results and known/unknown denominator counts, preserving the year-only age approximation.
8. **Review historical linkage on merges as a documented policy.** Merge moves current records and increments their versions while immutable revisions/corrections retain original ownership. This is coherent, but access broadening through transferred authorship/team and the difference between current identity and signed identity should remain visible in the preview and history UI.
9. **Give clinically meaningful profile edits protected history.** `family_history`/`important_notes` are writable profile fields but absent from profile `CORRECTION_FIELDS` and detailed audit snapshots. Their old content is not retained by a dedicated profile revision. Decide which narrative/contact/communication edits need correction reasons and before/after record history, stored behind appropriate permissions rather than copied into broadly visible audit/debug logs.
10. **Define export/import fidelity explicitly.** Medication export includes controlled/status columns; `_catalog_rows` imports only the five name/dosage/brand fields. New imported entries consequently default to uncontrolled/active even when those exported columns say otherwise. Either support validated optional fields with an honest preview, or label this as a catalog-content import rather than a complete catalog round trip. Full authenticated ZIP remains the complete recovery mechanism.
11. **Keep current-record reports distinguishable from approved artifacts.** General visit/patient PDFs and Word reports read mutable encounter rows/current identities, whereas prescriptions/referrals read signed revisions. An open amendment can combine new working narrative with old signer metadata in a general export. Use a clear working-copy state or a signed-revision export mode; preserve access to exact issued bytes without regenerating them as if they were the original artifact.
12. **Centralize service actor/scope and version boundaries.** Some services enforce access internally after locking; others rely on the view and do not accept an actor. Make intentional trust boundaries clear for commands/imports/recovery as well as HTTP callers. Child writes that change a patient register should use the same parent-version policy as direct register edits. Reorder operations currently lock/bump tasks but accept no opening versions; decide whether last-write-wins ordering is intended.
13. **Review operational ownership when accounts become inactive.** Dated team memberships, pending assigned tasks, owned follow-ups and appointments can survive account deactivation. Retaining history is correct, but active responsibility should have an explicit reassignment/coverage workflow. Password recovery currently saves a preloaded whole User without a row lock/version bump; concurrent administration could overwrite newer account fields. Login success also uses a preloaded lockout state; verify its interaction with simultaneous failed attempts before claiming concurrent lockout guarantees.
14. **Share exposed configuration and effective metrics.** Appointment model/service/availability defaults use 30 while system config exposes `DEFAULT_APPOINTMENT_DURATION`; reconcile behavior if that setting differs. Clarify no-show denominators (currently including cancellations), future appointments included in weekly totals, nullable-age coverage, signed versus working assessments and deterministic tie ordering. Preserve the currently documented inclusion of drafts in general visit counts.
15. **Verify portability against the selected database.** Conditional/expression uniqueness, decimal rounding checks, nullable cursor sort fields and lock behavior require checks on the actual pinned runtime/database profile. Read-only AST checks establish none of these. Model validation protects many ordinary paths, but raw recovery must also establish cross-record meaning, not only field types/FK existence and supported schema labels.
16. **Treat media/database rollback as an explicit protocol.** Upload helpers compensate immediate persistence exceptions, but files written before an outer request rollback can remain orphaned. Retain the reconciliation command and define staging/finalization for stronger guarantees. Verify binary decoding/dimensions, nested Office macro layouts, all download checksum expectations and historical attachment inventories; this review did not run a malicious-file corpus or PDF rendering.
17. **Bound backup and response-storage growth together.** Backup creation buffers the full inventory/media and can produce files above the restore upload/expansion limits. Align creator preflight, restore limits and deployment capacity so a successfully created backup is actually recoverable. API idempotency also persists complete backup response bytes (R11); model-level storage bounds and operation retention matter alongside filesystem retention. Automatic backup names have second precision and writes are direct: overlapping runs can collide or leave partial archives after a crash; consider unique temporary files and atomic publication. Safety-before-restore copies intentionally fall outside automatic retention and need an explicit capacity policy.

## Recommended order and verification limits

Use the priority index above. Keep the existing working model architecture, then correct authority/lifecycle/authorization and durable recovery boundaries before expanding business features. R4, metric attribution, contact ownership and replay-after-revocation behavior have explicit policy choices to settle before changing valid client inputs. No implementation changes are authorized by this review request.

| Subsequent verification area | Evidence needed |
| --- | --- |
| Patient/clinical workflows | Follow-up terminal/reset/correction invariants; primary identifier country/issuer handling; emergency-contact projections; summary permissions; draft completion evidence; approved versus working risk |
| Security/scope | Team-only revocation before/after mutation locking; replay after membership/permission removal; debug raw-media denial; restored actor identity; strict referral body/header versions |
| Scheduling/tasks/notifications | Inactive clinician reopen/reschedule; authorized truly future next appointment; repeated lifecycle reminder delivery; delayed polling; task reorder and concurrent reassignment semantics |
| Billing/report/export | Labelled per-currency totals; actual author/team attribution; precise monetary constraints on selected DB; XLSX cell types and CSV consumer behavior; signed/current export distinctions |
| Imports/recovery | Changed inventory between preview/execute; concurrent restores/uploads; process termination around reservation/commit; cache failure after ordinary/full-restore commit; recoverable operation receipts and exact restored bytes |
| Runtime/hosting | Pinned supported Python/Django/DRF, PostgreSQL/MySQL/MariaDB/shared cache as selected; constraints/locks/cursor null ordering; storage capacity, macro/image corpus and PDF/Arabic output |

Only production-source review, AST parsing, a standalone arithmetic calculation, documentation/reference checks and framework-documentation confirmation were performed. No new suite, DB/concurrency/cache-failure, browser, spreadsheet-consumer or PDF rendering verification was run. The lack of a finding in an area is not a claim of complete correctness. Existing completed findings were reopened only where current source supplied new evidence.
