# Hackathon Submission Checklist

## Application

- [ ] Backend starts with the documented environment variables.
- [ ] Frontend builds with `pnpm run build`.
- [ ] Backend liveness endpoint returns success.
- [ ] Backend readiness endpoint returns success when the database is available.
- [ ] Frontend uses the configured API base URL and does not depend on a hardcoded production localhost URL.
- [ ] Dashboard loads without a runtime error.

## Evaluator walkthrough

- [ ] Open Dashboard and show the value proposition and workflow strip.
- [ ] Show persisted system metrics and explain that they are computed from application state.
- [ ] Select a real product from Demo Catalog.
- [ ] Show raw values, normalized values, confidence, evidence, and provenance.
- [ ] Show conflicts and human-review state when present.
- [ ] Open Product Analyzer and show the staged pipeline.
- [ ] Open Commerce Output and show field-level auditability.
- [ ] Download at least one delivery format: JSON, CSV, or XLSX.
- [ ] Open Catalog Processing and show row validation, progress, review queue, and export.

## Data honesty

- [ ] Do not call rule-based quality metrics ground-truth accuracy.
- [ ] Do not claim accuracy without an official expected-output dataset.
- [ ] State that official Delivery Format fields, LOVs, UOMs, and limits are used only when supplied/imported.
- [ ] Do not claim a discovery provider is configured unless the live status says so.
- [ ] Do not present unavailable fields as inferred facts.

## Security and trust

- [ ] No API keys are present in source code or frontend bundles.
- [ ] Upload limits and safe filenames are enabled.
- [ ] CORS is configured for the intended frontend origin in deployment.
- [ ] Source isolation and provenance are visible in the demo.
- [ ] Conflicts remain non-destructive and reviewable.

## Submission artifacts

- [ ] `README.md`
- [ ] `docs/ARCHITECTURE.md`
- [ ] `docs/DEMO_SCRIPT.md`
- [ ] `docs/JUDGE_QA.md`
- [ ] `docs/LIMITATIONS.md`
- [ ] `docs/SUBMISSION_CHECKLIST.md`
- [ ] Phase implementation reports and browser verification notes
- [ ] Backend regression result
- [ ] Frontend production build result
