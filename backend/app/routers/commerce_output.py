"""Commerce-ready output generation and delivery endpoints."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.commerce_output_schema import (
    CommerceOutputGenerateRequest,
    CommerceOutputSchema,
)
from app.services.commerce_output_service import CommerceOutputService

router = APIRouter(prefix="/api/v1/commerce-output", tags=["commerce-output"])


def _service(db: Session) -> CommerceOutputService:
    return CommerceOutputService(db)


@router.post("/{product_id}/generate", response_model=CommerceOutputSchema)
def generate_commerce_output(product_id: int, request: CommerceOutputGenerateRequest | None = None, db: Session = Depends(get_db)):
    try:
        output = _service(db).generate(product_id, request.enrichment_run_id if request else None)
        return _service(db).payload(output)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Commerce Output generation failed: {exc}") from exc


@router.get("/{product_id}", response_model=CommerceOutputSchema)
def get_commerce_output(product_id: int, db: Session = Depends(get_db)):
    try:
        output = _service(db).ensure_latest(product_id)
        return _service(db).payload(output)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Commerce Output could not be loaded: {exc}") from exc


@router.get("/{product_id}/fields")
def get_commerce_output_fields(product_id: int, db: Session = Depends(get_db)):
    try:
        output = _service(db).ensure_latest(product_id)
        return _service(db).payload(output)["fields"]
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{product_id}/export")
def export_commerce_output(product_id: int, format: Literal["json", "csv", "xlsx"] = "json", db: Session = Depends(get_db)):
    try:
        service = _service(db)
        output = service.ensure_latest(product_id)
        body, media_type, filename = service.export(output, format)
        return Response(content=body, media_type=media_type, headers={"Content-Disposition": f"attachment; filename={filename}"})
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
