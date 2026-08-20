"""Phase 5 reference-data routes. All approvals require active official master data."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.utils.upload import read_upload_limited, safe_upload_filename
from app.models.reference_data import LOVEntry, UOMEntry
from app.schemas.reference_data_schema import (
    AttributeResolutionRequest,
    AttributeResolutionResponse,
    FractionNormalizationRequest,
    FractionNormalizationResponse,
    ImportResponse,
    ReferenceDatasetListResponse,
    ResolutionRequest,
    ResolutionResponse,
    UOMNormalizationRequest,
    UOMNormalizationResponse,
)
from app.services.reference_data_service import ReferenceDataService, comparison_value

router = APIRouter(prefix="/api/v1", tags=["Reference Data"])


def service(db: Session) -> ReferenceDataService:
    return ReferenceDataService(db)


@router.get("/reference-data", response_model=ReferenceDatasetListResponse)
def list_reference_data(db: Session = Depends(get_db)):
    return {"datasets": service(db).registry()}


@router.get("/reference-data/status", response_model=ReferenceDatasetListResponse)
def reference_data_status(db: Session = Depends(get_db)):
    return {"datasets": service(db).registry()}


@router.post("/reference-data/import", response_model=ImportResponse, status_code=status.HTTP_201_CREATED)
async def import_reference_data(
    file: UploadFile = File(...),
    dataset_type: Optional[str] = Form(None),
    version: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    filename = safe_upload_filename(file.filename, "reference-data.csv")
    suffix = Path(filename).suffix.casefold()
    if suffix not in {".csv", ".xlsx", ".xls"}:
        raise HTTPException(status_code=400, detail="Reference data must be CSV, XLSX, or XLS.")
    target_dir = Path(settings.reference_data_directory)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{uuid4().hex}_{filename}"
    content = await read_upload_limited(file)
    with target.open("wb") as buffer:
        buffer.write(content)
    try:
        return service(db).import_dataset(target, dataset_type=dataset_type, version=version)
    except ValueError as exc:
        target.unlink(missing_ok=True)
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Reference-data import failed; no dataset was activated.") from exc


@router.get("/manufacturers/search", response_model=ResolutionResponse)
def search_manufacturers(q: Optional[str] = None, db: Session = Depends(get_db)):
    return service(db).resolve_manufacturer(q)


@router.get("/brands/search", response_model=ResolutionResponse)
def search_brands(q: Optional[str] = None, manufacturer: Optional[str] = None, db: Session = Depends(get_db)):
    return service(db).resolve_brand(q, manufacturer)


@router.post("/resolve/manufacturer", response_model=ResolutionResponse)
def resolve_manufacturer(payload: ResolutionRequest, db: Session = Depends(get_db)):
    return service(db).resolve_manufacturer(payload.value or payload.manufacturer_value)


@router.post("/resolve/brand", response_model=ResolutionResponse)
def resolve_brand(payload: ResolutionRequest, db: Session = Depends(get_db)):
    return service(db).resolve_brand(payload.value or payload.brand_value, payload.manufacturer_value)


@router.post("/resolve/attribute", response_model=AttributeResolutionResponse)
def resolve_attribute(payload: AttributeResolutionRequest, db: Session = Depends(get_db)):
    return service(db).resolve_attribute(payload.classpath, payload.leaf_node, payload.attribute, payload.candidate_value)


@router.post("/normalize/uom", response_model=UOMNormalizationResponse)
def normalize_uom(payload: UOMNormalizationRequest, db: Session = Depends(get_db)):
    return service(db).normalize_uom(payload.value, payload.uom)


@router.post("/normalize/fraction", response_model=FractionNormalizationResponse)
def normalize_fraction(payload: FractionNormalizationRequest, db: Session = Depends(get_db)):
    return service(db).normalize_fraction(payload.value)


@router.get("/lov/{classpath}")
def lov_for_classpath(classpath: str, attribute: Optional[str] = None, db: Session = Depends(get_db)) -> dict[str, Any]:
    reference = service(db)
    datasets = reference._active_datasets("lov", "faucets_lov", "fittings_lov")
    if not datasets:
        return {"status": "REFERENCE_DATA_UNAVAILABLE", "classpath": classpath, "entries": [], "explanation": "No active official LOV dataset has been imported."}
    query = db.query(LOVEntry).filter(LOVEntry.dataset_id.in_([dataset.id for dataset in datasets]), LOVEntry.classpath_comparison == comparison_value(classpath))
    if attribute:
        query = query.filter(LOVEntry.attribute_comparison == comparison_value(attribute))
    entries = query.all()
    names = sorted({entry.dataset.name for entry in entries})
    return {"status": "AVAILABLE", "classpath": classpath, "reference_dataset": ", ".join(names) if names else None, "entries": [{"attribute_label": entry.normalized_label or entry.attribute_label, "attribute_values": entry.normalized_values or entry.attribute_values, "filtering_flag": entry.filtering_flag, "guidelines": entry.guidelines, "remarks": entry.remarks, "leaf_node": entry.leaf_node, "reference_dataset": entry.dataset.name} for entry in entries]}
