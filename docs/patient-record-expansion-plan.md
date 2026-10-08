# Patient record expansion

Authorized 2026-10-08: implement accepted patient schema/workflows across backend/frontend; no migrations, test-suite access, builds, dependency/version changes or project-data operations.

Decisions: birth year remains primary (unknown nullable); clinic registration replaces admission terminology; care-team memberships own assignment/access, with dated membership history. Keep literal identifiers unchanged; permanent patient numbers distinguish duplicates, archived/active duplicate warnings are dismissible, merge is optional and explicit. Preserve signed snapshots/issued documents.

Completed: (1) core identity/preferences/completeness and normalized optional fields; (2) structured identifiers, contacts, representatives, allergies/ongoing medications and correction history; (3) dated team membership and access; (4) optional duplicate review and preview-bound merge; (5) multiple follow-up actions and unknown/care-setting semantics; (6) document provenance, imports/exports/recovery contracts; (7) frontend forms/patient tabs/actions; (8) isolated probes/source checks and retention/handoff documentation.

Verification must distinguish source/isolated SQLite checks from unavailable pinned HTTP/browser/PostgreSQL checks. Prior work preserved. Final contracts: [schema and retention](patient-record-schema.md); [implementation/verification](patient-record-verification.md).
