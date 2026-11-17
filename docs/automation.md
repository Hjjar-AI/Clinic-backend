# GitHub automation

[Setup](setup.md) · [Bundles](bundles.md) · [Verification](verification.md) · [Evidence](doneCurrent.md).

## Backend checks

`.github/workflows/checks.yml` runs on pushes, pull requests, manual dispatch and Mondays at 04:37 UTC. Windows 2022/Linux Ubuntu 24.04 x64 use Python 3.14, the existing pinned requirements and installed native PDF/MIME libraries. Jobs run the SQLite suite, database-free native/PDF checks, and a disposable HTTP start/access-denial/stop probe. A Linux job runs the existing PostgreSQL suite against an owned temporary Unix-socket cluster. No clinic configuration/storage or application migration files are used by the isolated checks.

The frontend is checked out beside the backend for its bundled fonts. Automatic runs use `main`; manual checks expose a `frontend_ref` input. Use a commit SHA for a controlled compatibility baseline. The separate release workflow always requires an exact frontend SHA and records both commits.

## Repository access

The repositories are `Hjjar-AI/Clinic-backend` and `Hjjar-AI/Clinic-frontend`; both are public. Checkout uses the ordinary job token without custom secrets or repository variables, and credentials are not persisted. Checks use read permissions; artifact verification also needs `actions: read`. Only the final manually dispatched draft-release job grants `contents: write`, to create a draft with attachments. No workflow publishes a release, pushes code/tags or deploys. If either repository becomes private later, sibling checkout will need a separately configured read credential.

## Release and browser workflows

`.github/workflows/bundles.yml` is manually dispatched and builds/smoke-checks two downloadable executable folders; see [bundle instructions](bundles.md). It does not run on every push.

After both builds pass, reusable `.github/workflows/verify-bundles.yml` downloads each actual ZIP/tar.gz on its matching OS, verifies SHA-256 and source revisions, extracts into a temporary path containing spaces and runs the extracted executable. Linux receives its documented native prerequisites; Windows verification does not install MSYS2, Python application requirements or external native DLL paths. Green verification produces `verified-Linux-<run ID>` and `verified-Windows-<run ID>` artifacts with archives, checksums and JSON evidence, retained for 30 days.

`.github/workflows/compatibility.yml` manually pairs the selected backend revision with an exact frontend SHA. It calls the frontend's reusable browser workflow on `main`, which checks out the supplied source SHAs and exercises existing synthetic API-backed workflows. Push the frontend reusable workflow before using this entry point. The frontend offers the corresponding manual entry point; compatibility checks are not part of weekly scheduling.

## Dependency vulnerability reports

`.github/workflows/dependency-audit.yml` runs on requirement/audit-workflow changes, manual dispatch and Mondays at 05:07 UTC. It installs CI-only `pip-audit` and resolves/audits SQLite, PostgreSQL, MySQL/MariaDB and Redis/Memcached requirement profiles on Linux; a Windows PostgreSQL profile also covers Windows-specific shared requirements. MariaDB reuses the MySQL driver profile. Reports include transitive dependencies and are retained for 14 days; vulnerability findings or resolution/advisory-service errors fail the check. It never runs `--fix` or edits requirements/lockfiles. Optional unpinned requirements resolve at scan time, so this reports selected profiles rather than certifying every deployed environment or native system library.

## Manual draft releases

Choose **Actions → Prepare draft release → Run workflow**, providing a successful **Windows and Linux bundles** run ID and an existing tag pointing to that run's backend commit. The workflow checks run provenance, re-downloads/reverifies both OS archives, rejects differing frontend revisions or checksums and writes notes containing both source SHAs and the original run link. The final job creates a **draft** release with the archives, checksums and verification reports. Existing releases/assets are not overwritten; tags and application versions are not created or changed. Review and publish the draft separately. Artifact expiration may require building a new bundle run.

The frontend owns automatic unit/component tests and Vite builds on Windows/Linux, plus a manual browser workflow with an exact backend SHA. Browser fixtures use disposable synthetic storage. The browser workflow is opt-in and does not override a local browser-work stop. Neither the CI suites nor a successful build certify layout, native dialogs or physical printing.
