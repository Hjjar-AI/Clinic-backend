# Automated test suite plan

Authorized 2026-10-11: create and run frontend/backend tests. Preserve versions/lockfiles and unrelated changes; no production build or destructive project-data operations.

- Backend: isolated runner/settings; core validation, authentication/CSRF, scope and versioned HTTP, patient records/merge, visit signing/documents, scheduling/billing/tasks, catalogs/imports, authenticated recovery/media, notifications/reports/commands.
- Frontend: Node runner with aliases/browser doubles; actual utilities, API interceptors/services, Pinia stores, guards, composables and overlay behavior.
- Run both suites, investigate failures, document confirmed defects separately from test mistakes and unverified rendering/concurrency.
- Document repeatable commands, isolation and coverage limits. Browser-rendered component/E2E and PostgreSQL verification require their own available environments; do not label source/unit checks as browser coverage.
