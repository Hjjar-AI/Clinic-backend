# Critical workflow release checklist

Run this checklist against a clean database and a production-like database before every release. Record the build identifier, tester, clinic timezone, browser, and result for every line.

## Preconditions

- Demo data is disabled and the configured timezone is visible/known.
- Test admin, doctor, and receptionist accounts exist with the intended role matrix.
- A backup destination with sufficient free space is available.
- Browser developer tools show no failed API requests before the workflow starts.

## End-to-end workflow

1. **Login and session** — sign in, verify the visible identity and permissions, leave a dirty form open, verify the expiry warning, and verify an expired/revoked session returns to login with a clear message.
2. **Patient** — search using Arabic spelling variants, create a complete patient, verify duplicate feedback using the same identifier/phone, reopen the record, and confirm the audit entry has actor, time, and changed fields.
3. **Appointment** — create a scheduled appointment, verify overlap rejection in the form and API, then transition scheduled → confirmed → arrived → completed. Verify calendar, dashboard, and patient page show the same state and time.
4. **Visit** — create an incomplete draft, refresh and recover it, complete required clinical fields, finalize it, verify direct editing is blocked, open an amendment with a reason, finalize again, and lock it.
5. **Prescription/referral** — verify generation is blocked for a draft visit. Generate both from the finalized visit and verify patient, visit, clinician, medication instructions, version, Arabic layout, and audit events.
6. **Invoice** — create a draft and compare the UI preview with the backend total. Issue it, mark it paid, verify material edits/deletion are blocked, and confirm dashboard/report totals exclude drafts and cancelled invoices as documented.
7. **Export** — apply list/report filters, export each supported format, verify the rows and columns match the visible filter scope, and confirm generation time/timezone plus an audit event are present.
8. **Backup** — create a full backup, record its SHA-256 response header, inspect its manifest, and verify the archive opens without errors.
9. **Restore** — in a clean environment, preview the backup, verify counts/version/media impact, enter the exact confirmation phrase, restore, and verify the automatic safety backup was created. Re-run steps 2–7 against restored data.

## Cross-role and failure checks

- Repeat protected reads and writes as each role by calling the API directly; a hidden frontend control is not considered a permission test.
- During patient, appointment, visit, task, and invoice editing, submit an older `version` and verify a 409 conflict with recovery guidance.
- Disconnect the network during a save and verify the operation is not reported as successful; reconnect and ensure a retry does not create a duplicate.
- Verify cancelled/no-show appointments and completed/cancelled tasks stop producing reminders.
- Verify archived patients cannot be selected for new appointments, visits, or invoices but remain readable in authorized history and exports where explicitly included.

## Release sign-off

Release only when every critical step passes or has a documented owner-approved exception. Attach the checklist result, reconciliation totals, backup checksum, and any exceptions to the release record.
