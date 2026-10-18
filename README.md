# GitPulse: Audience Workspace

An original, single-account GitHub audience tracker with durable snapshots, append-only observations, a protected API and a typed dashboard.

**Status: tested reference implementation.** Core and browser checks pass; one real public GitHub REST sync was verified. The public Pages dashboard uses fictional data, not your account snapshot. A hosted private API, unattended scheduling, production load and disaster recovery have not been verified.

## Public Demo

[Open the public audience workspace](https://sushant-ai-demos.pages.dev/gitpulse/)
on Cloudflare Pages. It remains accessible when the maintainer's computer is off.
The dashboard uses fictional sample data; private account snapshots, sync APIs
and credentials are not exposed.
[GitHub Pages fallback](https://sushant-nemade.github.io/gitpulse/) |
[All project demos](https://sushant-ai-demos.pages.dev/).

## Provenance and Licensing

The functional concept was selected from [AI Project Gallery](https://github.com/KalyanM45/AI-Project-Gallery), referencing [KalyanM45/GitPulse](https://github.com/KalyanM45/GitPulse) at `8af259174045fce5c081b36e36b407df82834823`.

The upstream README claims MIT licensing, but the referenced LICENSE is absent and GitHub reports no detected license. Consequently **no upstream source code, assets, Git history or license notice was imported**. This project independently implements the documented audience-tracking workflow; it is not a fork, relicensing of upstream code, or a claim of exact parity with every upstream feature. Its original code is offered under [MIT](LICENSE). Third-party dependencies retain their own licenses, bundled with the static deployment.

Primary category: **Data and Developer Tools**. Portfolio placement: **Trustworthy data and developer tools**. [Projects catalog](https://github.com/Sushant-Nemade/ai-project-gallery).

## Implemented Workflow

- Followers, following, lost followers excluding refollows, change history, and public repository metrics.
- Numeric GitHub IDs distinguish renames from removals. Baseline imports are not falsely classified as new followers.
- Both audience lists and repositories must finish fetching before the SQLite transaction commits. A failed request, malformed payload, duplicate identity or stale writer preserves the previous snapshot.
- SQLite history rejects updates/deletions through database triggers. Individual current snapshots update atomically; a single database is bound to one account.
- Fixed GitHub REST origin, no redirected credential requests, response/page/record caps, a 50-request budget and a 90-second sync deadline.
- Authenticated state and sync endpoints, constant-time token comparison, explicit optional CORS origins and a public health endpoint.
- Strict Python typing and runtime-validated TypeScript data; safe DOM text rendering, search, sorting and CSV export with formula-prefix protection.

Dates are **first observed**, not actual follow dates. REST pagination is not a globally consistent GitHub snapshot: account changes during paging can affect observations. History starts when you begin collecting; no historical recovery or private contribution-graph coverage is claimed.

## Local Setup

Requires Python 3.13, uv, and Node.js 24. From the repository root:

```text
uv sync --frozen
uv run --frozen python -m scripts.demo
cd frontend
npm ci --ignore-scripts
npm run build
cd ..
```

Inspect public data explicitly:

```text
uv run --frozen python -m gitpulse sync --username Sushant-Nemade
uv run --frozen python -m gitpulse report --username Sushant-Nemade
```

These commands store the account snapshot in ignored local `data/gitpulse.sqlite`. Never publish that database or an exported live snapshot as demo data. Public REST requests can work without a GitHub token, subject to rate limits. Configure `GITHUB_TOKEN` locally only if needed; tokens remain server-side.

## Protected Local Application

Set `API_TOKEN` to a strong random value of at least 32 characters through your terminal or secret manager, not in chat or Git. Set `GITHUB_USERNAME` and optionally `DATABASE_PATH`. `.env.example` documents names; this project does not automatically load `.env` files.

```text
uv run --frozen uvicorn gitpulse.api:application --factory --host 127.0.0.1 --port 8770
```

Open http://127.0.0.1:8770 and configure the API connection with the local service's API token, **not a GitHub personal token**. Tokens are held only in browser memory and cleared on disconnect. HTTPS is required for non-loopback API origins. Remote private API hosting needs explicit CORS configuration, persistent storage, HTTPS, backup and access-policy review; Pages hosts only the fictional demo.

Automatic collection is disabled by default. Schedule explicit CLI syncs on your own secured machine only after validating credentials, quotas, storage and retention. No paid hosting or broad MongoDB network access is configured.

## Verification

```text
uv run --frozen pytest -q
uv run --frozen mypy gitpulse
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pip-audit --progress-spinner off
cd frontend
npm run format:check
npm audit
npm run build
npx playwright install chromium
npm test
```

CI uses mocks and fictional data, not your credentials or live snapshots. See [release evidence](docs/RELEASE_STATUS.md) and [operations](docs/OPERATIONS.md). The static Pages artifact excludes Python state, environment files, access tokens and private databases.