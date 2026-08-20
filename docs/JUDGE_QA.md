# Judge Q&A

## What is the core problem?

Commerce teams receive product information in inconsistent PDFs, websites, CSVs, and catalogs. The challenge is not merely extracting text; it is producing a usable product record while preserving evidence, handling missing values, surfacing conflicts, and making the result reviewable.

## Where does AI contribute?

AI-compatible extraction and enrichment stages help interpret product descriptions, identify structured attributes, classify products, discover an attribute schema, and produce evidence-aware confidence. The system does not present model output as unquestionable truth.

## What is deterministic?

Source isolation, file parsing, row preservation, safe URL handling, comparison normalization, conflict detection, reference-data checks, unit normalization, review-state propagation, export shaping, and catalog aggregation are implemented as deterministic application behavior.

## What happens when two sources disagree?

Both source-backed values remain available. The system normalizes comparable values, records the conflict and severity, preserves provenance, and sends the item to human review. It does not automatically select a winner or overwrite the original extraction.

## Can the system hallucinate a SKU?

No. A product identifier is accepted only when an explicit identifier is present in the source. Otherwise the UI reports that the product ID was not found in the provided sources.

## Does the system fabricate missing attributes?

No. Missing attributes remain missing or review-required. The product and field statuses explain what is unavailable.

## What is the trust model?

Trust is evidence-first and status-based: source provenance, evidence availability, confidence, validation status, conflicts, and review state are shown together. A confidence value is not an accuracy claim.

## What is the catalog-scale proof?

The supplied 1,000-row catalog is processed through persisted validation and batch lifecycle state. The verified demonstration batch contains 1,000 total rows, 998 valid rows, 2 invalid rows retained for review, 998 successful processing results, and 0 processing failures.

## What does “ground-truth unavailable” mean?

The available input catalog is not an official expected-output dataset. The dashboard therefore does not calculate or display ground-truth accuracy. If an official expected-output CSV/XLSX is supplied later, the existing evaluation architecture can compare generated fields against it.

## Does the platform claim complete Unilog compliance?

No. Manufacturer, brand, LOV, UOM, and character-limit checks are applied only when corresponding official/reference data has actually been imported. Unsupported checks are visibly unavailable rather than treated as passes.

## What is the most important product decision?

The platform makes uncertainty visible. It separates source-backed extraction, normalization, validation, discovery, human review, and delivery instead of hiding all decisions inside a single opaque score.

## What is intentionally not implemented?

The verified scope does not include RAG, FAISS, embeddings, knowledge graphs, ML trust scoring, LangGraph agents, automatic conflict resolution, or fabricated benchmark accuracy.

## Additional evaluator questions

### Why is this different from simple web scraping?

Scraping only retrieves page text. This platform also preserves source identity, creates evidence chunks, extracts structured product attributes, normalizes values, detects conflicts, validates against available reference data, routes uncertainty to review, and produces an auditable Commerce Output record.

### How does the system scale to 1,000 or more products?

The Catalog Processing layer persists a batch and each row separately, validates before processing, uses bounded row-by-row work, records progress, isolates failures, supports retry and cancellation, preserves original row numbers, and exports aggregate results. The verified supplied batch processed 998 valid rows successfully with 0 processing failures.

### How would this work in production?

The repository includes environment-driven configuration, bounded uploads, safe filenames, production-aware logging, CORS controls, liveness and readiness probes, a production-aware backend container, Vercel-oriented frontend configuration, and documented deployment steps. A real deployment still requires operator-provided infrastructure, database, storage, domain, and secrets.

### What is the business value?

The system reduces manual product-data preparation, makes missing and conflicting information visible before publication, preserves supplier evidence for audit, and turns an unstructured or inconsistent catalog into a reviewable delivery workflow. The business value is governed speed and traceability, not an unsupported accuracy percentage.

### What would you build next?

With the corresponding official data and business requirements, the next steps would be broader reference-data coverage, stronger asynchronous worker infrastructure for very large catalogs, richer reviewer workflow controls, production object storage, and measured evaluation against an official expected-output dataset. Those additions would be implemented only with supplied specifications and observed validation data.
