"""Phase 9 catalog processing API."""
from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.utils.upload import read_upload_limited, safe_upload_filename
from app.models.catalog import CatalogBatch
from app.schemas.catalog_schema import (
    CatalogAggregationResponse,
    CatalogItemResponse,
    CatalogResultsResponse,
    CatalogRetryRequest,
    CatalogReviewQueueResponse,
    CatalogStartRequest,
    CatalogStatusResponse,
    CatalogUploadResponse,
    CatalogUploadValidationResponse,
)
from app.services.catalog_service import CatalogDomainError, CatalogService, process_catalog_batch_in_background

router = APIRouter(prefix="/api/v1/catalog", tags=["Catalog Processing"])


def _handle(error: CatalogDomainError) -> HTTPException:
    return HTTPException(status_code=error.status_code, detail=str(error))


@router.post("/batches/upload", response_model=CatalogUploadValidationResponse)
async def upload_catalog(file: UploadFile = File(...), dataset_name: Optional[str] = None, db: Session = Depends(get_db)):
    filename = safe_upload_filename(file.filename, "catalog.csv")
    if Path(filename).suffix.lower() not in {".csv", ".xlsx"}:
        raise HTTPException(status_code=400, detail="Catalog must be a CSV or XLSX file.")
    try:
        content = await read_upload_limited(file)
        with NamedTemporaryFile(prefix="catalog-upload-", suffix=Path(filename).suffix, delete=False) as temporary:
            temporary.write(content)
            path = Path(temporary.name)
        try:
            batch = CatalogService(db).create_batch(path, filename, dataset_name)
        finally:
            path.unlink(missing_ok=True)
        return CatalogService.upload_summary(batch)
    except CatalogDomainError as error:
        raise _handle(error)


@router.post("/batches/{batch_id}/start", response_model=CatalogStatusResponse)
def start_catalog(batch_id: int, request: CatalogStartRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    try:
        batch = CatalogService(db).start(batch_id, mode=request.mode, use_llm=request.use_llm)
        background_tasks.add_task(process_catalog_batch_in_background, batch_id, request.mode, request.use_llm)
        return CatalogService.status_payload(batch)
    except CatalogDomainError as error:
        raise _handle(error)


@router.get("/batches/{batch_id}/status", response_model=CatalogStatusResponse)
def catalog_status(batch_id: int, db: Session = Depends(get_db)):
    try:
        batch = db.query(CatalogBatch).filter_by(id=batch_id).first()
        if not batch:
            raise CatalogDomainError("Catalog batch not found.", 404)
        CatalogService(db).recalculate(batch_id)
        db.commit()
        return CatalogService.status_payload(batch)
    except CatalogDomainError as error:
        raise _handle(error)


@router.get("/batches/{batch_id}/progress", response_model=CatalogStatusResponse)
def catalog_progress(batch_id: int, db: Session = Depends(get_db)):
    return catalog_status(batch_id, db)


@router.get("/batches/{batch_id}/results", response_model=CatalogResultsResponse)
def catalog_results(batch_id: int, page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=1000), status: Optional[str] = None, search: Optional[str] = None, db: Session = Depends(get_db)):
    try:
        return CatalogService(db).results(batch_id, page, page_size, status, search)
    except CatalogDomainError as error:
        raise _handle(error)


@router.get("/batches/{batch_id}/failures", response_model=CatalogResultsResponse)
def catalog_failures(batch_id: int, page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=1000), db: Session = Depends(get_db)):
    return catalog_results(batch_id, page, page_size, "failed", None, db)


@router.post("/batches/{batch_id}/retry", response_model=CatalogStatusResponse)
def retry_catalog(batch_id: int, request: CatalogRetryRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    try:
        service = CatalogService(db)
        batch = service.retry(batch_id, request.item_ids or None)
        if request.start_immediately:
            service.start(batch_id, mode=request.mode, use_llm=False)
            background_tasks.add_task(process_catalog_batch_in_background, batch_id, request.mode, False, request.item_ids or None)
        return CatalogService.status_payload(batch)
    except CatalogDomainError as error:
        raise _handle(error)


@router.post("/batches/{batch_id}/cancel", response_model=CatalogStatusResponse)
def cancel_catalog(batch_id: int, db: Session = Depends(get_db)):
    try:
        return CatalogService.status_payload(CatalogService(db).cancel(batch_id))
    except CatalogDomainError as error:
        raise _handle(error)


@router.get("/batches/{batch_id}/summary", response_model=CatalogAggregationResponse)
def catalog_summary(batch_id: int, db: Session = Depends(get_db)):
    try:
        return CatalogService(db).aggregation(batch_id)
    except CatalogDomainError as error:
        raise _handle(error)


@router.get("/batches/{batch_id}/review-queue", response_model=CatalogReviewQueueResponse)
def catalog_review_queue(batch_id: int, db: Session = Depends(get_db)):
    try:
        return CatalogService(db).review_queue(batch_id)
    except CatalogDomainError as error:
        raise _handle(error)


@router.get("/batches/{batch_id}/export")
def catalog_export(batch_id: int, format: str = Query(..., pattern="^(csv|xlsx|json)$"), filter: str = Query("all", pattern="^(all|ready|review_required|failed)$"), db: Session = Depends(get_db)):
    try:
        content, media_type, filename = CatalogService(db).export(batch_id, format, filter)
        return Response(content=content, media_type=media_type, headers={"Content-Disposition": f'attachment; filename="{filename}"'})
    except CatalogDomainError as error:
        raise _handle(error)


@router.get("/batches/{batch_id}/reports/{report_type}")
def catalog_report(batch_id: int, report_type: str, db: Session = Depends(get_db)):
    try:
        service = CatalogService(db)
        if report_type == "catalog-summary":
            return service.aggregation(batch_id)
        if report_type == "failed-products":
            return service.results(batch_id, page=1, page_size=100000, status="failed")
        if report_type == "conflict-report":
            return {"batch_id": batch_id, "items": [item for item in service.results(batch_id, page=1, page_size=100000)["items"] if item["conflict_count"] > 0]}
        if report_type == "human-review-report":
            return service.review_queue(batch_id)
        if report_type == "evaluation-report":
            return service.aggregation(batch_id)
        raise CatalogDomainError("Unsupported catalog report type.", 400)
    except CatalogDomainError as error:
        raise _handle(error)
