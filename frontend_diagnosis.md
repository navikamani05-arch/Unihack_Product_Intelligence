Frontend diagnosis and browser verification (2026-08-12):

- The live preview initially rendered Dashboard successfully, but clicking Ingestion produced a blank white page.
- Browser console capture contained no text, but source inspection identified a definite React/TypeScript runtime/build defect: IngestionView declared `productResult`/`setProductResult` while its render and reset logic referenced undeclared `productResults`/`setProductResults`.
- Fixed IngestionView state to use an array `productResults` and normalized the extraction response to accept `extracted_products` or legacy `extracted_data`.
- Live preview was reloaded after the fix. Dashboard rendered; clicking Ingestion successfully rendered Multi-Source Ingestion with PDF, Website, and CSV tabs.
- Direct backend health check succeeded at `/api/v1/health`, returning status healthy.
- No source-isolation logic was changed by the frontend fix.

Remaining checks: complete backend pytest suite and confirm final frontend build/preview state.
Final live-preview verification: Dashboard loaded, and clicking Ingestion rendered the page successfully. The page exposed the PDF Upload, Website Enter URL, and CSV Upload controls with the expected Phase 2C feature text. The Extract Product Intelligence control remains wired to the current upload job in source code and is not affected by this rendering fix.
The live browser verification also confirmed that selecting Website renders the URL input and Process control, while selecting CSV renders the CSV drop zone and accepted file type. Both source tabs render without runtime errors.
