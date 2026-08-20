# Final Deployment Audit & Submission Readiness

**Project:** AI Product Intelligence & Trust Engine  
**Audit date:** 15 August 2026  
**Repository:** `/home/ubuntu/ai-product-intelligence/`

## Executive conclusion

The frontend is deployable to Vercel and the backend is deployable as a Docker web service. No deployment-blocking code defect was found, so no application code was changed during this audit. The main operational caveat is persistence: the application currently stores its SQLite database and uploaded/reference files under `/app/data`, so the backend must have a durable volume mounted at that exact path. A fresh external deployment will not automatically contain the catalog data currently present in the sandbox.

A public HTTPS URL cannot be produced from this audit alone because no external Render, Railway, Fly.io, GitHub, or Vercel deployment credentials/session were supplied. The exact deployment sequence and post-deployment smoke test are provided below.

## Verification performed

| Check | Result |
|---|---|
| Backend regression suite | **129 passed** |
| Frontend production build | **Passed** — Vite transformed 1,415 modules |
| Local backend liveness | **HTTP 200** from `/api/v1/health` |
| Local backend readiness | **HTTP 200** from `/api/v1/health/ready` |
| Local dashboard route | **HTTP 200** from `/api/v1/dashboard/overview`; returned the persisted 1,000-row batch metrics |
| Production frontend configuration | `frontend/vercel.json` present and valid for Vite SPA deployment |
| Production container configuration | Dockerfile binds to `0.0.0.0`, uses `PORT`, and defines a readiness healthcheck |
| Code changes during audit | **None** |

The test suite emitted existing deprecation/SQLAlchemy warnings, but no test failed.

## 1. Frontend deployability to Vercel

**Yes.** The `frontend/` directory is ready for a Vercel project. `frontend/vercel.json` defines the Vite build command, `dist` output directory, framework, and SPA fallback rewrite. Configure the Vercel project as follows:

| Vercel setting | Value |
|---|---|
| Root directory | `frontend` |
| Framework preset | Vite |
| Build command | `pnpm run build` |
| Output directory | `dist` |
| Production environment variable | `VITE_API_URL=https://<backend-host>/api/v1` |
| Optional production environment variable | `VITE_API_TIMEOUT_MS=120000` |

`VITE_API_URL` is injected at build time. The frontend API client already uses that variable for production and does not contain a hardcoded production localhost URL.

## 2. Backend production readiness

**Yes, for a hackathon/demo deployment with durable storage.** The backend Dockerfile starts Uvicorn without development reload, binds to `0.0.0.0`, reads the platform-provided `PORT`, and exposes a healthcheck through `/api/v1/health/ready`. The FastAPI application also has environment-based CORS, request IDs/logging, generic unexpected-error responses, and liveness/readiness endpoints.

The backend should not be run in production through the root `docker-compose.yml`; that file is explicitly development-only because it uses source mounts, reload mode, localhost defaults, and development commands.

The main caveat is that SQLite and uploaded files are filesystem-backed. Use a managed PostgreSQL database and object storage for a higher-scale production system, or use the existing SQLite/filesystem design with a durable volume for the live hackathon prototype.

## 3. Localhost dependencies

There are no hardcoded localhost dependencies in the production frontend API path or backend business logic. Localhost appears only in development-safe defaults:

- Backend `CORS_ALLOWED_ORIGINS` defaults to `http://localhost:5173,http://127.0.0.1:5173`.
- Vite's development proxy defaults to a local backend at `http://localhost:8000`.
- The development Docker Compose stack uses local ports and reload mode.

Override `CORS_ALLOWED_ORIGINS` and `FRONTEND_URL` on the deployed backend. Set `VITE_API_URL` on Vercel. The production frontend build will then use the public backend URL.

## 4. Recommended backend platform

**Recommended:** Render Web Service using the repository's backend Dockerfile, plus a Render Persistent Disk mounted at `/app/data`.

Render is the simplest fit for this repository because it provides Docker deployment, a public HTTPS hostname, environment variables, health checks, and persistent disk support. Render persistent disks are a paid-service feature; do not assume that a free web-service tier provides the durable disk required by this SQLite/file-storage design.

**Alternatives:** Railway with a Volume mounted at `/app/data`, or Fly.io with a volume mounted at `/app/data`. All three support a public HTTPS API. Do not select a platform configuration that has only ephemeral container storage.

## 5. Environment variables

### Backend required for the deployed demo

```text
DATABASE_URL=sqlite:///./data/ai_product_intelligence.db
ENVIRONMENT=production
DEBUG=False
CORS_ALLOWED_ORIGINS=https://<your-project>.vercel.app
FRONTEND_URL=https://<your-project>.vercel.app
ENABLE_DOCS=False
```

`DATABASE_URL` may remain the SQLite value above when `/app/data` is durable. If using PostgreSQL, set it to the platform's SQLAlchemy-compatible database URL and separately address uploaded/reference file persistence.

### Backend required only when live LLM extraction is demonstrated

```text
OPENAI_API_KEY=<server-side-secret>
OPENAI_API_BASE=<openai-compatible-base-url>
OPENAI_MODEL=<model-name>
```

`OPENAI_API_KEY` must be stored only in the backend platform's secret/environment configuration. It must never be placed in Vercel frontend variables or source code. `OPENAI_API_BASE` and `OPENAI_MODEL` should match the selected OpenAI-compatible provider.

### Optional backend discovery variables

```text
DISCOVERY_PROVIDER=none
DISCOVERY_PROVIDER_API_KEY=<server-side-secret-if-a-supported-provider-is-used>
```

Leave discovery disabled for the most deterministic demo unless a supported provider is intentionally configured. The dashboard honestly reports the no-provider state.

### Frontend on Vercel

```text
VITE_API_URL=https://<backend-host>/api/v1
VITE_API_TIMEOUT_MS=120000
```

Do not set `VITE_DEV_BACKEND_URL` for the Vercel production deployment; it is a development proxy setting.

## 6. Frontend-to-backend connection

Set `VITE_API_URL` in the Vercel project to the backend's public HTTPS origin plus `/api/v1`, for example:

```text
VITE_API_URL=https://ai-product-intelligence-api.onrender.com/api/v1
```

Trigger a new Vercel deployment after changing the variable because Vite embeds `VITE_*` values during the build. On the backend, set `CORS_ALLOWED_ORIGINS` to the exact Vercel browser origin, without a trailing slash, for example:

```text
CORS_ALLOWED_ORIGINS=https://ai-product-intelligence.vercel.app
FRONTEND_URL=https://ai-product-intelligence.vercel.app
```

If a custom domain is used, include that exact origin instead. Do not use `*` as a shortcut when credentialed browser behavior is needed.

## 7. Database and file persistence

The current application writes the SQLite database and uploaded/reference files below `./data`; inside the backend container this is `/app/data`. This is safe for the deployed demo **only when `/app/data` is mounted to durable storage**.

| Platform | Required storage configuration |
|---|---|
| Render | Add a Persistent Disk and mount it at `/app/data` |
| Railway | Add a Volume and mount it at `/app/data` |
| Fly.io | Create and mount a volume at `/app/data` |

Without the volume, a redeploy/restart can lose the database, uploaded documents, reference datasets, and processed catalog state. The 1,000-row processed catalog currently present in the sandbox's local SQLite database will not appear automatically on a fresh deployment. After deployment, re-upload `backend/data/Unihack_SampleDataset-Input.csv` through Catalog Processing and process it again, or explicitly transfer the database and related data files into the mounted volume.

For a judged demo, re-uploading and processing the CSV after deployment is the clearest and most reproducible approach. Verify the resulting batch status before sharing the URL.

## 8. Exact steps for a public HTTPS Live Prototype URL

### A. Prepare the repository

1. Commit the current repository to GitHub, including `backend/`, `frontend/`, Dockerfiles, Vercel configuration, tests, and documentation.
2. Do not commit `.env`, real API keys, or provider credentials.
3. Confirm the backend test suite and frontend build pass locally.

### B. Deploy the backend on Render

1. Create a Render account and choose **New → Web Service**.
2. Connect the GitHub repository.
3. Set the service root directory to `backend/`.
4. Choose Docker deployment and use `backend/Dockerfile`.
5. Set the service port to the platform-provided `PORT` behavior; do not replace the container command with development reload mode.
6. Add a Persistent Disk with mount path `/app/data` and enough capacity for the demo dataset and uploads.
7. Add the backend environment variables listed above. Initially, if the final Vercel URL is not known, deploy with a temporary exact origin and update CORS after Vercel is created.
8. Deploy and wait for the service health check to pass.
9. Copy the generated backend HTTPS URL, such as `https://<service>.onrender.com`.

### C. Deploy the frontend on Vercel

1. Create a Vercel project from the same GitHub repository.
2. Set the root directory to `frontend/`.
3. Select Vite or let Vercel detect the existing Vite configuration.
4. Add `VITE_API_URL=https://<service>.onrender.com/api/v1`.
5. Add `VITE_API_TIMEOUT_MS=120000`.
6. Deploy and copy the generated frontend URL, such as `https://<project>.vercel.app`.

### D. Complete the CORS connection

1. Return to the backend service environment settings.
2. Set `CORS_ALLOWED_ORIGINS` to the exact Vercel origin.
3. Set `FRONTEND_URL` to the same exact origin.
4. Save/redeploy the backend.
5. If the Vercel deployment was made before this change, redeploy Vercel only if its `VITE_API_URL` changed.

### E. Seed the live demo data

1. Open the public Vercel URL.
2. Open Catalog Processing.
3. Upload `backend/data/Unihack_SampleDataset-Input.csv` from the repository.
4. Start processing and wait for the batch to finish.
5. Confirm that the resulting batch and product metrics are visible on Dashboard.
6. Optionally upload a small PDF, website URL, or CSV in Ingestion to demonstrate source-backed provenance and source isolation.
7. Select a product, inspect evidence/conflicts/review state, and open Commerce Output.

## 9. Post-deployment smoke test

Run these checks after deployment, replacing the placeholder with the actual backend host:

```bash
BACKEND='https://<backend-host>'

curl -fsS "$BACKEND/api/v1/health"
curl -fsS -i "$BACKEND/api/v1/health/ready"
curl -fsS -i "$BACKEND/api/v1/dashboard/overview"
```

Expected results:

- `/api/v1/health` returns HTTP 200 and a healthy JSON response.
- `/api/v1/health/ready` returns HTTP 200 with `{"status":"ready",...}`.
- `/api/v1/dashboard/overview` returns HTTP 200. Before seeding, it may honestly show an empty state; after catalog processing it should show the real batch metrics.

Then perform this browser smoke path:

| Step | Expected result |
|---|---|
| Open the Vercel URL | React dashboard renders over HTTPS |
| Dashboard API status | Backend is reachable; no CORS error in browser console |
| Open Ingestion | PDF, Website URL, and CSV options render |
| Upload a small CSV | New job is created and processing status appears |
| Extract Product Intelligence | Current job's source-backed results render without prior-job contamination |
| Open Product Analyzer/Investigation | Evidence and provenance are visible |
| Open Conflict Detection | Conflicts, agreement counts, severity, and source citations render when applicable |
| Open Catalog Processing | Upload/process status, rows, review queue, and exports work |
| Open Commerce Output | Canonical record, field audit, validation state, and JSON/CSV/XLSX downloads work |
| Refresh the backend/reopen the frontend | Seeded data remains because `/app/data` is durable |

Do not treat a successful health endpoint alone as a complete workflow test. The final judge-facing URL should be shared only after the browser path and persistence refresh check pass.

## 10. Still missing before Unilog submission

### Required or materially important

| Item | Current state | What is still needed |
|---|---|---|
| Public HTTPS live prototype | Not deployed by this audit | Deploy backend and frontend, configure CORS/API URL, and smoke-test the public URL |
| Live demo data | Present only in the sandbox's local database | Re-upload/reprocess the 1,000-row CSV on the deployed durable volume, then verify metrics |
| Official expected-output dataset | **Unavailable** | Obtain the official expected-output CSV/XLSX before claiming ground-truth accuracy |
| Official Unilog Delivery Format metadata | **Unavailable/incomplete** | Obtain official field mappings, required fields, LOV registry, UOM rules, and character-limit matrix |
| Ground-truth accuracy | **Not calculated** | Requires the official expected-output dataset; do not substitute the raw input dataset |
| Official LOV/UOM compliance results | Only available where reference data has been supplied | Supply the official controlled vocabularies and rerun evaluation |
| Official character-limit results | Only configurable/project-supported limits are available | Supply the official per-field limits and rerun validation |

### Optional for the demo, not a blocker for the current prototype

- Configure an OpenAI-compatible backend key if the live extraction demo is required.
- Configure a supported discovery provider only if the live discovery flow is required; otherwise retain the honest `provider_not_configured` state.
- Use a managed PostgreSQL database and object storage, backups, rate limiting, secret rotation, and centralized observability for a non-demo production service.

The project intentionally does **not** claim or implement RAG/FAISS/embeddings, a knowledge graph, Random Forest trust scoring, LangGraph agents, automatic conflict resolution, or automatic product-data modification. Those are documented limitations rather than deployment blockers for the current evidence-first prototype.

## Reference documentation

- [Render Web Services](https://render.com/docs/web-services)
- [Render Persistent Disks](https://render.com/docs/disks)
- [Railway Volumes](https://docs.railway.com/volumes)
- [Fly.io FastAPI deployment](https://fly.io/docs/python/frameworks/fastapi/)
