# TrialGuard on one Vercel project

## Architecture

One Vercel project serves the Vite static build and the Python function on the
same domain. Browser code uses the relative Axios base URL `/api`; it never
contains a Vercel hostname, a Cloudflare hostname, or a provider credential.

```text
Browser
  └─ https://<project>.vercel.app
      ├─ /, /patients/*, /sites/*, /deviations, /capa/*, /bob → Vite SPA
      ├─ /api/* → api/index.py → src.backend.main:app
      └─ /mcp → api/index.py → FastAPI JSON-RPC router
                                 └─ managed PostgreSQL + NVIDIA/watsonx
```

`api/index.py` deliberately imports the existing FastAPI application instead of
duplicating it. Local Uvicorn use remains supported by `src.backend.main:app`.
On Vercel, no Uvicorn process is started: the platform invokes the Python
function per request.

## Repository structure

```text
api/index.py                         Vercel FastAPI entrypoint
src/frontend/                        existing Vite application
src/backend/                         existing FastAPI application
src/backend/scripts/initialize_production.py
requirements.txt                     root Python dependency manifest for Vercel
package.json                         root Vercel build command
vercel.json                          static output and same-origin rewrites
```

## Vercel project settings

Import **this repository root**, not `src/frontend`.

- Build command: `npm run build`
- Output directory: `src/frontend/dist`
- Install command: Vercel default; the build script runs `npm ci` in
  `src/frontend` using its committed lockfile.
- Python dependencies: root `requirements.txt`, which includes
  `src/backend/requirements.txt` and the PostgreSQL `psycopg` driver.

`vercel.json` routes `/api/*` and `/mcp` to `api/index.py`; all remaining
non-file requests are rewritten to `index.html` for React Router. Static assets
remain Vercel-served and CDN-friendly. Do not add an `/api/* → index.html`
rewrite.

## Persistent database

SQLite is only for local development. For Vercel, use a managed PostgreSQL
database attached to the same Vercel project (Vercel Postgres, powered by Neon,
or a Neon integration). Put its SQLAlchemy-compatible connection URL in
`DATABASE_URL`. This survives function restarts and redeployments; Vercel's
filesystem does not.

The SQLAlchemy models use portable columns, relationships, indexes, and foreign
keys. `DATABASE_URL` overrides local SQLite; leaving it blank retains
`DATABASE_PATH` local development behavior.

### One-time initialization

After creating the managed database and setting `DATABASE_URL` locally or in a
secure CI environment, run:

```powershell
$env:DATABASE_URL = '<managed-postgresql-url>'
.venv\Scripts\python.exe -m src.backend.scripts.initialize_production
```

The initializer creates the schema, inserts deterministic data only when no
trial exists, runs analysis once only after a new seed, and verifies:

- 1 trial, 6 sites, 60 patients, 240 visits
- 1200 lab results and 125 adverse events

It does not run on HTTP requests. The old reset seed command remains a local
development tool and must never be pointed at production.

For future schema changes, add an explicit reviewed migration before deploying
the model change; `create_all` is bootstrap-only and is not a replacement for
production migrations.

## Environment variables

Set these as **server-side Vercel environment variables** for Production (and
Preview if desired):

```text
DATABASE_URL=<managed PostgreSQL connection URL>
APP_ENV=production
NVIDIA_API_KEY=...
NVIDIA_MODEL=nvidia/nemotron-3.5-lightning-30b-a3b
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
WATSONX_API_KEY=...
WATSONX_PROJECT_ID=...
WATSONX_URL=https://us-south.ml.cloud.ibm.com
```

The sole frontend configuration is optional and public:

```text
VITE_API_BASE_URL=/api
```

Never use `VITE_` for database, NVIDIA, watsonx, or token values. NVIDIA keeps
`enable_thinking: false` in the existing server-side client. watsonx and NVIDIA
fallback behavior are unchanged.

## Local Vercel test and production deployment

Install/authenticate the Vercel CLI, then run from repository root:

```powershell
npx vercel link
npx vercel dev
```

Test one origin:

```text
GET  /                     GET  /api/sites
GET  /patients             GET  /api/patients
GET  /patients/PT-0042     GET  /api/deviations
GET  /deviations           GET  /api/capa
GET  /capa                 POST /api/bob/ask
GET  /bob                  POST /mcp
```

After the local Vercel test and managed database initialization pass:

```powershell
npx vercel deploy --prod
```

Verify `POST /api/bob/ask` with `{"question":"What is rule INC-01?"}` and
confirm `tool_used` is `get_protocol_rule`. Also verify SITE-003 risk,
SITE-003 Major deviations, PT-0042 deviations, site-risk summary, and the model
identity question. `/mcp` stays same-domain JSON-RPC 2.0.

## Persistence verification and redeployment

Generate or update a CAPA/deviation through the API, request it again, deploy a
new revision, and request it again. The record must remain because the database
is managed PostgreSQL, not function-local storage. If it is absent, stop and
check `DATABASE_URL` and the selected Vercel environment before continuing.

## Troubleshooting

- `DATABASE_URL` empty in Vercel: the app would fall back to SQLite, which is
  not supported for production persistence. Set the managed URL before deploy.
- `/api/api/...`: Axios already has base URL `/api`; endpoint helpers must omit
  that prefix, as Ask Bob does with `/bob/ask`.
- SPA refresh 404: verify the root `vercel.json` was deployed.
- API reaches `index.html`: ensure the `/api/*` rewrite precedes the SPA rewrite.
- Provider unavailable: Ask Bob and CAPA return their existing safe fallback;
  provider errors and secrets are not sent to the browser.

Redeploy using `npx vercel deploy --prod`; do not reseed unless deliberately
resetting a non-production database.
