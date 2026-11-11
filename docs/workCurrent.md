# Remaining work — priority order

Local launch on Python 3.14.4/Django 6.1.2 is now verified; the earlier environment blocker is resolved. [Scope and evidence](doneCurrent.md#python-314-compatibility-and-launch-2026-11-11).

Fresh local database setup was subsequently authorized and completed on **2026-11-11**. Current tables/columns, database integrity and real admin login/logout pass; no demo patients were created. The missing-file blocker is resolved. [Fresh-setup evidence](doneCurrent.md#authorized-fresh-database-2026-11-11). Earlier storage findings describe the discarded database, not the fresh one.

1. Confirm supported currencies/precision and quantity limits; current billing uses two-place half-up arithmetic and full payments.
2. Check consumer-specific spreadsheet/PDF exports and calibrate actual prescription stock/printer at 100%.
3. Broaden UI widths/zoom/long text, accessibility and browser engines; verify native Windows downloads/printing if targeted. [Frontend](../../frontend/docs/workCurrent.md).
4. Requirements-dependent extensions: lab trends; medication strength/form/route; versioned scales/typed answers; locations/timezones/resources; payment/refund ledger; retained invoice PDFs.
5. With explicit test-suite authorization, repeat broader clinical/API/PostgreSQL regression checks on the updated dependency profile. Historical [suite evidence](doneCurrent.md) uses Python 3.12/Django 5.0; the new runtime currently has focused probes and real launch/HTTP/shutdown evidence only.

Fresh local schema/account setup was explicitly authorized and completed later; broader existing-database upgrades and deployment validation remain outside scope. Completed fixes/checks and unperformed limits: [evidence](doneCurrent.md).
