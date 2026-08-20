# Local Manual Test Guide

## Local URLs

| Service | URL | Verification |
|---|---|---|
| Frontend | http://127.0.0.1:5175/ | React/Vite dashboard opened successfully in the browser |
| Backend liveness | http://127.0.0.1:8000/api/v1/health | HTTP 200; database healthy |
| Backend readiness | http://127.0.0.1:8000/api/v1/health/ready | HTTP 200; database ready |
| API documentation | http://127.0.0.1:8000/docs | Available because local `ENABLE_DOCS=True` |

Vite selected port 5175 because ports 5173 and 5174 were already occupied. The frontend proxy at `/api/v1` successfully forwarded requests to the backend on port 8000. No application functionality was changed.

## Recommended evaluator walkthrough

Open the frontend URL and begin on **Dashboard**. Confirm that the selected persisted catalog batch is `Unihack_SampleDataset-Input.csv`, that it reports 1,000 rows, and that the dashboard shows persisted metrics rather than fabricated values. The current local database contains 998 successfully processed products, 998 products requiring review, 100% evidence coverage, and 998 Commerce Output records. Ground-truth accuracy is correctly shown as unavailable because no official expected-output dataset is configured.

Use **Catalog Processing** to test the large-scale path. Upload `backend/data/Unihack_SampleDataset-Input.csv` and give the batch a descriptive dataset name. Confirm that the batch is created, the total row count is displayed, and the processing controls expose the source-only mode. Start the batch and monitor status, progress, processed rows, successful rows, invalid rows, failures, and review counts. Open the results table, use search and pagination, inspect the review queue, and verify that retry and cancellation controls are visible. Do not enable discovery for this local smoke test unless a provider is deliberately configured.

Use **Products** or the catalog results to open a persisted product. Confirm that the product identifier, title, manufacturer or brand values, extracted attributes, missing attributes, confidence, and evidence are displayed. The evidence should retain the source type and source-specific provenance. For CSV evidence, verify row-based provenance; for PDF evidence, verify page numbers; and for website evidence, verify the source URL.

Use **Product Analyzer** to test the single-product intelligence workflow. Select a product or upload a source through **Ingestion**. Test each input mode separately where practical: PDF upload, website URL ingestion, and CSV upload. Confirm the processing status, source type, extracted records or chunks, and errors. Then run product intelligence extraction using the current job. Verify that the result contains only evidence from the current job and that product identifiers are never invented. For a CSV containing multiple products, confirm that all rows are represented and that original values are retained.

Use **Product Investigations** to create or open an investigation for a product and inspect the matched source-backed product identity. Confirm that the investigation is scoped to its own jobs and evidence. Multi-source matching should show whether records refer to the same product while preserving the original sources and provenance.

Use **Conflicts** to inspect conflict detection. Open a product or investigation with multiple source records and review value, unit, missing-attribute, and identity conflict classifications. Confirm that normalized equivalents such as `400 V`, `400V`, and `400 volts` are not falsely treated as conflicting. Where a genuine conflict exists, verify that the application reports the severity, source agreement, evidence, and provenance without automatically overwriting either value.

Use **Evaluation** to inspect the distinction between rule-based quality evaluation and ground-truth evaluation. Confirm that rule checks can report completeness, normalization, UOM/LOV compliance where reference data exists, evidence coverage, placeholder removal, title or description checks, and character-limit checks only when limits are configured. Confirm that the interface says `Official ground truth dataset not available.` and does not display fabricated accuracy.

Use **Reference Data** to inspect the optional manufacturer, brand, LOV, and UOM reference-data areas. Since no official reference dataset is active in the current local database, unavailable reference-data metrics should remain explicitly unavailable rather than being represented as official compliance results.

Use **Commerce Output** to open the canonical output for a selected product. Verify that the final record retains raw values, normalized values, field-level validation, missing-field status, conflicts, confidence, review state, and evidence or provenance. Confirm that missing identifiers are displayed as `Not found in provided sources` when the source lacks a SKU or product ID, rather than being generated.

Use the Commerce Output download controls to export JSON, CSV, and XLSX. Open each downloaded file and confirm that the canonical record and field-level audit information are preserved. Also test the catalog-level export controls from Catalog Processing for JSON, CSV, and XLSX, using the all-products and review-required filters where available.

## Fast smoke-test sequence

For a short demonstration, use the existing persisted batch rather than reprocessing all 1,000 rows. Start on Dashboard, open one product, inspect evidence and provenance, open its review state, inspect conflicts, open Commerce Output, and download one JSON and one XLSX export. Then open Catalog Processing and show the persisted batch status, progress summary, review queue, and report controls.

For a full ingestion demonstration, upload a small CSV fixture with several rows and different column names, process it in source-only mode, inspect all resulting rows, open a product in Product Analyzer, inspect provenance, review conflicts and missing fields, and generate Commerce Output. This avoids requiring an LLM key while testing the source-backed pipeline. A live LLM extraction demonstration additionally requires the backend `OPENAI_API_KEY`, `OPENAI_API_BASE`, and `OPENAI_MODEL` variables to be configured.

## Expected local verification results

The backend returned HTTP 200 for liveness, readiness, and the dashboard overview endpoint. The dashboard overview returned persisted catalog metrics and explicitly marked official ground-truth accuracy as unavailable. The browser dashboard rendered successfully after refresh, with navigation for Dashboard, Ingestion, Products, Product Investigations, Evaluation, Reference Data, Product Analyzer, Conflicts, Commerce Output, and Catalog Processing.

## Notes

The local SQLite database and uploaded files are under `backend/data`, which is suitable for this local demonstration. This storage must be mounted to a durable volume at `/app/data` before production deployment. The local environment is configured for development and does not imply production persistence or public HTTPS availability.
