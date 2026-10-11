# PDF appearance and full browser workflows

Verified 2026-10-11 with synthetic records only. This follows the [earlier suite expansion](testing.md); historical results remain in the completed handoffs.

## Results

| Suite | Passed |
| --- | ---: |
| Backend service/HTTP/recovery | 174 |
| Frontend Node service/state | 110 |
| Vue DOM/import | 77 |
| Chromium, desktop/tablet/mobile | 60 |
| Separate PDF appearance inspector | 6 |

The complete browser matrix passed in 9.1 minutes with zero retries. A focused three-viewport rerun additionally verified the final loaded-Cairo/computed-font assertions in print mode. Runtime: Python 3.14.4, Django 5.2.9, DRF 3.15.1, WeasyPrint 70, Node 24.21.0, Chromium 156. Optional PyMuPDF 1.28.2 was installed only in the disposable test environment. Project versions, requirements and lockfiles were preserved. No production build, migration inspection/change or clinic database/media/backup access was performed.

## Complete browser scenarios

`frontend/tests/e2e/clinical-workflows.spec.js` adds five scenarios; `zz-full-recovery.spec.js` adds one. Each runs in all three viewports, adding 18 cases to the previous 42. The tests use ordinary UI interactions and the real Django API; API requests prepare synthetic fixtures and independently inspect persisted outcomes.

- Appointment booking uses the actual availability picker; the booked slot becomes unavailable, editing retains the current slot, rescheduling changes time and version, and reload succeeds.
- Visit creation preserves unassessed clinical risks, saves without a dirty-navigation prompt, signs, opens a reasoned amendment, updates and resigns. Both immutable revisions are retained. Prescription issuance draws/saves a signature through the actual control. Referral issuance supplies the reason through its form. Both issued document types are verified; prescription/referral/patient/visit PDFs are downloaded.
- Invoice creation submits fractional values through native input validation, computes 9.50 SYP, issues and pays by card, and retains amount/method/actor/time. A paid invoice rejects material changes; its PDF downloads and payment persists after reload.
- Patient imports upload CSV, preview valid/invalid rows before any write, optionally assign a doctor, preserve unknown and year-only birth, commit the valid records and follow the patient-list link.
- Medication imports map all five columns, preview before writes, confirm and verify the resulting catalog entry.
- Full ZIP recovery downloads a genuine authenticated archive, validates its digest, changes synthetic inventory, uploads/previews the archive, enters the exact phrase and execution consent, and restores. A safety-backup filename is returned, the old session loses access and relogin works. Signed revisions, issued checksum, paid actor/timestamp and media bytes survive exactly; post-backup records disappear and archived media returns in the UI.

## PDF and print checks

`backend/tests/pdf_appearance.py` deliberately runs separately from ORM tests and prohibits database access through `SimpleTestCase`. Five actual templates render long Arabic/Latin synthetic fixtures: 45 prescription medications, 45 invoice lines, a long referral, three long patient visits and a long visit with a medication table. The sixth case inspects all **18 PDFs retained by browser workflows**: prescription, referral, patient, visit, invoice and browser-printed referral for each viewport.

Assertions check A4 geometry, multipage stress output, nonblank/non-heading-only pages, text inside page bounds, Arabic text/glyphs, embedded font resources, valid text mapping, medication/invoice row retention, repeated prescription headers, complete decimal amounts, invoice totals and referral closing text. Chromium embeds variable-font outlines as PDF Type3 `CharProcs`; those embedded resources are checked instead of requiring a TrueType program. Browser assertions separately verify Cairo has loaded, the body uses Cairo, print mode hides application chrome and editable controls, and the referral text remains visible.

Manual review used rendered PNGs of first/second/final pages and actual downloads. Arabic letters are joined/readable, dates/doses and numeric columns remain legible, long sections flow across pages, table headers repeat and the clinical print content fits A4. This is review of the exercised samples, not exhaustive visual certification for every possible input or physical printer.

## Confirmed defects and corrections

| Location | Observed failure and correction |
| --- | --- |
| `core/pdf_utils.py` and five PDF templates | Reliance on system fonts produced inconsistent output. Load bundled Cairo/Inter locally with the same WeasyPrint font configuration, embed the fonts and apply them to page footers. Use explicit bidirectional isolation for dates/phone/IDs/doses/amounts. Invoice numeric cells no longer split decimals; long visit/patient containers paginate instead of leaving heading-only pages. |
| `apps/backup/backup_creator.py` | Django's default JSON encoder truncated datetime microseconds, changing signed and paid timestamps after full recovery. The backup-specific encoder retains complete ISO precision; a deterministic microsecond regression covers the signed snapshot. |
| `frontend/src/features/visits/composables/useVisitForm.js` | Untouched nullable risk controls caused API rejection. Serialize them to the existing blank/unknown choice, preserving explicit negative findings; mark successful saves clean before navigation. |
| `frontend/src/components/ui/BaseButton.vue` | Null href overwrote RouterLink's target; missing native event broke invoice PDF `@click.stop`. Bind href only for anchors and forward the click event. |
| `frontend/src/components/ui/FormInput.vue` | Step landed on a wrapper, leaving native number fields restricted to integers. Bind step to the actual input; regressions exercise decimal native validity. |
| `frontend/src/components/ui/SignaturePad.vue` | Saved SVG markup failed the backend's validated PNG/JPEG contract. Rasterize the same collected strokes into a transparent PNG data URL. |
| `frontend/src/features/billing/views/InvoiceForm.vue`, `InvoicesList.vue` | Currency display defaulted to Saudi riyals for SYP invoices. Format using the invoice's currency and initialize new invoices consistently with the existing SYP backend default. |

Existing endpoint authorization, expected versions, idempotency, signed revision/document retention, import preview binding and full-recovery confirmation remain in force.

## Repeatable commands and retained review output

Run the ordinary suites with the commands in [backend testing](testing.md) and [frontend testing](../../frontend/docs/testing.md). To retain browser PDFs and inspect them:

```bash
# From frontend, with backend dependencies and Chromium already installed:
CLINIC_PDF_ARTIFACT_DIR=/tmp/clinic-browser-pdfs pnpm test:e2e

# From backend, in an isolated test environment containing optional PyMuPDF:
python -B tests/pdf_appearance.py --output /tmp/clinic-pdf-review \
  --downloads /tmp/clinic-browser-pdfs
```

The inspector also requires fontTools, available with the PDF runtime. It does not add either package to pinned application requirements. Without `--downloads`, it explicitly skips the browser-artifact check; a complete run must supply downloads for all three projects.

This session's artifacts are in `/tmp/clinic-document-review/downloads` and `/tmp/clinic-document-review/stress` (PDFs, PNG review pages and JSON page/font summaries). They contain synthetic data and are temporary. Read-only dependency directories required temporary Vite/Playwright config extensions and caches in `/tmp`; the runs still exercised the actual workspace sources.

The PDF renderer resolves `Cairo-VariableFont_slnt,wght.ttf` and `Inter-VariableFont_opsz,wght.ttf` together from the sibling frontend's `public/static/fonts`, `dist/static/fonts` or `dist/fonts`. A Django `PDF_FONT_DIR` setting can point to a deployed directory containing both. Missing assets follow the existing renderer-failure path instead of silently replacing the requested typography. Issued historical PDF bytes remain unchanged.

## Remaining limits

Pinned Django/DRF still needs a supported-Python run. SQLite tests do not verify PostgreSQL concurrent writers/locking. Firefox/WebKit, physical printers, exhaustive accessibility/visual coverage, production bundles and workflows outside the documented matrix remain unverified. The previously reported coverage percentages are historical and were not recalculated; these counts do not imply 100% coverage.
