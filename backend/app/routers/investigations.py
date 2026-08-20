"""API routes for Product Investigation and multi-source product matching."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.investigation_schema import (
    AvailableIngestionJobResponse,
    ConflictDetailResponse,
    ConflictResolutionRequest,
    InvestigationComparisonResponse,
    InvestigationConflictsResponse,
    InvestigationCreateRequest,
    InvestigationResponse,
)
from app.services.conflict_detection_service import ConflictDetectionService
from app.services.investigation_service import InvestigationError, ProductInvestigationService

router = APIRouter(prefix="/api/v1/investigations", tags=["Product Investigations"])


def _raise_domain_error(error: InvestigationError) -> None:
    message = str(error)
    if message.endswith("not found"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message) from error
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message) from error


@router.post("", response_model=InvestigationResponse, status_code=status.HTTP_201_CREATED)
def create_investigation(payload: InvestigationCreateRequest, db: Session = Depends(get_db)):
    """Create an empty investigation; sources are explicitly attached in a separate step."""
    investigation = ProductInvestigationService.create(db, payload.name, payload.description)
    return ProductInvestigationService.serialize(db, investigation)


@router.get("", response_model=List[InvestigationResponse])
def list_investigations(db: Session = Depends(get_db)):
    """List investigations without leaking any unattached ingestion jobs or evidence."""
    return ProductInvestigationService.list_investigations(db)


@router.get("/available-jobs", response_model=List[AvailableIngestionJobResponse])
def list_available_completed_jobs(db: Session = Depends(get_db)):
    """List completed jobs that a user may explicitly attach to an investigation."""
    return ProductInvestigationService.list_available_jobs(db)


@router.get("/{investigation_id}", response_model=InvestigationResponse)
def get_investigation(investigation_id: int, db: Session = Depends(get_db)):
    """Return an investigation and its explicitly attached source jobs."""
    try:
        investigation = ProductInvestigationService.get_or_raise(db, investigation_id)
        return ProductInvestigationService.serialize(db, investigation)
    except InvestigationError as error:
        _raise_domain_error(error)


@router.post("/{investigation_id}/sources/{job_id}", response_model=InvestigationResponse)
def attach_completed_job(investigation_id: int, job_id: int, db: Session = Depends(get_db)):
    """Reference an existing completed ingestion job without copying its evidence."""
    try:
        investigation = ProductInvestigationService.attach_job(db, investigation_id, job_id)
        return ProductInvestigationService.serialize(db, investigation)
    except InvestigationError as error:
        _raise_domain_error(error)


@router.get("/{investigation_id}/comparison", response_model=InvestigationComparisonResponse)
def get_investigation_comparison(investigation_id: int, db: Session = Depends(get_db)):
    """Build an explainable comparison from only the investigation's attached source jobs."""
    try:
        return ProductInvestigationService.comparison(db, investigation_id)
    except InvestigationError as error:
        _raise_domain_error(error)


@router.get("/{investigation_id}/conflicts", response_model=InvestigationConflictsResponse)
def get_investigation_conflicts(investigation_id: int, db: Session = Depends(get_db)):
    """Detect conflicts using only evidence from the investigation's explicitly attached jobs."""
    try:
        return ConflictDetectionService.detect_for_investigation(db, investigation_id)
    except InvestigationError as error:
        _raise_domain_error(error)


@router.get("/{investigation_id}/conflicts/{conflict_id}", response_model=ConflictDetailResponse)
def get_investigation_conflict_detail(
    investigation_id: int, conflict_id: int, db: Session = Depends(get_db)
):
    """Return the persisted evidence snapshot for one conflict within this investigation only."""
    return ConflictDetectionService.detail_for_conflict(db, investigation_id, conflict_id)


@router.post("/{investigation_id}/conflicts/{conflict_id}/resolve", response_model=ConflictDetailResponse)
def resolve_investigation_conflict(
    investigation_id: int,
    conflict_id: int,
    payload: ConflictResolutionRequest,
    db: Session = Depends(get_db),
):
    """Persist a human review decision without changing any source assertion or extracted attribute."""
    return ConflictDetectionService.resolve_conflict(db, investigation_id, conflict_id, payload)


@router.delete("/{investigation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_investigation(investigation_id: int, db: Session = Depends(get_db)):
    """Delete only the investigation and attachment rows, retaining original ingested data."""
    try:
        ProductInvestigationService.delete(db, investigation_id)
        return None
    except InvestigationError as error:
        _raise_domain_error(error)
