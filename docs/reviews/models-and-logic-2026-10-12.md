# Backend models and cross-model logic review

Reviewed and corrected 2026-10-12. R1–R29 now have production-source corrections; the obsolete pending findings and review-only authorization text have been replaced by the dispositions below. Source completion is distinct from deployed/runtime verification. Remaining actionable checks are centralized in [current work](../workCurrent.md).

## Completed dispositions

| Finding | Final correction / source |
| --- | --- |
| R1 | High-risk patient report selects each encounter's latest approved revision, including the last approval during an unsigned amendment; JSON values explicitly extracted as text. `apps/reports/visit_statistics.py`. |
| R2 | Shared terminal follow-up policy; identical outcome is a no-op, replacement is rejected without overwriting actor/time. `core/follow_up.py`, visit/record services. |
| R3 | Visit-owned status/date/evidence/reason cannot be changed through the register. A newly scheduled occurrence retires the old terminal bridge; pending clears evidence/reason. Bridge writes advance patient versions. `patients/follow_up_services.py`, `record_services.py`. |
| R4 | Newly assigned completion evidence must be an active final/locked encounter with an approved revision. Existing historical references remain retainable. `patients/record_services.py`. |
| R5 | Every changed clinical summary, including unknown, needs clinical-edit permission; unchanged echoes remain accepted. Unknown/negative summaries cannot contradict active positive records. `patients/services.py`. |
| R6 | Current assignment uses dated active care-team membership grouped by user ID; performance separates assigned patients, patients treated and visits actually authored. `reports/patient_statistics.py`, `doctor_performance.py`. |
| R7 | Operational overdue closure limits legacy visits to active scoped patients, matching the action register. Archived history remains readable separately. `visits/services.py`. |
| R8 | Encounter services recheck current action permission and patient scope after patient-before-visit locking, retaining historical-author scope. Attachment actions use their existing document permission. `visits/services.py`. |
| R9 | Issuance locks parent before visit and rechecks scope, required permissions, preview patient version and final revision. Exact issued bytes remain immutable. `prescriptions/issuance.py`. |
| R10 | Replay runs current endpoint permissions and current resource/queryset scope without executing the mutation. Prescription/referral replays also require clinician/edit authority. `core/replay.py`, `middleware.py`. |
| R11 | Ordinary reservation, mutation and receipt commit together: worker death rolls back an unfinished reservation. Expiry is enforced; `cleanup_operations` expires completed receipts after 30 days. Legacy processing entries report interruption rather than falsely claiming live processing. Interrupted destructive recovery requires explicit reconciliation. |
| R12 | `RecoveryOperation` has no restored-account FK and stays outside backup/replacement inventory. Bounded completion receipt commits with restored inventory, remains available to an authorized restored administrator after relogin, and never reexecutes a completed restore. `core/models.py`, middleware, backup services/views. |
| R13 | Paid reconciliation aggregates labelled amounts by currency; frontend renders each currency independently. `reports/services.py`, frontend `Reconciliation.vue`. |
| R14 | Visit CSV uses `csv_cell`; visit/catalog XLSX forces strings to text on all sheets, including metadata, preserving numeric/date cells. `exports/visit_export.py`, `clinical_data_export.py`. |
| R15 | Booking, rescheduling and reopening validate freshly locked clinician activity/role; historical cancellation/closure remain allowed. `appointments/services.py`. |
| R16 | Next appointment uses the authorized appointment queryset and future local date/time with deterministic ordering. `appointments/views.py`. |
| R17 | Locked scale edits enforce 100 active questions; metadata/UI expose the limit; raw recovery rejects oversized active definitions. Existing answer snapshots are retained. `clinical/services.py`, serializers, backup validation, frontend `ScalesAdmin.vue`. |
| R18 | Default/answer step checks explicitly use `rel_tol=0`, retaining finite/overflow/range checks. `clinical/models.py`, `visits/scale_validation.py`. |
| R19 | Compatibility primary national ID explicitly projects the blank-issuer/blank-country tuple. Profile synchronization and record correction/retirement use that complete identity, retaining distinct country-issued records. Patient services. |
| R20 | Active primary emergency contact owns legacy contact fields; profile writes use the versioned record/correction service. Primary changes/retirement update the projection; transferred merge contacts remain additional contacts so survivor projection stays unchanged. Patient services/merge. |
| R21 | Task/appointment reminder UUID identifies an occurrence, changes on explicit reopening/rescheduling/reassignment, and stays stable through retries and normal task progress. Read notification history is retained. Models, services, signals/reminder jobs. |
| R22 | Development polling is capped at half the current hour-reminder window, with bounded 60-minute late delivery; messages use actual scheduled dates/times. Automatic backup cadence remains separate through `BACKUP_CHECK_INTERVAL_HOURS`. Reminder jobs/scheduler. |
| R23 | Raw DEBUG clinical media serving removed; protected API downloads remain the only application route. `config/urls.py`. |
| R24 | Restore captures bounded initiating identity before replacement. Full restore audit is a system event with that identity, never a numeric-ID match to a different restored principal. Backup views/receipts. |
| R25 | Operation gate drains HTTP readers/writers and participating jobs before exclusive snapshot/restore/catalog work. PostgreSQL uses session advisory locks; other profiles require common POSIX lock storage across all workers/jobs. Protected streams are buffered within the gate. Interrupted recovery blocks further restores until explicit operator reconciliation. `core/operation_gate.py`, middleware/jobs/services. |
| R26 | DB-backed cache generations commit with mutations; cache publication/read outages degrade to cache misses. Restore separately marks durable commit and compensates media only before commit; receipt/audit commit with inventory. `cache_utils.py`, backup restore. |
| R27 | Preview binds full catalog content/version inventory; execute checks it under the same exclusive gate before parsing/applying rows. Merge and replacement both reject stale inventory; empty/invalid replacement safeguards retained. Import/catalog services/views. |
| R28 | Referral uses shared strict body/If-Match parser and bounded typed reason; final issuance still rechecks revision/version. Referral services/views. |
| R29 | Ordinary successful receipt shares the mutation transaction and is never unconditionally deleted after commit. Durable generations eliminate fallible postcommit cache callbacks. Middleware/cache utilities. |

## Related design decisions

- Preserve service-centered ownership, immutable approved revisions/issued artifacts, dated history, decimal billing and explicit current-versus-approved reporting. No broad model rewrite or raw database immutability enforcement was introduced.
- Effective team scope now checks membership start time. Unknown average age remains null and the UI labels it unknown. New appointment defaults consistently use the exposed duration setting.
- Family history/important notes need clinical-edit permission and reason-bearing corrections. Clinical profile history stays behind clinical-view permission; ordinary contact corrections no longer invalidate verified identity. Working visit/PDF exports are labelled unapproved and suppress previous approval signatures.
- Medication spreadsheet import is explicitly a content import: five mapped text fields, existing controlled classification retained, new drugs uncontrolled, imported content active. UI explains that activation/controlled columns are not full recovery. Authenticated ZIP remains full recovery.
- Password recovery locks and updates only intended fields with a version bump; login checks/reset occur under the same account lock, with failed-attempt bookkeeping committed before raising authentication failure.
- Backup creation enforces restore upload/expansion/member limits; automatic archives use unique names and atomic publication. Safety-copy retention remains an explicit operator capacity policy.
- Partial payments/refunds, exchange-rate conversion, operational reassignment features, reorder conflict UX, database triggers and a general staged-upload protocol were not chosen as fixes to these findings. Existing supported behavior remains; future product work needs its own scope.

## Verification and rollout limits

43 focused production-source/ORM probes passed in synthetic in-memory SQLite using system Django 5.2.9, including clinical transitions/projections, approved risk, authorship, scale bounds, stale import inventory, ordinary mutation/receipt rollback, restore receipt retention, precommit media compensation, postcommit failure preservation and two-process POSIX gate exclusion. Missing DRF/phone/MIME boundaries were excluded or fail-closed substitutes; these probes do not establish HTTP integration. Five Vue descriptor/script parses, AST parsing of 178 production Python files, and changed-document reference checks also passed; results are in [completed work](../doneCurrent.md).

No migration files or test-suite files were inspected/changed. No suite, production build, clinic database/schema action, dependency/version change, browser, spreadsheet-consumer or PDF rendering was performed. New `CacheGeneration`/`RecoveryOperation` tables and reminder-generation fields require separately authorized schema initialization/application before running this source on an existing database.

Pinned Python/Django/DRF, PostgreSQL/MySQL/shared-storage locking, real cache/worker termination, HTTP replay after permission removal, and rendered/export consumer behavior remain deployment/integration checks in the current work record. Every worker/job must participate in the gate; direct external database/storage writers must be quiesced. An interrupted recovery cannot be assumed safe to repeat; reconcile inventory/media from the safety archive before explicitly acknowledging its receipt.

## Area-by-area coverage

| Area / main production sources | Relationships and logic reviewed | Original finding references |
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
| Frontend contract consumers | Shared API client's observed versions, `If-Match`, idempotency/retry bookkeeping; patient/visit/scale/billing/import/recovery/prescription/referral/task services | R9/R12/R28; frontend consumers checked; rendered verification remains open |

The backup/import/report apps without their own models were still reviewed: they mutate, serialize or aggregate other apps' models. A row without a new defect is coverage, not a runtime guarantee.

## Model inventory and ownership

| Models | Intended fact owner / boundary |
| --- | --- |
| `Patient`, `PatientIdentifier`, `PatientContact`, `PatientRepresentative` | Current identity/contact/representation facts; explicit verification and correction history; patient parent version |
| `PatientCareTeam` | Dated assignment/access, independent of compatibility `Patient.doctor` and retained historical-author scope |
| `PatientAllergy`, `PatientMedication` | Longitudinal clinical facts and source/provenance; clinical action permission |
| `PatientFollowUp` | Independent action lifecycle/evidence; visit-owned bridge with retained occurrences |
| `PatientCorrection`, `PatientMerge`, `PatientDuplicateReview` | Immutable corrections/merge manifests; mutable duplicate-review decisions with ordered pairs |
| `PatientDocument`, `VisitAttachment` | Stored clinical file identity/provenance/checksum; scoped download and retained media |
| `Visit`, `VisitDiagnosis`, `VisitMedication`, `VisitScaleResponse` | Working encounter facts and saved catalog/scale definitions; guarded replacement while editable |
| `VisitRevision` | Approved immutable clinical snapshot, signer/time/reason and identity at signing |
| `IssuedDocument`, `PrescriptionSignature` | Exact immutable issued artifact versus auxiliary signature record; revision linkage and issuance actor |
| `DiagnosisOption`, `MedicationOption`, `ClinicalScale`, `ScaleField`, `ClinicalNoteTemplate` | Current reusable definitions; retirement preserves encounter snapshots; scale edits use parent versions |
| `Appointment` | Doctor schedule occupancy and attendance lifecycle; patient reference does not imply completed clinical encounter |
| `Invoice`, `InvoiceLine` | Invoice/line monetary facts, issue identity, currency and full-payment lifecycle; no inferred partial-payment/refund system |
| `User`, `UserTask`, `Notification`, `ClinicSetting` | Principal/security state, assigned work, per-recipient delivery state and versioned clinic configuration |
| `AuditLog`, `IdempotencyOperation` | Bounded audit metadata and transactional operation identity/result; independent recovery receipts and durable cache generations |
| Abstract/shared bases | `TimeStampedModel`, `SoftDeleteModel`, `ImmutableModel`, `PatientRecord`, `ClinicalPatientRecord`; managers/querysets provide application guards |

Reports, imports, recovery, referrals, dashboard, exports and system modules have no independent clinical fact model; their consistency depends on consuming/mutating the owners above.
