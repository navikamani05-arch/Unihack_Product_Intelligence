# Evaluator Demo Script

## Opening: 30 seconds

Say: **“AI Product Intelligence for Commerce turns raw product inputs into evidence-backed, reviewable, commerce-ready records. The key design choice is that the system shows not only a value, but where it came from, how it was normalized, whether it conflicts, and whether a human still needs to review it.”**

Open the Dashboard. Point out that the headline and metrics are computed from persisted application state. Mention the two honest badges: real source-backed data is available, while official expected-output ground truth remains unavailable unless supplied.

## Step 1 — Show the workflow: 30 seconds

Point to the workflow strip: **Raw Product Data → Product Understanding → Evidence Discovery → Validation → Enrichment → Human Review → Commerce-Ready Output → Catalog Scale.**

Say: **“This is one governed handoff chain, not a black-box score.”**

## Step 2 — Select a real product: 60–90 seconds

Scroll to **Demo catalog** and select a persisted product. Point out its source types, evidence count, and conflict count. Use the product detail panel to show:

- Raw input value and normalized value side by side.
- Confidence as evidence-based metadata, not ground-truth accuracy.
- PDF page, CSV row, or website URL provenance.
- Evidence snippets supporting selected fields.
- Conflicts preserved for review instead of silently resolved.

Say: **“A missing identifier is not guessed. A disagreement is not overwritten. The reviewer can see exactly what still needs attention.”**

## Step 3 — Open Product Analyzer: 60–90 seconds

Use the Product Analyzer action. Choose **Source Only** for the deterministic source-backed path. Explain that **Discovery Enabled** is optional and controlled: identity must be verified before external evidence is accepted, and no provider or page is fabricated.

Show the live pipeline stages, category/schema view, missing or review items, attribute evidence, and conflict section. If a provider is not configured, say: **“The safe no-provider state is intentional; external discovery never becomes an unsupported source of truth.”**

## Step 4 — Show Commerce Output: 60 seconds

Open **Commerce Output**. Generate or load the final record. Show:

- Product-level status: ready or review required.
- Field-level raw, normalized, and output values.
- Validation state and reference-data availability.
- Character-limit status only where an official limit exists.
- Provenance and evidence.
- Review and conflict propagation.

Download JSON first, then mention CSV and XLSX. Say: **“The delivery record is stable and exportable, but it remains auditable. It does not hide the source value behind a rewritten payload.”**

## Step 5 — Show catalog scale: 60–90 seconds

Open **Catalog Processing**. Point out the supplied 1,000-row dataset result when present: 1,000 rows validated, 998 valid rows queued, 2 invalid rows retained, 998 processed successfully, and 0 processing failures. These figures are persisted batch metrics, not fabricated benchmark claims.

Show search, filters, review queue, and export. Explain that invalid rows are retained for review and that row numbers and original snapshots are preserved.

## Step 6 — Close with trust: 30 seconds

Say: **“The system is designed to make uncertainty visible. AI contributes understanding and structured extraction; deterministic validation, source evidence, conflict detection, and human review govern what is delivered. Official ground-truth accuracy is not shown because the official expected-output dataset is not part of the supplied data.”**

## Three-minute version

| Time | Screen | Talking point |
|---|---|---|
| 0:00 | Dashboard hero | **Problem:** commerce teams start with sparse, inconsistent product data and need a trustworthy delivery record, not just scraped text. |
| 0:20 | Demo Catalog | Select a real persisted product and show Part Number, Product Description, Brand, Manufacturer, source type, and evidence count. |
| 0:40 | Product Analyzer | Open the analyzer and show product understanding, category, attributes, confidence, evidence, and provenance. Clarify that AI structures the record while evidence and rules govern it. |
| 1:10 | Discovery / evidence section | Explain identity verification, source ranking, evidence acceptance/rejection, and the safe no-provider state. External information is not accepted before identity verification. |
| 1:40 | Conflict / review | Show that disagreements, missing fields, and unsupported validations become review items instead of being silently resolved. |
| 2:00 | Commerce Output | Show the canonical record, field-level audit, provenance, validation, conflicts, and review state. Download JSON or mention CSV/XLSX. |
| 2:30 | Catalog Processing | Show the real supplied batch: 1,000 input rows, 998 valid, 2 invalid, 998 successfully processed, and 0 processing failures. |
| 2:50 | Dashboard close | **Impact:** the system makes product intelligence usable at commerce scale while keeping uncertainty and source lineage visible. Ground-truth accuracy is not claimed because the official expected-output dataset is unavailable. |

The **five-minute version** is the detailed walkthrough above. It adds deeper evidence-chain inspection, field-level raw-versus-normalized comparison, human-review context, controlled discovery controls, and export verification.
