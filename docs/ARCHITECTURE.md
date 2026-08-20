# AI Product Intelligence & Trust Engine — Architecture

## Purpose

The platform converts product data from PDFs, websites, CSV files, and catalog batches into source-backed product intelligence and a reviewable Commerce Output record. It is designed for **traceability before automation**: raw values remain available, every accepted assertion retains provenance where available, conflicts are surfaced, and human decisions are recorded separately from extracted source values.

## System map

```text
PDF / Website / CSV / Catalog Upload
                |
                v
      Ingestion + Source Isolation
                |
                v
      Evidence Chunks + Provenance
                |
                v
    Product Understanding / Extraction
                |
        +-------+--------+
        |                |
        v                v
 Reference Validation   Controlled Discovery
        |                |
        +-------+--------+
                v
      Enrichment + Confidence
                |
        +-------+--------+
        |                |
        v                v
 Conflict Detection   Human Review
        |                |
        +-------+--------+
                v
     Commerce-Ready Output / Export
                |
                v
      Evaluator Dashboard / Catalog UI
```

## Backend layers

| Layer | Responsibility | Primary persisted state |
|---|---|---|
| Ingestion | Parse PDF, website, CSV, and catalog inputs | `IngestionJob`, `RawDocumentSource`, `EvidenceChunk`, `CatalogBatch`, `CatalogItem` |
| Product intelligence | Extract structured fields, classify products, discover schemas, calculate evidence-based confidence | `ProductRecord`, `ProductAttribute`, `EnrichmentRun`, `EnrichmentBatch` |
| Trust controls | Normalize comparisons, detect conflicts, verify discovery identity, preserve source isolation | `DataConflict`, discovery entities, review decisions |
| Reference data | Apply only imported manufacturer, brand, LOV, UOM, and fraction knowledge | Reference-data registries and normalization decisions |
| Delivery | Build stable, exportable field-audited records | `CommerceOutput`, `CommerceOutputField` |
| Evaluation | Keep rule-based quality separate from unavailable ground-truth accuracy | Evaluation runs and expected-dataset registry |
| Presentation | Expose evaluator overview, product demo, catalog scale, review, and exports | React/Vite/Tailwind frontend |

## Data and trust boundaries

**Source isolation:** extraction and investigation queries are scoped to the current ingestion job or explicitly attached investigation sources. A prior PDF, website, or CSV cannot silently contaminate a new job.

**Evidence provenance:** PDF evidence retains page information, website evidence retains URL information, CSV evidence retains source filename and row information, and catalog items retain original row snapshots. When lineage is unavailable, the UI reports that state instead of implying provenance.

**Non-destructive review:** human review decisions are stored separately. A reviewer can approve, reject, or propose a value without overwriting the source-backed extraction.

**Discovery safety:** external pages require safe URL handling, bounded fetching, identity verification, and evidence extraction from verified sources. No source URL or external assertion is fabricated.

**Reference-data honesty:** only reference datasets actually imported into the application are used for compliance checks. Missing official reference artifacts remain visibly unavailable.

## Evaluator paths

1. **Single-product path:** choose a persisted source-backed product, open Product Analyzer, inspect live stages, evidence, confidence, conflicts, and review, then open Commerce Output and download JSON, CSV, or XLSX.
2. **Catalog-scale path:** open Catalog Processing, upload or select the supplied catalog, inspect row validation and persisted progress, review invalid or flagged rows, then export filtered results.
3. **Evaluation path:** inspect rule-based quality metrics. Ground-truth accuracy remains unavailable unless an official expected-output dataset is uploaded.

## Deployment shape

The backend is a FastAPI service with SQLAlchemy persistence. The frontend is a Vite-built static React application. Local development uses the Vite proxy; deployed frontend builds use an environment-provided API base URL. The backend exposes liveness and readiness probes and supports container startup through the production-aware Dockerfile.

## What this architecture intentionally does not claim

The current platform does not claim a fabricated accuracy percentage, complete Unilog Delivery Format compliance, a universal LOV/UOM registry, automatic conflict resolution, RAG, FAISS, embeddings, a knowledge graph, ML trust scoring, or autonomous agents. Those remain outside the verified implementation boundary.
