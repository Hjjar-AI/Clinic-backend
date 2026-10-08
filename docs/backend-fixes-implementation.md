# Backend review fixes — implementation record

Completed 2026-10-07: all 27 [original review](backend-models-logic-review.md) findings.

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

## Verification

Checks used temporary scripts/new in-memory SQLite via Django schema editor; no project DB opening/migration/clearing/population.

- Python source syntax and Django model system checks passed, excluding migration and test-suite paths.
- Verified pinned Django 5.0.6/DRF 3.15.1 installed only in `/tmp`; project requirements/versions unchanged.
- Real HTTP checks with CSRF and `ATOMIC_REQUESTS` enabled passed: login CSRF, persistent failed counters, forced-password gate, idempotent success replay, request digest conflicts, stale-write conflicts, catalog If-Match, settings, JSON backup and multipart replay across different boundaries.
- Persistence probes passed: visit signing/amendment history, catalog snapshot stability, finite/off-step/retired scale rejection, pending/null lab behavior, structured JSON, attachment verified metadata and signed-state guards, follow-up outcomes, care-team scope, appointment filters/duration alias and after-commit cache generations.
- JSON and full ZIP round trips passed with invoice lines/payments, revisions, media, authentication group/permission memberships and exact issued-document bytes. Modified archive media was rejected.
- Import preview/execution parity, shared phone handling, empty replacement protection and explicit old date ranges with zero-filled months passed.
- Parser-only JavaScript checks passed for changed JS/Vue script sections. No frontend build or compilation was run.

Unverified: PDF layout/rendering, browser interaction, PostgreSQL/concurrent writers. Probe runtime: Python 3.14; not proof every pinned dependency supports it. Migration generation/schema application remain excluded as requested.

Second-pass findings and verification: [backend-second-pass.md](backend-second-pass.md).
