# Release Evidence

Reviewed 2026-10-06. Original implementation inspired by GitPulse's documented workflow; no upstream code imported because its referenced license file could not be verified.

## Verified

- 20 Python tests for stable identity, renames/refollows, complete-fetch-before-write, duplicate IDs, stale writers, append-only history, persistence, following response order, pagination, redirects, invalid payloads, authentication, redaction, lock recovery and CORS defaults.
- Strict mypy on all application modules; Ruff lint/format and strict TypeScript production build.
- Eight Playwright cases across desktop 1440x900 and mobile 390x844: every view, search/sort, CSV download, API origin validation, nonblank chart, responsive framing and HTML injection rendered as text.
- npm audit and pip-audit report no known vulnerabilities at verification time; this is not a security guarantee.
- One actual public GitHub REST sync of Sushant-Nemade: one follower, one following account and 23 repositories at observation time. Raw account data remains ignored/local; public demo rows are fictional.

## Not Verified or Implemented

- A privately hosted backend, uptime/load guarantees, multi-user tenancy, OAuth, cloud-database replication or production disaster recovery.
- Live loss/refollow events beyond deterministic fixtures; the first real snapshot is only a baseline.
- Exact upstream feature parity, GraphQL contribution totals, follower join dates or historical data before collection starts.
- Docker runtime and unattended scheduling. These are not part of the verified release.

Check GitHub Actions separately for remote CI and Pages status. Local passing checks alone are not deployment proof.