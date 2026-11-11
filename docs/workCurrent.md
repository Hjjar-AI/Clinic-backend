# Remaining work — priority order

Local launch on Python 3.14.4/Django 6.1.2 is now verified; the earlier environment blocker is resolved. [Scope and evidence](doneCurrent.md#python-314-compatibility-and-launch-2026-11-11).

**Existing-database blocker (2026-11-11):** the user's login traceback and read-only schema inventory confirm two missing current model tables and twelve missing columns. Login fails on `core_cachegeneration`; adding that table alone cannot reconcile the remaining differences. Data-preserving schema repair requires explicit new authorization; none has been performed. [Inventory and limits](doneCurrent.md#existing-database-login-failure-2026-11-11).

1. Confirm supported currencies/precision and quantity limits; current billing uses two-place half-up arithmetic and full payments.
2. Check consumer-specific spreadsheet/PDF exports and calibrate actual prescription stock/printer at 100%.
3. Broaden UI widths/zoom/long text, accessibility and browser engines; verify native Windows downloads/printing if targeted. [Frontend](../../frontend/docs/workCurrent.md).
4. Requirements-dependent extensions: lab trends; medication strength/form/route; versioned scales/typed answers; locations/timezones/resources; payment/refund ledger; retained invoice PDFs.
5. With explicit test-suite authorization, repeat broader clinical/API/PostgreSQL regression checks on the updated dependency profile. Historical [suite evidence](doneCurrent.md) uses Python 3.12/Django 5.0; the new runtime currently has focused probes and real launch/HTTP/shutdown evidence only.

Schema preparation and deployment validation were removed from scope by request. Completed fixes/checks and unperformed limits: [evidence](doneCurrent.md).
