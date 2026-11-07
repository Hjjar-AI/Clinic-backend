# Models and API contracts

Django/DRF `apps/`, shared `core/`, configuration `config/`. Services own validation/lifecycle; serializers adapt representation. [Recovery](operations.md#recovery) · [Setup](setup.md) · [Evidence](doneCurrent.md).

## Shared boundaries

- `/api/v1/`: session credentials/config CSRF bootstrap; unsafe requests send `X-CSRFToken`. Preserve falsy `data`/`error` envelopes, file responses and empty 204/205/304 bodies/replays.
- Mutations require positive integer opening `version`/quoted `If-Match`; reject bool/float coercion/header-body disagreement. Retain payload/idempotency key after uncertain outcomes; refresh conflicts. Ordinary reservation/mutation/receipt commit together, expire after 30 days and replay only under current action/resource authorization.
- Require effective grants **and** patient/team/historical-author/creator scope, never role alone. Re-read active actors/grants after parent/resource locks; views pass actors. Lock patient before visit/invoice. Archived parents reject operational writes; history stays readable. Signing/issuance requires authorized clinician/edit access.
- Lock current accounts for login/reset; failed-attempt bookkeeping commits before auth failure. Security changes revoke sessions. Normalize usernames NFKC/trim consistently; creation never rewrites existing role grants. Preferences allow only bounded schema 1/density/splitView/progressive; API deactivates accounts.
- Reject unknown write keys; read-only echoes are inert. Explicit nested serializers and frontend `src/services/contracts.js` write allowlists preserve opening versions/nullable values. Scale-question commands separate parent version from definition fields.
- Signed/correction/merge/audit history rejects ORM update/delete/updating bulk upserts; authenticated raw recovery is the deliberate exception. Constrain lifecycle/verification/team stamps, enums, positive revisions and receipt state/response/expiry; restoration clears current archive stamps, retains history. Ordinary missing text is empty; clinical unknown/dedupe-disabled keys retain NULL.
- Model cache ownership/ audit fields have single registries. DB `CacheGeneration` commits with mutations; cache failures become misses, never lost receipts. Raw restore explicitly invalidates groups. Clinical text stays in protected domain history; audit stores allowed metadata.
- [Runtime](setup.md#native-libraries-by-os): fail closed without native locking/MIME/PDF; platform setup never weakens these contracts.

## Patient identity and ownership

Names required; birth optional **year-only**; gender/ID/phone may be unknown. `patient_number` permanent/unique. Cross-person duplicate IDs/phones warn without suffixing/blocking. Completeness recommends birth/gender/registration, optionally ID/phone/team/language; it is not validity.

| Owner | Invariants |
| --- | --- |
| Patient | Current identity/registration (`admission_date` alias), occupation/address/phone/preferences; marital codes `single/married/divorced/widowed`, gendered Arabic labels only. `national_id` projects active same-patient national `primary_identifier`; `doctor/doctor_id` project effective doctor-role team. Verification actor/time is server-owned and invalidated by identity changes. |
| Identifier | Active type/value/issuer/uppercase two-letter country tuple unique within patient, nonunique across people. Profile ID creates/selects blank issuer/country and retires old selection with reason; `select_primary` may choose an issuer/country-specific national record. |
| Contact | Multiple records, at most one active primary; active primary emergency contact supplies read-only summary. Profile/register share canonical records/history; name/relation limits 150/100. |
| Representative | Separate identity/contact/authority/evidence/verification/validity; representation grants no login access. |
| Care team | Effective dates/roles doctor, nurse, therapist, assistant, coordinator drive scope/display/completeness. Unended planned rows reserve patient/user; cancellation cannot predate start. Retain ended/rejoined rows. Nonadmin creators join; admin selection need not join clinician team. |
| Allergy/medication | Longitudinal status/dates/provenance/visit/notes. Changes need clinical-edit; positives set summary recorded, retirement never implies none-known. Unknown/negative summaries cannot contradict active positives; unchanged echoes allowed. |
| Follow-up | Due/method/optional effective-team owner; pending/completed/missed/cancelled/waived. Server `outcome_at/outcome_by`; reason/evidence same-patient. Newly linked completion needs active final/locked approved visit; `completed_revision` pins that approval through later amendment/archive. Terminal outcomes/schedule/source/appointment/completion links cannot be rewritten/reopened. |
| Document | Protected bytes/checksum/MIME/size, category/date/source/provider, server verification and opening document version; archive retains bytes. |
| Correction | Immutable actor/time/reason/before-after for **all** changed editable profile/register facts, including verification invalidation. Family history/important notes/allergy-medication summaries need clinical-edit; their history needs clinical-view. |
| Duplicate/merge | Optional ordered-pair review; explicit immutable merge manifest retains original ownership/content/team/adjustments. |

Register edits/retirements need reasons, stamps, valid choices/dates/links; identical edits are no-ops. Later follow-up schedules create new occurrences; reports count active occurrences once. Methods: In-person/Telehealth/Phone.

`Visit.follow_up` uniquely protects the current occurrence; `source_visit` retains provenance. Read nested `follow_up`; write `follow_up_input: {due_date,method,reason}`. Unchanged echo is a no-op; change/removal needs reason. Removing pending retires/detaches it; removing terminal selection preserves its result. Outcomes use the register, not a visit-completion endpoint. Register locks patient → linked visit → occurrence and advances patient/linked-visit versions; retirement detaches current pointer. Visit-originated writes retain action permission; direct register edits need clinical-edit/scope. Signed snapshots retain sign-time facts.

## Patient API and reconciliation

Under `/patients/{id}/`:

| Endpoint | Shape / policy |
| --- | --- |
| GET `records/` | `kind,offset` → `{items,total,version}`, 100/page including retired identifiers/contacts/representatives/allergies/medications/follow-ups. |
| POST `records/` | `{kind,record_id?,operation:save/retire/select_primary,fields,reason,version}` → `{record,version}`. Primary selection: existing identifier, empty fields/reason; `is_primary`/outcome/completion metadata read-only. |
| GET `corrections/` | Offset → `{items,total,merges}`; 100 corrections/page/latest 100 merges, original source history retained. |
| POST `duplicate_review/` | `{other_id,status:dismissed/different,reason,version}`; optional, dismissible, repeatable display. |
| POST `merge_preview/`, `merge/` | Source URL/target ID; 10-minute token binds actor/both versions/content/team/access impact. Execute token/reason/versions, admin edit+archive grants and explicit consent. |
| Team/documents | `team_candidates/` returns minimal eligible users. Team edits use patient version/reason; documents their own version. |

Merge locks parents stably and rejects changed content/team dates/roles. Keep survivor demographics/primary identifier; transfer current records/visits/appointments/invoices/documents, explicitly combine teams. Planned memberships confer no early access; duplicate identifier tuples transfer retired, primary contacts nonprimary. Clear source primary ID, archive/link source; block source restoration. Never rewrite signed bytes/original ownership; expose broadened access/history. No automatic merge/undo.

## Encounters, documents and operations

Narrative/template schema 1 bounds known MSE/formulation/risk/plan sections, template treatment/doctor text and visit goals/provenance/acknowledgement. Unknown keys rejected; bounded namespaced `extensions` allowed. Goals: nullable progress or finite 0–100. Validate content/preferences without rewriting signed history.

Visits own working narrative/diagnoses/medications/labs/scales/files; draft/final/amended/locked changes use versions/reasons. Signing creates immutable schema-v4 `VisitRevision`; v3 remains readable unchanged. Snapshot identity/file number, longitudinal facts, clinician/time, clinical rows, scale definitions/answers, attachments and root follow-up. Retired catalogs cannot erase saved labels/controlled flags/scales. Scores/defaults finite, ranged, absolutely step-aligned; active scales max 100 questions.

`IssuedDocument` schema 1 is the sole signature/exact-PDF history: bytes/checksum/revision/actor/snapshot/signature/stamp, validated links and embedded images. Prescription signature required; prescription/referral needs final/locked approval, no unsigned-amendment issuance. Lock parent/visit and recheck scope/revision/preview patient version. Bytes+audit commit together; consume prescription preview only after commit, tolerate cache-cleanup failure. Clinical date/age comes from approval; address/clinic config are issue-time facts. Read-only visit revisions/issued-document history; current working exports labelled unapproved and suppress old signatures. Care setting and unknown/voluntary/involuntary `care_basis` remain separate; unknown is not false/zero.

Prescription `print_options`: blank/preprinted, width 80–216 mm, height 120–350 mm, offsets −5…5 mm (positive right/down), finite max two decimals. UI/default options A6 105×148; omitted API options A4. Blank offsets normalize zero. Retain options/date/exact bytes; preprinted artwork never enters PDF. Repeat identity/signature/date and page numbering; reject overflow rather than truncate. Auth/export-protected POST `/prescription/calibration/` produces patient-free crosses/50 mm ruler without issuance/preview consumption.

Under `/prescription/`: GET `patient/{id}/history/` returns `{items,total,offset,limit}`, newest first, 20/page, optional same-patient visit filter. GET `documents/{id}/pdf/` returns retained bytes; `documents/{id}/instructions/` creates separate A4 snapshot handout, no issuance/inferred schedule/duration. All require current clinical-view/export/scope, prescription kind and `no-store`; copies remain readable during amendment.

GET `visit/{id}/handover/` (optional `pdf/`) uses latest approved revision; `patient/{id}/handover/` picks latest approved encounter, optionally excluding current. Order by signed snapshot date, ties signing time/revision (handover) or encounter ID (risk); unsigned dates cannot reorder history. JSON needs clinical-view/scope, PDF also export. Optional `clinical_data.instruction_acknowledgement`: aware nonfuture `explained_at`, patient/representative/both recipient, optional name/notes, nullable boolean `clarification_needed`. Service owns recorder/time, ignores forgery/preserves unchanged stamps; include in signed revision.

| Area | Policy |
| --- | --- |
| Appointments | Lock active clinician eligibility; validate overlap/work hours/default duration. Completed booking cannot move; reopen/reschedule rechecks occupancy. Future shortcut uses scoped local schedule; retain inactive-clinician history. |
| Billing | Current manage-billing/scope, patient-before-invoice lock/opening version. Full UUID invoice numbers; default SYP, uppercase three-ASCII-letter currency. Amount ≤99,999,999.99; quantity 0.01–999,999.99; two-place half-up lines via Decimal service/model/recovery validation, not SQL multiplication equality. API decimal strings/UI integer hundredths. Derive totals from lines; omitted lines preserve rows/unchanged total, changed total needs explicit lines. Same-patient active visit; material details immutable after issue/payment, payment actor/time server-owned. Full payments only; no partial/refund/conversion. Reconcile paid totals by currency. |
| Tasks/notifications | Actor-aware assignment, reasoned terminal/reopen, guarded deletion; reorder locks stable IDs (last writer wins), semantic priority. Stable reminder occurrence UUID on retry/progress; renew on reopen/schedule/assignee change. Retain reads; structured entity/category/occurrence retirement; hash oversized dedupe keys. |
| Reporting | Latest approved risk survives amendment; effective-team assignments, authors/user IDs for treated patients/counts. Unknown average age NULL; general visit counts include drafts. |
| Import/export | Bounded UTF-8 CSV/XLSX, explicit maps/row outcomes and formula-safe text including metadata. Patient preview/create share preparation/scope; catalog writes/import/recovery share identity matching. Preview binds file/options/current inventory; changed/invalid/empty replacements cannot retire lists. Medication import is content-only. |

## Retention

Archive preserves clinical/profile/team/document/action history; finalized visits cannot be ordinarily deleted. Draft deletion retires/detaches pending follow-up but retains occurrence history. Pseudonymization clears mutable identity, not signed snapshots/corrections/merge/audit; no automatic purge policy. Full backup format 3 rejects earlier formats; validate primary/same-patient/pointer/source links, active occurrences/date bounds, completion/signer revisions, invoice arithmetic and issued checksums within authenticated inventory. [Full restore](operations.md#recovery) differs from catalog merge and may bypass ORM history guards only after validation.
