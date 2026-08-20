# AI Product Intelligence & Trust Engine

A source-backed product intelligence and commerce delivery prototype for industrial catalogs. The system ingests PDFs, websites, CSV/XLSX catalogs, and official reference datasets; preserves source evidence and provenance; extracts and normalizes product attributes; detects conflicts; supports controlled discovery; processes large catalogs; produces auditable Commerce Output; and presents an evaluator-facing dashboard.

## Architecture

The repository is a monorepo with a FastAPI/SQLAlchemy backend and a React/Vite/Tailwind frontend.

| Component | Location | Responsibility |
|---|---|---|
| Backend API | `backend/` | Ingestion, extraction, investigations, conflict detection, evaluation, reference data, enrichment, discovery, Commerce Output, catalog batches, and dashboard aggregation |
| Frontend | `frontend/` | Evaluator dashboard, source ingestion, Product Analyzer, investigations, evaluation, reference data, Commerce Output, and Catalog Processing |
| Database | SQLite by default; PostgreSQL-compatible URL supported by SQLAlchemy | Persisted source, product, evidence, enrichment, discovery, review, catalog, output, and dashboard state |
| Deployment | Vercel-ready frontend plus containerized backend | Static frontend deployment with a separately deployed API and explicitly configured CORS |

The application is intentionally evidence-first. Original values are not overwritten, reviewer decisions are stored separately, and unavailable official specifications are represented as unavailable rather than inferred.

## Requirements

- Python 3.11 or newer
- Node.js 20 or newer
- `pnpm` or npm
- SQLite for local development, or a production relational database URL
- An OpenAI-compatible provider only when LLM extraction is required

## Local development

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The local API is available at `http://localhost:8000`. Health endpoints are:

- `GET /api/v1/health` — liveness plus database status.
- `GET /api/v1/health/ready` — readiness probe; returns HTTP 503 if the database is unavailable.
- `GET /docs` — interactive API documentation when `ENABLE_DOCS=True`.

### Frontend

```bash
cd frontend
pnpm install
cp .env.example .env.local
pnpm run dev --host
```

The local frontend is available at `http://localhost:5173`. When `VITE_API_URL` is empty, requests use the relative `/api/v1` path and Vite proxies `/api` to `VITE_DEV_BACKEND_URL` (default `http://localhost:8000`). This keeps the browser API path same-origin during development and avoids hardcoded production backend URLs.

For a production frontend build:

```bash
cd frontend
pnpm run build
pnpm run preview
```

## Environment configuration

Backend settings are loaded from `.env` through `pydantic-settings`. Frontend settings are injected at Vite build time. Never commit real credentials; the checked-in examples contain placeholders only.

| Variable | Component | Purpose |
|---|---|---|
| `DATABASE_URL` | Backend | Database URL; SQLite is the local default |
| `ENVIRONMENT` | Backend | `development`, `staging`, or `production` label |
| `DEBUG` | Backend | FastAPI debug mode; keep `False` in production |
| `CORS_ALLOWED_ORIGINS` | Backend | Comma-separated exact browser origins; do not use `*` with credentials |
| `FRONTEND_URL` | Backend | Optional public frontend origin added to CORS |
| `MAX_UPLOAD_SIZE_BYTES` | Backend | Bounded upload size; default 25 MiB |
| `REQUEST_TIMEOUT_SECONDS` | Backend | Website-ingestion request timeout |
| `LOGGING_LEVEL` | Backend | `DEBUG`, `INFO`, `WARNING`, or `ERROR` |
| `ENABLE_DOCS` | Backend | Interactive docs toggle; disable in production if not needed |
| `OPENAI_API_KEY` | Backend | Optional server-side LLM credential; never expose to frontend |
| `OPENAI_API_BASE` | Backend | Optional OpenAI-compatible endpoint |
| `OPENAI_MODEL` | Backend | LLM model identifier |
| `DISCOVERY_PROVIDER` | Backend | `none` by default; optional supported provider |
| `DISCOVERY_PROVIDER_API_KEY` | Backend | Optional server-side discovery credential |
| `VITE_API_URL` | Frontend | Production API base including `/api/v1`; empty means same-origin `/api/v1` |
| `VITE_API_TIMEOUT_MS` | Frontend | Axios request timeout in milliseconds |
| `VITE_DEV_BACKEND_URL` | Vite dev server | Local proxy target only |
| `VITE_DEV_PROXY_TIMEOUT_MS` | Vite dev server | Local proxy timeout |

The complete commented template is in `.env.example`; frontend-specific variables are in `frontend/.env.example`.

## Production deployment

### Backend

The backend container runs without the development reload flag:

```bash
cd backend
docker build -t ai-product-intelligence-api .
docker run --rm \
  -p 8000:8000 \
  --env-file ../.env \
  -v "$PWD/data:/app/data" \
  ai-product-intelligence-api
```

For a managed deployment, use a persistent database rather than container-local SQLite, store uploaded/reference data on durable storage, place the API behind TLS and a reverse proxy, and configure exact `CORS_ALLOWED_ORIGINS` values for the deployed frontend. Set `ENVIRONMENT=production`, `DEBUG=False`, and decide whether interactive docs should remain enabled.

The API exposes `/api/v1/health` for liveness and `/api/v1/health/ready` for load-balancer readiness. The readiness endpoint checks database connectivity.

### Frontend on Vercel

The `frontend/` directory contains `vercel.json` with the Vite build command, `dist` output directory, and SPA fallback. Configure the Vercel project with `frontend` as its root directory and set:

```text
VITE_API_URL=https://api.example.com/api/v1
VITE_API_TIMEOUT_MS=120000
```

Replace the example API origin with the actual deployed backend. If frontend and backend are served behind one reverse proxy, `VITE_API_URL` may remain empty and the same-origin `/api/v1` path can be used.

The existing root `docker-compose.yml` is explicitly a development stack. It uses source mounts, Vite proxying, and backend reload. Do not use it as a production orchestration manifest without replacing the development volumes, reload command, secrets handling, and storage strategy.

## Evaluator demonstration flow

The shortest evaluator path is:

1. Open **Dashboard** and verify the API status banner, persisted catalog batch, real pipeline counts, reference-data status, discovery availability, and ground-truth availability.
2. Select a persisted product in **Demo Catalog**.
3. Review the product showcase: raw input, normalized/canonical values, confidence, source provenance, evidence chain, conflicts, review state, and Commerce Output state.
4. Select **Understand in Product Analyzer** to run the existing Source Only or Discovery Enabled product workflow. Discovery remains controlled and reports `provider_not_configured` when no provider is configured.
5. Open **Catalog Processing** to upload or select the large catalog, inspect validation, progress, result rows, failed rows, review queue, and CSV/XLSX/JSON exports.
6. Open **Commerce Output** to generate or inspect the stable field-auditable record and download JSON, CSV, or XLSX.
7. Use **Evaluation** and **Reference Data** to show rule-based quality checks and official-data availability. Ground-truth accuracy remains unavailable unless an official expected-output dataset is supplied.

## Supported API areas

| Area | Prefix |
|---|---|
| Health | `/api/v1/health`, `/api/v1/health/ready` |
| PDF, website, CSV ingestion | `/api/v1/ingest`, `/api/v1/ingest/website`, `/api/v1/ingest/csv` |
| Extraction | `/api/v1/extract` |
| Investigations and conflicts | `/api/v1/investigations` |
| Evaluation | `/api/v1/evaluation` |
| Reference data | `/api/v1/reference-data` |
| Enrichment | `/api/v1/enrichment` |
| Controlled discovery | `/api/v1/discovery` |
| Commerce Output | `/api/v1/commerce-output` |
| Catalog batches | `/api/v1/catalog/batches` |
| Evaluator dashboard | `/api/v1/dashboard` |

The OpenAPI document at `/openapi.json` is enabled only when `ENABLE_DOCS=True`.

## Testing and quality gates

Run the backend suite from the backend directory:

```bash
cd backend
python3 -m pytest -q
```

Run the frontend checks:

```bash
cd frontend
pnpm run build
pnpm run lint
```

The test suite covers source isolation, PDF/website/CSV ingestion, extraction guardrails, investigations, conflicts, evaluation availability, reference data, enrichment, discovery safety, Commerce Output, catalog batches, and evaluator dashboard aggregation.

## Security and operational behavior

Uploads are bounded by `MAX_UPLOAD_SIZE_BYTES`, filenames are sanitized before storage, and file paths are not derived directly from user-provided directory components. Discovery applies SSRF protection, redirect re-validation, response-size limits, fetch limits, identity verification, and source ranking before accepting external evidence. LLM and discovery credentials are server-side environment variables only and are not logged.

Request logs include request ID, method, path, status, and duration, but not request bodies, uploaded contents, API keys, or authorization headers. Unexpected exceptions return a generic message with a request ID while detailed diagnostics remain server-side.

The application does not automatically resolve conflicts, overwrite source values, generate missing identifiers, fabricate expected outputs, claim ground-truth accuracy without official data, or silently approve products that require review.

## Data and honest limitations

The supplied Unihack catalog is an input dataset. It can support deterministic parsing, validation, source-backed processing, evidence/provenance inspection, and rule-based quality reporting. The official expected-output file is handled as an upload-only Evaluation artifact and is intentionally not committed with the repository or runtime database. The application does not assume complete official Delivery Format metadata, a complete official LOV/UOM registry, or a complete official character-limit matrix unless those artifacts are supplied.

Accordingly:

- Rule-based quality metrics are not ground-truth accuracy.
- Missing official reference artifacts are displayed as unavailable, not as passes.
- Discovery is optional and disabled by default unless a supported provider is configured.
- The default local SQLite setup is suitable for demonstration and testing, not high-availability production.
- Durable object storage, managed database operations, TLS termination, secret rotation, backups, rate limiting, and centralized log/metric collection should be supplied by the deployment platform.
- The project intentionally does not implement RAG/FAISS/embeddings, a knowledge graph, ML trust scoring, or agent orchestration.
