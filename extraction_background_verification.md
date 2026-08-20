## Browser verification

At preview URL https://5173-iu2oeaz8c1kgdpfjpkor2-f39f59f6.sg1.manus.computer/ the Ingestion CSV flow accepted browser-background-one.csv and created Job ID 1240 with 1 record. Clicking Product Intelligence immediately changed the button to "Product Intelligence in progress..." and displayed:

- Extraction status: Processing
- Batch: 0 / 1
- Evidence processed: 0 / 1
- Products extracted: 0
- Cancel control

This demonstrates that the original extraction POST no longer remains open for the LLM operation and that the UI is polling a persisted task status.

The one-row task was still processing at the last browser view; backend real smoke tests independently verified terminal completion and JSON result for one record.

## Backend real smoke tests

Provider probe: configured=true, model=gpt-5-mini, HTTP 200, application/json, JSON response, 3.113 seconds.

Queued extraction smoke tests:

- 1 record, Job 1236 / Task 1: POST queue latency 0.019s, initial QUEUED, terminal COMPLETED, 1 batch, 1 product, total 38.278s.
- 3 records, Job 1237 / Task 2: POST queue latency 0.014s, initial QUEUED, terminal COMPLETED, 2 batches, 3 products, total 64.409s.
- 10 records, Job 1238 / Task 3: POST queue latency 0.012s, initial QUEUED, terminal COMPLETED, 5 batches, 10 products, total 171.855s.

All terminal responses were valid JSON and retained product counts. Health checks after each task returned HTTP 200 with approximately 2ms latency.

A separate live three-record health probe repeatedly called /api/v1/health during extraction: zero non-200 responses, maximum observed health latency 0.0062s, and total task duration 71.497s.
## Browser completion evidence

After the backend task completed, the browser status panel updated to Completed with Batch 1 / 1, Evidence processed 1 / 1, and Products extracted 1. The page rendered Extracted Results (1 Product), SKU/Product ID BROWSER-BG-001, and CSV provenance `browser-background-one.csv · Row 1`. The browser therefore verified the complete queued flow: immediate processing state, polling, terminal completion, result hydration, and provenance preservation.
