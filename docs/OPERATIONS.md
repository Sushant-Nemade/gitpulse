# Operations

## Security and Data

Bind the API to loopback by default. Use HTTPS and a strong API token behind an explicitly configured reverse proxy for remote access. Do not put GitHub tokens in frontend configuration, URLs, browser storage, logs or the gallery. `CORS_ORIGINS` is an optional comma-separated list of trusted exact origins; do not use a wildcard for a private deployment.

GitHub identity/relationship observations can be personal data even when public. Keep the ignored database private, restrict filesystem access, define retention and obtain appropriate permission before monitoring other accounts. Browser fonts contact Google Fonts; no analytics tracker is included.

## Recovery and Concurrency

One database belongs to one account. Do not change accounts against an existing database. Take secured backups before maintenance. History is append-only; deletion or retention changes require an explicit operator decision, not a silent sync rewrite.

The API rejects concurrent in-process syncs; optimistic revisions also reject a stale cross-process writer. Failed network fetches do not modify the snapshot. SQLite commits snapshots/events/repositories together. A 90-second sync budget and 50-request cap prevent unbounded collection; large accounts or exhausted GitHub quotas fail safely rather than truncate the accepted snapshot.

No data is collected automatically unless you explicitly schedule the CLI on a secured host. Review GitHub API policies and quotas. Page contents can change during pagination, so observed changes are signals to review, not proof of another person's actions.

## Deployment

The Pages workflow deploys only the built frontend with fictional fixtures after successful CI. It never includes `data/`, environment files or a live-account export. The private backend is an independently configured operator service, not an automatically hosted SaaS.

To roll back frontend delivery, restore the last reviewed revision in a new change and rerun checks. Restore database backups separately under operator control; do not force-push or silently reset history.