# Remaining work

[Current behavior](contracts.md) · [Dated evidence and limits](doneCurrent.md) · [Frontend work](../../frontend/docs/workCurrent.md).

1. Review-fix implementation is source-complete. When separately authorized, verify session activity/expiry, referenced file replay/cleanup, recovery/process failures, collection compatibility and HTTP/proxy/bundle serving with the coordinated frontend. The [remaining logic corrections](doneCurrent.md#logic-review-corrections-2026-11-18) also need isolated runtime checks for upload limits, backup retention, XLSX patient dates, catalog usage-count exports, seed-setting preservation and approved dashboard risk. Tests/builds were expressly excluded; see [source evidence](doneCurrent.md#review-fixes-and-contract-handoff-2026-11-18). No clinic-storage operation is authorized by these follow-ups.

2. Run the new [GitHub workflows](automation.md) after both repositories are pushed. Verify static validation, download caches, summaries, Dependabot action updates, Windows/downloaded archives, scheduled checks, compatibility/audit jobs and manual draft preparation with an existing matching tag; production topology remains separate. [Workflow maintenance evidence](doneCurrent.md#workflow-maintenance-2026-11-18) is source-only. Local Linux evidence is in [completed work](doneCurrent.md#github-workflows-and-linux-bundle-2026-11-17).
3. Confirm supported currencies/precision and quantity limits; current billing uses two-place half-up arithmetic and full payments.
4. Check consumer-specific spreadsheet/PDF exports and calibrate actual prescription stock/printer at 100%.
5. Broaden UI widths/zoom/long text, accessibility and browser engines; verify native Windows downloads/printing if targeted.
6. Requirements-dependent extensions: lab trends; medication strength/form/route; versioned scales/typed answers; locations/timezones/resources; payment/refund ledger; retained invoice PDFs.
7. Review the pdfkit dependency advisory `PYSEC-2026-2860`; dependency removal/version changes need separate authorization.

The authorized fresh local setup is complete. Existing-database upgrades and deployment validation remain outside scope; ordinary startup never grants either scope.
