# Automated test suite plan

Updated 2026-10-11. Authorized tests, test tooling and Vue/Vite test transforms; preserve existing application versions and clinic data. Implementation and repeatable runners are complete; [guide](testing.md), [results](doneCurrent.md).

2026-10-11 expansion complete: 39 additional backend, 41 frontend component and 21 browser cases; **173 backend / 110 Node / 74 Vue / 42 Chromium checks passed**. Added empty-body/replay/throttle and mobile clickability/overflow regressions; [coverage](testing.md).

Remaining environment verification:

- Verify pinned Django/DRF on a supported Python runtime; the Python 3.14 probe encounters Django 5 template-context errors.
- PostgreSQL concurrent writers/locking, production build, other browser engines and workflows outside the documented matrix remain unverified. Requested Arabic PDF/static-font/print checks and all specified full browser workflows are complete; [record](pdf-workflow-verification.md).

Requested follow-on expansion complete: **174 backend / 110 Node / 77 Vue / 60 Chromium / 6 PDF appearance checks passed**, including all requested clinical, billing, import and full-recovery workflows across three viewports.
