"""Phase 7 controlled information-discovery endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.discovery import DiscoveryEvidence
from app.schemas.discovery_schema import (
    CrossSourceConflictResponse,
    DiscoveryDetailResponse,
    DiscoveryEvidenceResponse,
    DiscoveryProviderStatusResponse,
    DiscoveryRunResponse,
    DiscoverySourceResponse,
    DiscoveryStartRequest,
)
from app.services.discovery_service import DiscoveryService

router = APIRouter(prefix="/api/v1/discovery", tags=["discovery"])


def _evidence_response(row: DiscoveryEvidence) -> DiscoveryEvidenceResponse:
    return DiscoveryEvidenceResponse(
        id=row.id,
        source_id=row.candidate_source_id,
        source_url=row.source.canonical_url,
        source_title=row.source.title,
        source_type=row.source.source_type,
        attribute_name=row.attribute_name,
        raw_value=row.raw_value,
        normalized_value=row.normalized_value,
        quote=row.quote,
        page_number=row.page_number,
        extraction_method=row.extraction_method,
        evidence_quality=row.evidence_quality,
    )


@router.get("/provider-status", response_model=DiscoveryProviderStatusResponse)
def provider_status():
    return DiscoveryService.provider_status()


@router.post("/product/{product_id}", response_model=DiscoveryRunResponse)
def discover_product(product_id: int, payload: DiscoveryStartRequest, db: Session = Depends(get_db)):
    service = DiscoveryService(db)
    try:
        return service.run(product_id, payload.user_urls)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/product/{product_id}", response_model=DiscoveryDetailResponse)
def latest_discovery(product_id: int, db: Session = Depends(get_db)):
    service = DiscoveryService(db)
    try:
        run, queries, sources, evidence = service.detail(product_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return DiscoveryDetailResponse(
        run=run,
        queries=queries,
        sources=sources,
        evidence=[_evidence_response(row) for row in evidence],
    )


@router.get("/product/{product_id}/sources", response_model=list[DiscoverySourceResponse])
def discovery_sources(product_id: int, db: Session = Depends(get_db)):
    service = DiscoveryService(db)
    try:
        _, _, sources, _ = service.detail(product_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return sources


@router.get("/product/{product_id}/evidence", response_model=list[DiscoveryEvidenceResponse])
def discovery_evidence(product_id: int, db: Session = Depends(get_db)):
    service = DiscoveryService(db)
    try:
        _, _, _, evidence = service.detail(product_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [_evidence_response(row) for row in evidence]


@router.get("/product/{product_id}/cross-source-conflicts", response_model=list[CrossSourceConflictResponse])
def discovery_cross_source_conflicts(product_id: int, db: Session = Depends(get_db)):
    service = DiscoveryService(db)
    try:
        run, _, _, _ = service.detail(product_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return (run.summary or {}).get("cross_source_conflicts", [])
