# Critical workflow release checklist

Before each release, run on clean and production-like databases; record build identifier/tester/clinic timezone/browser/result per line.

## Preconditions

- Demo data disabled; timezone visible/known.
- Admin/doctor/receptionist accounts match intended role matrix.
- Backup destination has sufficient space.
- Browser devtools show no failed API requests before starting.

## End-to-end workflow

1. **Login and session** — sign in; verify visible identity/permissions, dirty-form expiry warning, and clear expired/revoked-session return to login.
2. **Patient** — Arabic-variant search; create complete patient, check identifier/phone duplicate feedback, reopen; audit includes actor/time/changed fields.
3. **Appointment** — schedule; reject overlaps in form/API; scheduled → confirmed → arrived → completed. Calendar/dashboard/patient page agree on state/time.
4. **Visit** — incomplete draft → refresh/recover → complete required fields → finalize → reject direct edits → reasoned amendment → re-finalize → lock.
5. **Prescription/referral** — draft generation blocked; generate both from final visit, verify patient/visit/clinician/instructions/version/Arabic layout/audit.
6. **Invoice** — compare draft UI/backend totals; issue/pay; reject material edits/deletion; dashboard/report totals exclude drafts/cancellations as documented.
7. **Export** — apply list/report filters, export every supported format; rows/columns match visible scope; generation time/timezone/audit present.
8. **Backup** — create full backup; record SHA-256 response header, inspect manifest, open archive without errors.
9. **Restore** — clean environment: preview counts/version/media impact, exact confirmation phrase, restore, verify automatic safety backup; repeat steps 2–7 on restored data.

## Cross-role and failure checks

- Repeat protected API reads/writes per role; hidden UI controls do not prove permission enforcement.
- Submit stale `version` for patient/appointment/visit/task/invoice edits; expect 409 with recovery guidance.
- Disconnect during save: no false success; reconnect/retry without duplicates.
- Cancelled/no-show appointments and completed/cancelled tasks must stop reminders.
- Archived patients unavailable for new appointments/visits/invoices; readable in authorized history/explicitly included exports.

## Release sign-off

Release requires every critical step passing or documented owner-approved exceptions. Attach results/reconciliation totals/backup checksum/exceptions to release record.
