# Local Runtime Verification

- Backend started locally on port 8000 with the existing FastAPI entry point.
- `GET /api/v1/health` returned HTTP 200 with a healthy database.
- `GET /api/v1/health/ready` returned HTTP 200 with database ready.
- `GET /api/v1/dashboard/overview` returned HTTP 200 and real persisted catalog metrics: 1,000 catalog rows, 998 processed products, 998 Commerce Output records, 100% evidence coverage, and ground-truth accuracy unavailable because no official ground-truth dataset is configured.
- Frontend Vite started on port 5175 because ports 5173 and 5174 were already occupied.
- Vite proxy check `GET http://127.0.0.1:5175/api/v1/health` returned HTTP 200 from the backend.
- Browser frontend URL opened: `http://127.0.0.1:5175/`.
- Dashboard rendered successfully with navigation, persisted batch summary, product records, evidence-first workflow, review state, and Commerce Output entry points.
- Initial browser API warning was transient; after refresh the dashboard loaded normally.
