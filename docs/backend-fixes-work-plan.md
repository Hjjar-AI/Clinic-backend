# Backend review fixes

Authorized: all backend-models-logic-review.md findings; no migrations/test-suite access/builds/compilation/packaging/dependency-version changes.

- [x] Clinical validation, immutable revisions and issued documents
- [x] Complete authenticated backups and recoverable restore
- [x] Shared access rules, durable authentication state and idempotency
- [x] Versioned archival, follow-ups, files and lifecycle invariants
- [x] Consistent appointments, invoices, catalog writes and settings
- [x] Imports, reports, exports, reminders and cache correctness
- [x] Focused verification and final implementation notes

Decisions: historical-author access; care-team patient scope plus action permissions; unchanged receptionist defaults; final/locked document issuance; pending labs without fabricated results; single full payments with actor/time; distinct full/catalog recovery; archive preserves clinical data, identity restriction means pseudonymization.

Implemented details and validation: [backend-fixes-implementation.md](backend-fixes-implementation.md).

Performed none of the excluded work or project DB operations. Verification: isolated in-memory SQLite/temporary scripts and dependencies under `/tmp`.
