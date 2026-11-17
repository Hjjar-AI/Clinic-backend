# GitHub automation

[Setup](setup.md) · [Bundles](bundles.md) · [Verification](verification.md) · [Evidence](doneCurrent.md).

## Backend checks

`.github/workflows/checks.yml` runs on pushes, pull requests and manual dispatch. Windows 2022/Linux Ubuntu 24.04 x64 use Python 3.14, the existing pinned requirements and installed native PDF/MIME libraries. Jobs run the SQLite suite, database-free native/PDF checks, and a disposable HTTP start/access-denial/stop probe. A Linux job runs the existing PostgreSQL suite against an owned temporary Unix-socket cluster. No clinic configuration/storage or application migration files are used by the isolated checks.

The frontend is checked out beside the backend for its bundled fonts. Automatic runs use `main`; manual checks expose a `frontend_ref` input. Use a commit SHA for a controlled compatibility baseline. The separate release workflow always requires an exact frontend SHA and records both commits.

## Repository access

The repositories are `Hjjar-AI/Clinic-backend` and `Hjjar-AI/Clinic-frontend`; both are public. Checkout uses the ordinary job token without custom secrets or repository variables. Checkout credentials are not persisted; workflows have only `contents: read` and do not push, publish or deploy. If either repository becomes private later, sibling checkout will need a separately configured read credential; the ordinary job token is scoped to its own repository.

## Release and browser workflows

`.github/workflows/bundles.yml` is manually dispatched and builds/smoke-checks two downloadable executable folders; see [bundle instructions](bundles.md). It does not run on every push.

The frontend owns automatic unit/component tests and Vite builds on Windows/Linux, plus a manual browser workflow with an exact backend SHA. Browser fixtures use disposable synthetic storage. The browser workflow is opt-in and does not override a local browser-work stop. Neither the CI suites nor a successful build certify layout, native dialogs or physical printing.
