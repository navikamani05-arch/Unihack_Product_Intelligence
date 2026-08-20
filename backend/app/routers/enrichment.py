"""API endpoints for additive source-backed product enrichment."""
from __future__ import annotations

import csv
import io
import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.enrichment import EnrichmentRun
from app.models.product import ProductRecord
from app.schemas.enrichment_schema import (
    EnrichmentAnalyzeRequest,
    EnrichmentBatchRequest,
    EnrichmentBatchSchema,
    EnrichmentOutputSchema,
    EnrichmentProductListItem,
    EnrichmentReviewRequest,
    EnrichmentRunSchema,
)
from app.services.enrichment.pipeline import EnrichmentPipeline

router = APIRouter(prefix="/api/v1", tags=["enrichment"])


def _run_or_404(db: Session, product_id: int) -> EnrichmentRun:
    run = EnrichmentPipeline(db).latest(product_id)
    if not run:
        raise HTTPException(status_code=404, detail="No enrichment run is available for this product.")
    return run


@router.get("/enrichment/products", response_model=list[EnrichmentProductListItem])
def list_products(limit: int = Query(default=100, ge=1, le=500), db: Session = Depends(get_db)):
    """Lists existing products for Product Analyzer selection; no global evidence is returned."""
    return db.query(ProductRecord).order_by(ProductRecord.id.desc()).limit(limit).all()


@router.post("/analyze/batch", response_model=EnrichmentBatchSchema)
def analyze_batch(request: EnrichmentBatchRequest, db: Session = Depends(get_db)):
    try:
        return EnrichmentPipeline(db).batch(request.product_ids, retry_failed=request.retry_failed, mode=request.mode)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Batch enrichment could not complete: {exc}") from exc


@router.post("/analyze/batch/{batch_id}/resume", response_model=EnrichmentBatchSchema)
def resume_batch(batch_id: int, db: Session = Depends(get_db)):
    from app.models.enrichment import EnrichmentBatch
    batch = db.query(EnrichmentBatch).filter_by(id=batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Enrichment batch was not found.")
    return EnrichmentPipeline(db).batch(list(batch.requested_product_ids or []), retry_failed=True)


@router.post("/analyze/{product_id}", response_model=EnrichmentRunSchema)
def analyze_product(product_id: int, request: EnrichmentAnalyzeRequest | None = None, db: Session = Depends(get_db)):
    try:
        run = EnrichmentPipeline(db).analyze(
            product_id,
            use_llm=bool(request and request.use_llm),
            mode=request.mode if request else "SOURCE_ONLY",
        )
        return run
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Enrichment could not complete: {exc}") from exc


@router.get("/enrichment/{product_id}", response_model=EnrichmentOutputSchema)
def enrichment_result(product_id: int, db: Session = Depends(get_db)):
    pipeline = EnrichmentPipeline(db)
    run = _run_or_404(db, product_id)
    payload = pipeline.output(run)
    product = payload.get("product") or {
        "id": product_id,
        "name": None,
        "manufacturer": None,
        "sku": None,
    }
    return {
        "run": run,
        "product": product,
        "attributes": pipeline.attributes(run),
        "evidence": pipeline.evidence(run),
        "conflicts": pipeline.conflicts(run),
        "review_decisions": pipeline.reviews(run.id),
    }


@router.get("/enrichment/{product_id}/evidence")
def enrichment_evidence(product_id: int, db: Session = Depends(get_db)):
    pipeline = EnrichmentPipeline(db)
    return pipeline.evidence(_run_or_404(db, product_id))


@router.get("/enrichment/{product_id}/conflicts")
def enrichment_conflicts(product_id: int, db: Session = Depends(get_db)):
    pipeline = EnrichmentPipeline(db)
    return pipeline.conflicts(_run_or_404(db, product_id))


@router.get("/enrichment/{product_id}/attributes")
def enrichment_attributes(product_id: int, db: Session = Depends(get_db)):
    pipeline = EnrichmentPipeline(db)
    return pipeline.attributes(_run_or_404(db, product_id))


@router.get("/enrichment/{product_id}/export")
def export_enrichment(product_id: int, format: Literal["json", "csv"] = "json", db: Session = Depends(get_db)):
    pipeline = EnrichmentPipeline(db)
    run = _run_or_404(db, product_id)
    output = pipeline.output(run)
    if format == "json":
        return Response(content=json.dumps(output, default=str, indent=2), media_type="application/json", headers={"Content-Disposition": f"attachment; filename=enrichment-{product_id}.json"})
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=["product_id", "attribute", "raw_value", "normalized_value", "unit", "confidence", "validation_status", "evidence_count"])
    writer.writeheader()
    for name, value in (output.get("attributes") or {}).items():
        writer.writerow({"product_id": product_id, "attribute": name, "raw_value": value.get("raw_value"), "normalized_value": value.get("normalized_value"), "unit": value.get("unit"), "confidence": value.get("confidence"), "validation_status": value.get("validation_status"), "evidence_count": len(value.get("evidence") or [])})
    return Response(content=stream.getvalue(), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=enrichment-{product_id}.csv"})


@router.post("/enrichment/{product_id}/review")
def review_enrichment(product_id: int, request: EnrichmentReviewRequest, db: Session = Depends(get_db)):
    pipeline = EnrichmentPipeline(db)
    try:
        decision = pipeline.review(_run_or_404(db, product_id), request.action, request.attribute_id, request.value, request.reason)
        return {"id": decision.id, "decision": decision.decision, "attribute_id": decision.attribute_id, "value": decision.reviewer_value, "reason": decision.reason, "created_at": decision.created_at}
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
