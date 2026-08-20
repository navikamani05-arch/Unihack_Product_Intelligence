# Extraction Timeout Verification Notes

## Service verification

The restarted backend responds with HTTP 200 JSON on `/api/v1/health` and the frontend root on port 5173 responds with HTTP 200 HTML. The backend and frontend were restarted and are running on `0.0.0.0:8000` and `0.0.0.0:5173`.

## Effective provider/batching evidence

The real provider probe returned HTTP 200 with `application/json; charset=utf-8` using model `gpt-5-mini`. Backend logs show the configured provider base URL without exposing credentials and show `batch_size=2`.

## Controlled extraction results

The controlled CSV tests used real ingestion and the real configured LLM provider. Test A (1 record, Job 1217) returned HTTP 200 JSON in 26.432 seconds. Test B (3 records, Job 1218) returned HTTP 200 JSON in 85.505 seconds and used two LLM batches. Test C (10 records, Job 1219) returned HTTP 200 JSON in 184.585 seconds and used five LLM batches. The returned JSON contained `extracted_data`, `extracted_products`, `job_id`, `product_id`, `product_ids`, and `status`.

## Frontend verification

The browser preview loaded the React dashboard and opened the Ingestion page. The PDF, Website, and CSV tabs rendered. A browser CSV upload created Job 1230 with `Records Extracted: 10`. The Product Intelligence button entered its loading state and the backend log recorded `Processing 10 evidence chunks in 5 LLM batches (batch_size=2)` for that request. The live request was still running at the time of this note.

## Downstream browser smoke tests

After Job 1230 completed, the browser displayed `Extracted Results (10 Products)` and row-level CSV provenance, including `CSV · browser-small-catalog.csv · Row 1`; no HTML/JSON parsing error was shown. The Products view rendered its persisted catalog route. Product Analyzer rendered its existing product selector and controlled-discovery panel. Commerce Output rendered its product selector and honest `No Commerce Output snapshot is available yet` state. The Dashboard loaded its evaluator overview and displayed persisted catalog metrics.

The browser did briefly show `Backend API is not responding` while the synchronous five-batch extraction occupied the single backend worker; once the extraction returned HTTP 200, health requests recovered and the UI rendered the ten products. This is an observed remaining responsiveness limitation, not an extraction correctness failure.
