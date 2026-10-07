# Backend review fixes — implementation record

Completed 2026-10-07 for the 27 findings in [the original review](backend-models-logic-review.md).

## Changes by finding

| Finding | Implemented change |
| --- | --- |
| 1 | Shared canonical JSON/HMAC payload serialization and verification. |
| 2–3 | Full managed application/auth/content-type/audit inventory, archived records, original IDs/timestamps, labs, signed ZIP manifest, per-member checksums, bounded archives, reference validation, complete logical recovery and media compensation. Catalog-only restore merges without replacing clinical history. |
| 4 | Append-only `VisitRevision` snapshots at signing and amendment completion; reason, signer, time, patient identity, clinical rows, labs, scale definitions/answers, attachment inventory. |
| 5 | Server-authorized signing; append-only `IssuedDocument` with exact issued bytes, checksum, revision, actor, snapshot, signature/stamp; referral issuance uses POST. Issuance locks and rechecks visit version/state. |
| 6–7 | Bounded typed clinical JSON and row normalization before replacement; valid references, lengths, null handling and final-section validation; pending labs do not need fabricated values. |
| 8 | Finite numeric scores, valid steps, required answers, retired-definition restrictions and persisted validated field defaults. |
| 9 | Self-contained diagnosis/medication snapshots, including controlled classification; document content reads finalized revisions. |
| 10 | Shared patient/visit/appointment/invoice scope; care-team access and historical author access; permission-filtered dashboard sections; clinical patient subresources require visit permission. |
| 11–12 | Login outside request-wide transactions, durable failed counters, anonymous-login CSRF, dummy hashing, server-controlled password-change gate, effective-permission reporting, versioned password changes and role groups seeded only on creation. |
| 13 | Versioned follow-up outcomes, actor and time; overdue bulk closure records missed follow-ups; new due dates reset completion. |
| 14 | Locked/versioned destructive actions, archived-state rechecks, archive metadata, explicit patient archive/restore, preserved dependent history and active-parent checks for new records. |
| 15 | Durable idempotency records, canonical request digest, saved successful response replay, multipart boundary-independent fingerprints, expanded endpoint coverage and retained frontend operation keys after uncertain network failures. |
| 16 | Cache invalidation after commit, captured generation publication, random generation tokens and protected previews/idempotency records during general cache clearing. |
| 17 | Canonical appointment duration, validation for inactive schedules, reminder reset, datetime overlap intervals including the prior day, consistent duration bounds and scoped calendar filters. |
| 18 | `InvoiceLine`, server-derived totals, explicit currency, two-decimal half-up rounding, paid actor/time, payment method supplied on payment, immutable issue identity/clinic snapshot and itemized PDF context. Legacy total-only clients receive one service line. |
| 19–20 | Protected historical parent relationships; patient archive keeps dependencies; identity restriction explicitly preserves signed history and is described as pseudonymization rather than complete anonymization. |
| 21 | Authoritative explicit report periods, empty month filling, period-aware visit average, stable concept grouping with saved labels, latest-assessment risk and validated summary dates. |
| 22 | Clinic-local business dates, reminder catch-up windows across midnight, occurrence-specific dedupe, updated timestamps and suppression of empty audit updates. |
| 23 | Shared preview/execution parsers for CSV/XLSX, no truncation, national-ID duplicate rules, phone warnings, mapping/policy-bound medication preview, validated row outcomes and guarded replacement. |
| 24 | Canonical catalog persistence, versioned catalogs/scales/templates/settings, dedicated retirement/reactivation, writable ordering/controlled flags and normalized medication identity constraint. |
| 25 | Visit serializers delegate to services; database enum/version/range constraints; audited task reorder and canonical reactivation; validated demo records are signed through the normal service. |
| 26 | Attachments require editable visit state and expected version; verified MIME/size/checksum, cleanup on persistence failure, retained signed inventory and media recovery. `reconcile_media` reports missing/old orphaned uploads and deletes only with explicit `--delete`. |
| 27 | Spreadsheet text-cell protection, validated export columns, canonical clinical JSON export mapping, atomic bounded settings updates and correctly stored demo labs. |

## Deliberate behavior and API contracts

- Clinical revisions and issued documents reject ordinary ORM instance and QuerySet changes/deletion. The validated full-recovery loader is an explicit exception using raw serialization/database operations.
- Doctors retain patient scope through authored visits; care-team membership grants record scope. Endpoint action permissions remain required. Existing receptionist default permissions remain unchanged.
- Prescriptions and referrals require a final/locked visit with a signed revision. Opening an amendment blocks issuance until re-signing. Prescription previews are bound to visit, patient version and template.
- Mutations accept an observed `version`, or `If-Match` where provided by the shared parser. Frontend editors preserve their opening version; action calls can use the last observed resource version.
- `GET /visits/<id>/revisions/` and `GET /visits/<id>/issued-documents/` expose authorized history without mutation endpoints.
- Patient archive/restore are explicit POST actions. Archive preserves linked records. Pseudonymization retains signed identity snapshots, narratives, audit history and historical access.
- Follow-up `completed`, `missed`, `cancelled`, and `waived` outcomes are distinct. Bulk overdue closure means missed; cancelled/waived follow-ups do not count as completed adherence.
- Billing supports a single full payment. Currency defaults to SYP; amounts use two decimal places with half-up rounding. Partial payments, refunds and credit-note workflows were not inferred as requirements.
- Scheduling retains the existing working-hour policy. Historical dates remain allowed; completed appointments cannot move; arrived appointments follow the existing editable-schedule rule.
- Restore preview binds file digest and selected scope. Full patient recovery requires the entire related dataset and revokes sessions. Catalog-only recovery preserves clinical records and current users.
- Full ZIP is the portable recovery artifact. JSON contains all logical records but no file bytes; full recovery rejects missing referenced files. Incomplete legacy backup schemas are rejected before mutation rather than risking partial recovery. The installation must retain its backup HMAC key.
- Imports explicitly support CSV UTF-8 and XLSX. Formula cells must be converted to values. Invalid/empty replacement files cannot retire the catalog.

## Verification

All checks used temporary scripts and a new in-memory SQLite schema created directly with Django's schema editor. No project database was opened, migrated, cleared or populated.

- Python source syntax and Django model system checks passed, excluding migration and test-suite paths.
- Verification passed against the project's pinned Django 5.0.6 and DRF 3.15.1, installed only under `/tmp`. Project requirements and dependency versions were unchanged.
- Real HTTP checks with CSRF and `ATOMIC_REQUESTS` enabled passed: login CSRF, persistent failed counters, forced-password gate, idempotent success replay, request digest conflicts, stale-write conflicts, catalog If-Match, settings, JSON backup and multipart replay across different boundaries.
- Persistence probes passed: visit signing/amendment history, catalog snapshot stability, finite/off-step/retired scale rejection, pending/null lab behavior, structured JSON, attachment verified metadata and signed-state guards, follow-up outcomes, care-team scope, appointment filters/duration alias and after-commit cache generations.
- JSON and full ZIP round trips passed with invoice lines/payments, revisions, media, authentication group/permission memberships and exact issued-document bytes. Modified archive media was rejected.
- Import preview/execution parity, shared phone handling, empty replacement protection and explicit old date ranges with zero-filled months passed.
- Parser-only JavaScript checks passed for changed JS/Vue script sections. No frontend build or compilation was run.

Material validation limits: PDF layout/rendering, browser interaction and PostgreSQL/concurrent-writer behavior were not exercised. The runtime available for probes was Python 3.14; these probes do not establish compatibility for every pinned dependency on that interpreter. Migration generation and schema application remain outside this task, as requested.
