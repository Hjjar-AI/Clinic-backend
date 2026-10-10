# Automated test suite plan

Updated 2026-10-11. Authorized tests, test tooling and Vue/Vite test transforms; preserve existing application versions and clinic data. Implementation and repeatable runners are complete; [guide](testing.md), [results](doneCurrent.md).

Remaining environment verification:

- Verify pinned Django/DRF on a supported Python runtime; the Python 3.14 probe encounters Django 5 template-context errors.
- PostgreSQL concurrent writers/locking, PDF Arabic typography/static fonts, production build and additional browser/visual workflows remain outside the verified matrix.
