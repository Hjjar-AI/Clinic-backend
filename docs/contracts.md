# Models and API contracts

Django/DRF features live in `apps/`, shared infrastructure in `core/`, configuration in `config/`. Services own validation/lifecycle; serializers adapt representation; endpoint action permissions and shared record scope are both required. Current source is authoritative. [Operations](operations.md), [evidence](doneCurrent.md), [remaining work](workCurrent.md).

## Shared boundaries

- API `/api/v1/`, session credentials and config CSRF bootstrap. Unsafe requests send `X-CSRFToken`; JSON `data`/`error` envelopes preserve falsy data. Downloads are files; 204/205/304/replays have empty bodies.
- Mutations require positive integer opening `version`/quoted `If-Match`; bool/float coercion and conflicting header/body are rejected. Retain payload/key across uncertain retries; refresh conflicts. Ordinary reservation/mutation/receipt commit together, expire after 30 days, and replay only after current action/resource authorization.
- Patient scope combines effective dated care team and retained historical-author/creator scope; legacy doctor is display/create compatibility only. Backend effective grants, not admin role alone, determine actions; inactive users denied. User creation does not rewrite existing role grants.
- Patient-before-visit locking and post-lock scope/permission rechecks protect encounter changes. Login/password recovery lock current accounts; failed-attempt bookkeeping commits before auth failure; security changes revoke sessions. Signing/issuance require authorized clinician/edit permission.
- DB-backed `CacheGeneration` commits with mutation; cache outages degrade to misses without deleting successful receipts. Installation-local `RecoveryOperation` has no restored-account FK and is excluded from replacement inventory. [Recovery protocol](operations.md#recovery).

## Patient identity and ownership

Names are required; birth is optional year-only, gender/ID/phone may be unknown. `patient_number` is permanent and unique. Shared duplicate identifiers/phones warn nonblockingly without suffix changes. Completeness is a configurable recommendation, not validity: birth/gender/registration by default; optional ID/phone/team/language.

| Owner | Facts / invariants |
| --- | --- |
| Patient | Current names/year/gender, registration (`admission_date` alias), controlled marital status, optional occupation/address/phone/contact preferences. `national_id` projects blank-issuer/blank-country national ID. Identity verification actor/time are server-controlled and invalidated by changed identity. |
| PatientIdentifier | Type/value/issuer/uppercase two-letter country; unique active tuple within patient, duplicates across people allowed. Profile synchronization uses the complete compatibility tuple. |
| PatientContact | Person/relationship/phone/email/emergency/primary/notes; multiple contacts, at most one active primary. Active primary emergency contact owns legacy emergency fields; profile and register edits share versioned correction history. |
| PatientRepresentative | Separate identity/contact, authority/evidence/verification/validity; recorded representation does not grant login access. |
| PatientCareTeam | Role doctor/nurse/therapist/assistant/coordinator, start/end/assigner/remover/reason; effective only after start, one current user/patient membership; ended/rejoined rows retained. Nonadmin creators join team; admin selection need not add admin as clinician. |
| PatientAllergy / PatientMedication | Longitudinal substance/reaction/severity or drug/dosage/schedule/status/dates, source/provenance/visit/notes. Clinical-edit permission; positive evidence copies summary to recorded, retirement never silently asserts none-known. Unknown/negative summaries cannot contradict active positives; any changed summary requires clinical-edit, unchanged echoes allowed. |
| PatientFollowUp | Title/optional effective-team owner/due date, pending/completed/missed/cancelled/waived; server outcome actor/time, reason and same-patient visit/appointment/evidence. Newly attached completed visit must be active final/locked with approved revision; historical references retained. |
| PatientDocument | Protected uploaded bytes/checksum/MIME/size, category/description/date/source/provider, server verification and opening document version. Archive retains bytes; direct metadata lifecycle writes use canonical service. |
| PatientCorrection | Immutable actor/time/reason/before-after for profile/register changes. Family history/important notes require clinical-edit permission and clinical-view access to their correction history. |
| PatientDuplicateReview / PatientMerge | Ordered pair/reviewer/decision; immutable explicit merge manifest with original ownership/content/team/adjustments. |

Mutable register records retain creator/updater/times and active/retired actor/time/reason. Edits/retirement need reason; unknown fields/invalid links/choices/dates rejected. Lock parent and advance its version. Terminal follow-up outcome cannot be replaced/reopened; identical visit outcome is a no-op. Visit-owned bridge date/status/evidence/reason is writable only through visit; new scheduling retires old terminal occurrence, pending clears evidence, bridge writes advance parent version. Extra actions remain independent; reports count without double-counting the bridge.

## Patient API and reconciliation

Under `/patients/{id}/`:

| Endpoint | Contract |
| --- | --- |
| `records/` GET | `kind`, offset; identifiers/contacts/representatives/allergies/medications/follow-ups → `{items,total,version}`, 100/page including retired history. |
| `records/` POST | `{kind,record_id?,operation:save/retire,fields,reason,version}` → `{record,version}` using opening patient version. |
| `corrections/` GET | Offset, `{items,total,merges}`; 100 corrections/page/latest 100 merges, original merged-source history retained. Clinical changes require clinical-view permission. |
| `duplicate_review/` POST | `{other_id,status:dismissed/different,reason,version}`; review is optional/dismissible and matches can be shown again. |
| `merge_preview/`, `merge/` POST | Source URL, target ID → token; execute token/reason/source+target versions. Admin with edit/archive permissions, explicit consent; preview 10 minutes, binds actor/both versions/source content/team/access impact. |
| Care team / documents | `team_candidates/` minimal eligible users; team writes use patient version/removal reason, documents use their own opening version. |

Merge locks parents in stable order and rejects changed preview. Active survivor demographics remain; current records/visits/appointments/invoices/documents move, teams explicitly combine, duplicate active identifier tuples transfer retired, source primary contacts transfer nonprimary. Access broadening/history stays visible; source archives and links to survivor, merged source restoration is blocked. Signed revisions/issued bytes and immutable original ownership never rewrite. No automatic merge/undo contract.

## Encounters, documents and operations

Visit owns working encounter narrative, diagnoses/medications/labs/scales and attachments. Draft/final/amended/locked transitions use versions/reasons. Final signing creates immutable schema-v2 `VisitRevision`: identity/file number, longitudinal summaries/records, clinician/time, clinical rows/labs, scale definitions/answers and attachment inventory. Catalog retirement cannot erase saved labels/controlled flags or scale snapshots. Scores/defaults must be finite, ranged and absolutely step-aligned; new active scales max 100 questions.

`IssuedDocument` retains exact PDF/checksum/revision/actor/snapshot/signature/stamp; prescription/referral require final/locked signed revision and block unsigned amendment issuance. Final persistence locks parent/visit, checks scope, visit/revision and preview patient version. History GET `/visits/{id}/revisions/` and `issued-documents/` is read-only. General patient/visit exports read current facts; working copies are labelled unapproved and suppress old signing metadata. Clinical unknowns remain distinct from false/zero: care setting and unknown/voluntary/involuntary `care_basis` are separate.

Optional prescription POST `print_options` selects `mode: blank/preprinted`, `width_mm` (80–216), `height_mm` (120–350), and `offset_x_mm`/`offset_y_mm` (−5…5, positive right/down); finite values have at most two decimals. A6 (105×148) is the UI/default-options size; omitted options retain the legacy A4 API renderer. Blank offsets normalize to zero. The issued snapshot retains normalized options and issue date alongside exact PDF bytes. Preprinted output excludes the reference artwork, repeats patient fields/signature/date on additional sheets, and rejects fields/instructions too large to fit; it never silently truncates them. Current address is bound by the preview patient version. All layouts repeat patient identification on continuation pages; preprinted sheets include page/total numbering. POST `/prescription/calibration/` requires authentication/export permission and accepts only paper settings for a patient-free PDF with physical alignment crosses and a 50 mm ruler; it neither issues a clinical document nor consumes a visit preview.

Prescription history GET `/prescription/patient/{id}/history/` returns `{items,total,offset,limit}` (20/page), newest first; optional `visit_id` must belong to that patient. GET `/prescription/documents/{id}/pdf/` returns the exact retained bytes/checksum; `/instructions/` renders a separate A4 patient handout from the issued snapshot without modifying it or issuing another document. All three require current clinical-view/export grants and shared patient/visit scope, accept prescription documents only, and return `Cache-Control: no-store`. Existing copies remain readable during an amendment; revoked access is rechecked on every read. Handouts reproduce free-text directions without parsing a schedule or inferring duration.

| Area / source | Current policy |
| --- | --- |
| Appointments | Active doctor/admin under locked eligibility; overlapping intervals/working hours validated, configured default duration, completed booking cannot move. Reopen/reschedule rechecks occupancy/eligibility; next shortcut uses authorized schedule and future local time. Historical inactive-clinician appointments retained. |
| Billing | Default SYP; finite bounded two-place decimals/half-up rounding, same-patient active visit, immutable material details after issue/payment. Single full-payment lifecycle; no inferred partial payment/refund/conversion. Paid reconciliation groups by currency. |
| Tasks/notifications | Actor-aware assignment, reasoned terminal/reopen transitions and guarded deletion; reorder locks stable IDs (last-write-wins order). Reminders use occurrence UUIDs, stable on retries/normal progress and renewed on reopen/schedule/assignee changes; read history retained. |
| Reporting | High-risk patients use latest approved revision, including last approval during amendment. Current assigned patients use dated team, treated patients/visit counts use authors and user IDs. Unknown average age is null; general visit counts intentionally include drafts. |
| Import/export | UTF-8 CSV/XLSX, bounded parsing, explicit maps, row outcomes and formula/text-cell protection across metadata sheets. Preview binds file/options/current catalog inventory; merge/replacement rejects intervening changes, invalid/empty replacement cannot retire lists. Medication import is content-only, not full status/controlled recovery. |

## Retention and completed review

Archive retains clinical/profile/team/document/action history; new operational writes require active parents. Draft deletion soft-archives bridge; finalized history cannot be deleted ordinarily. Pseudonymization clears mutable identity/registers but signed snapshots/corrections/merge/audit can still identify the person: it is not complete erasure. No automatic patient purge duration introduced. Full authenticated ZIP recovery is distinct from catalog merge; raw validated restore deliberately bypasses ordinary ORM history guards.

All R1–R29 source findings from 2026-10-12 are closed; this contract replaces their pending prose and duplicate implementation inventories:

| IDs | Corrected boundary / primary sources |
| --- | --- |
| R1/R6/R13 | Approved risk, author/team attribution, currency totals; `apps/reports/` and frontend reports. |
| R2–R5/R7/R19/R20 | Terminal/bridge/completion/summary policy, active operational scope, complete identifier tuple, canonical contacts; patient/visit services. |
| R8/R9/R28 | Post-lock access and final issuance freshness/strict versions/typed reason; visit, prescription and referral services/views. |
| R10–R12/R24–R26/R29 | Authorized replay, atomic reservations/receipts/expiry, restored-principal separation, exclusive gate and correct commit/media/cache boundary; `core/{middleware,replay,models,cache_utils,operation_gate}.py`, backup services/views. |
| R14–R18 | Spreadsheet text safety, clinician eligibility/future shortcut, scale bounds/absolute alignment; export/appointment/clinical/scale-validation sources. |
| R21/R22/R23/R27 | Occurrence delivery, bounded late reminders/poll cadence, no raw DEBUG media and inventory-bound catalog preview; jobs/signals/URL/import services. |

Related choices retained service architecture and immutable bytes; future dated scope, clinical narrative history, account locking, unknown age/default duration and atomic bounded backups were corrected. Exchange conversion, partial-payment/reassignment features, DB triggers and a general staged-upload protocol were not added. Original 27/second-pass corrections are completion history, not reopened findings. New schema, real deployment concurrency, HTTP and rendered checks remain in [current](workCurrent.md).
