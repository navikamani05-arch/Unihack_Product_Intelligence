"""API endpoints for Phase 4 rule-quality and future ground-truth evaluation."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.utils.upload import read_upload_limited, safe_upload_filename
from app.schemas.evaluation_schema import (
    EvaluationFailuresResponse,
    EvaluationProductResponse,
    EvaluationRunRequest,
    EvaluationSummaryResponse,
    GroundTruthAvailabilityResponse,
    GroundTruthComparisonResponse,
    GroundTruthSchemaProfileResponse,
)
from app.services.evaluation_service import EvaluationDomainError, EvaluationService

router = APIRouter(prefix="/api/v1/evaluation", tags=["Evaluation"])


def _raise(error: EvaluationDomainError) -> None:
    raise HTTPException(status_code=error.status_code, detail=error.message)


@router.post("/run", response_model=EvaluationSummaryResponse)
def run_evaluation(request: EvaluationRunRequest, db: Session = Depends(get_db)):
    """Run only the requested transparent evaluation mode."""
    try:
        if request.mode == "ground_truth":
            EvaluationService.run_ground_truth(db)
            return EvaluationService.ground_truth_summary(db)
        EvaluationService.run_rule_quality(db)
        return EvaluationService.latest_summary(db)
    except EvaluationDomainError as error:
        _raise(error)


@router.get("/summary", response_model=EvaluationSummaryResponse)
def evaluation_summary(
    mode: Literal["rule_quality", "ground_truth"] = "rule_quality",
    db: Session = Depends(get_db),
):
    """Return the latest selected-mode summary without triggering new evaluation."""
    return EvaluationService.ground_truth_summary(db) if mode == "ground_truth" else EvaluationService.latest_summary(db)


@router.get("/ground-truth/availability", response_model=GroundTruthAvailabilityResponse)
def ground_truth_availability(db: Session = Depends(get_db)):
    return EvaluationService.ground_truth_availability(db)


@router.get("/ground-truth/schema", response_model=GroundTruthSchemaProfileResponse)
def ground_truth_schema(db: Session = Depends(get_db)):
    try:
        return EvaluationService.ground_truth_schema(db)
    except EvaluationDomainError as error:
        _raise(error)


@router.post("/ground-truth/upload", response_model=GroundTruthAvailabilityResponse)
async def upload_ground_truth(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Register an official expected-output CSV/XLSX file; no expected values are inferred."""
    filename = safe_upload_filename(file.filename, "expected-output.csv")
    suffix = Path(filename).suffix.lower()
    if suffix not in {".csv", ".xlsx"}:
        raise HTTPException(status_code=400, detail="Expected output must be uploaded as CSV or XLSX.")
    temp_path: Optional[str] = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as handle:
            temp_path = handle.name
            handle.write(await read_upload_limited(file))
        EvaluationService.register_expected_dataset(db, Path(temp_path), filename)
        return EvaluationService.ground_truth_availability(db)
    except EvaluationDomainError as error:
        _raise(error)
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


@router.get("/products/{result_id}", response_model=EvaluationProductResponse)
def evaluation_product(result_id: int, db: Session = Depends(get_db)):
    try:
        return EvaluationService.product_result(db, result_id)
    except EvaluationDomainError as error:
        _raise(error)


@router.get("/failures", response_model=EvaluationFailuresResponse)
def evaluation_failures(run_id: Optional[int] = None, db: Session = Depends(get_db)):
    return EvaluationService.failures(db, run_id)


@router.get("/ground-truth/products/{product_id}", response_model=GroundTruthComparisonResponse)
def ground_truth_product(product_id: int, db: Session = Depends(get_db)):
    try:
        return EvaluationService.ground_truth_comparison(db, product_id)
    except EvaluationDomainError as error:
        _raise(error)
