# Backend review fixes

Authorized: fix all findings in backend-models-logic-review.md. No migrations, test-suite access, builds, compilation, packaging, or dependency version changes.

- [ ] Clinical validation, immutable revisions and issued documents
- [ ] Complete authenticated backups and recoverable restore
- [ ] Shared access rules, durable authentication state and idempotency
- [ ] Versioned archival, follow-ups, files and lifecycle invariants
- [ ] Consistent appointments, invoices, catalog writes and settings
- [ ] Imports, reports, exports, reminders and cache correctness
- [ ] Focused verification and final implementation notes

Implementation decisions: preserve author access to historical visits; care-team members inherit patient scope but still need action permissions; keep the current receptionist permission defaults; only final/locked visits can issue documents; allow pending labs without inventing results; keep single full invoice payments with recorded actor/time; distinguish full recovery from selective catalog restore; archival preserves clinical data and identity restriction is explicitly pseudonymization.
