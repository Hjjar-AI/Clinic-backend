# Backend review fixes

Authorized: fix all findings in backend-models-logic-review.md. No migrations, test-suite access, builds, compilation, packaging, or dependency version changes.

- [x] Clinical validation, immutable revisions and issued documents
- [x] Complete authenticated backups and recoverable restore
- [x] Shared access rules, durable authentication state and idempotency
- [x] Versioned archival, follow-ups, files and lifecycle invariants
- [x] Consistent appointments, invoices, catalog writes and settings
- [x] Imports, reports, exports, reminders and cache correctness
- [x] Focused verification and final implementation notes

Implementation decisions: preserve author access to historical visits; care-team members inherit patient scope but still need action permissions; keep the current receptionist permission defaults; only final/locked visits can issue documents; allow pending labs without inventing results; keep single full invoice payments with recorded actor/time; distinguish full recovery from selective catalog restore; archival preserves clinical data and identity restriction is explicitly pseudonymization.


Implemented details and validation: [backend-fixes-implementation.md](backend-fixes-implementation.md).

No migrations, test-suite files, builds, compilation, packaging, project dependency changes, or project database operations were performed. Temporary scripts used an isolated in-memory SQLite schema and temporary dependency installations under `/tmp`.
