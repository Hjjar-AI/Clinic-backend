# Remaining work

[Current behavior](contracts.md) · [Dated evidence and limits](doneCurrent.md) · [Frontend work](../../frontend/docs/workCurrent.md).

1. Run the new GitHub checks and manual bundle workflow after both repositories are pushed. Verify the Windows runner, downloaded Windows/Linux archives and the intended production topology; local Linux evidence is in [completed work](doneCurrent.md#github-workflows-and-linux-bundle-2026-11-17).
2. Confirm supported currencies/precision and quantity limits; current billing uses two-place half-up arithmetic and full payments.
3. Check consumer-specific spreadsheet/PDF exports and calibrate actual prescription stock/printer at 100%.
4. Broaden UI widths/zoom/long text, accessibility and browser engines; verify native Windows downloads/printing if targeted.
5. Requirements-dependent extensions: lab trends; medication strength/form/route; versioned scales/typed answers; locations/timezones/resources; payment/refund ledger; retained invoice PDFs.

The authorized fresh local setup is complete. Existing-database upgrades and deployment validation remain outside scope; ordinary startup never grants either scope.
