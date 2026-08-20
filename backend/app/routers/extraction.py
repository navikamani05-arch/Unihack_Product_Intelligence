"""API routes for structured AI product intelligence extraction."""
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.extraction import ExtractionJob
from app.models.product import ProductAttribute, ProductRecord
from app.schemas.product_schema import ExtractionAPIResponse, ExtractionStatusResponse
from app.services.extraction_job_service import ExtractionJobError, ExtractionJobService
from app.utils.logger import logger

router = APIRouter(prefix="/api/v1", tags=["Extraction"])


def _handle(error: ExtractionJobError) -> HTTPException:
    return HTTPException(status_code=error.status_code, detail=str(error))


@router.post("/extract/{job_id}", response_model=ExtractionAPIResponse)
def extract_product_intelligence(
    job_id: int,
    wait: bool = Query(False, description="Wait for completion for legacy synchronous callers."),
    db: Session = Depends(get_db),
):
    """Queue validated product extraction and return a persistent task identifier."""
    try:
        service = ExtractionJobService(db)
        _, chunks, _ = service.load_context(job_id)

        active_task = (
            db.query(ExtractionJob)
            .filter(
                ExtractionJob.ingestion_job_id == job_id,
                ExtractionJob.status.in_(["QUEUED", "PROCESSING"]),
            )
            .order_by(ExtractionJob.id.desc())
            .first()
        )
        if active_task:
            task = active_task
        else:
            task = service.create_task(job_id, len(chunks))

        if wait:
            # Explicit compatibility path for older scripts/integrations. The default
            # frontend path is queued and returns immediately.
            service.execute(task.id)
            db.expire_all()
            completed_task = db.query(ExtractionJob).filter(ExtractionJob.id == task.id).one()
            if completed_task.status == "FAILED":
                raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=completed_task.error_message)
            if completed_task.status == "CANCELLED":
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=completed_task.error_message)
            result = ExtractionJobService.status_payload(completed_task).get("result")
            if result is None:
                return ExtractionAPIResponse(
                    job_id=job_id,
                    task_id=completed_task.id,
                    status=completed_task.status,
                    extraction_status_url=f"/api/v1/extract/{job_id}/status",
                )
            return result.model_copy(
                update={
                    "task_id": completed_task.id,
                    "extraction_status_url": f"/api/v1/extract/{job_id}/status",
                }
            )

        if task.status == "QUEUED" and not active_task:
            ExtractionJobService.launch_in_background(task.id)

        return ExtractionAPIResponse(
            job_id=job_id,
            task_id=task.id,
            status=task.status,
            extraction_status_url=f"/api/v1/extract/{job_id}/status",
        )
    except ExtractionJobError as error:
        raise _handle(error) from error
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("Could not queue extraction for job %s.", job_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The extraction task could not be started.",
        ) from exc


@router.get("/extract/{job_id}/status", response_model=ExtractionStatusResponse)
def extraction_status(job_id: int, db: Session = Depends(get_db)):
    """Return the latest persisted extraction-task status for an ingestion job."""
    try:
        task = ExtractionJobService(db).latest_task(job_id)
        return ExtractionJobService.status_payload(task)
    except ExtractionJobError as error:
        raise _handle(error) from error


@router.get("/extract/tasks/{task_id}/status", response_model=ExtractionStatusResponse)
def extraction_task_status(task_id: int, db: Session = Depends(get_db)):
    """Return persisted status for a specific extraction task."""
    task = db.query(ExtractionJob).filter(ExtractionJob.id == task_id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Extraction task not found")
    return ExtractionJobService.status_payload(task)


@router.post("/extract/{job_id}/cancel", response_model=ExtractionStatusResponse)
def cancel_extraction(job_id: int, db: Session = Depends(get_db)):
    """Request cancellation before the next provider batch; in-flight calls finish safely."""
    try:
        service = ExtractionJobService(db)
        task = service.latest_task(job_id)
        return ExtractionJobService.status_payload(service.request_cancel(task.id))
    except ExtractionJobError as error:
        raise _handle(error) from error


@router.post("/extract/tasks/{task_id}/cancel", response_model=ExtractionStatusResponse)
def cancel_extraction_task(task_id: int, db: Session = Depends(get_db)):
    """Request cancellation for a specific extraction task."""
    try:
        task = ExtractionJobService(db).request_cancel(task_id)
        return ExtractionJobService.status_payload(task)
    except ExtractionJobError as error:
        raise _handle(error) from error


@router.get("/products/{product_id}", response_model=Dict[str, Any])
def get_product_record(product_id: int, db: Session = Depends(get_db)):
    """Retrieve a product and its attribute-level provenance."""
    product = db.query(ProductRecord).filter(ProductRecord.id == product_id).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product record not found")

    attributes = db.query(ProductAttribute).filter(ProductAttribute.product_id == product_id).all()
    return {
        "id": product.id,
        "sku": product.sku,
        "sku_evidence_chunk_id": product.sku_evidence_chunk_id,
        "sku_source_type": product.sku_source_type,
        "sku_source_identifier": product.sku_source_identifier,
        "sku_source_url": product.sku_source_url,
        "sku_page_number": product.sku_page_number,
        "sku_row_number": product.sku_row_number,
        "name": product.name,
        "product_name": product.name,
        "brand": product.manufacturer,
        "manufacturer": product.manufacturer,
        "category": product.category,
        "description": product.description,
        "status": product.status,
        "created_at": product.created_at.isoformat() if product.created_at else None,
        "updated_at": product.updated_at.isoformat() if product.updated_at else None,
        "attributes": [
            {
                "id": attribute.id,
                "attribute_name": attribute.attribute_name,
                "raw_value": attribute.raw_value,
                "original_value": attribute.raw_value,
                "normalized_value": attribute.normalized_value,
                "unit": attribute.unit,
                "confidence_score": attribute.confidence_score,
                "is_verified": attribute.is_verified,
                "source_type": attribute.source_type,
                "source_identifier": attribute.source_identifier,
                "source_url": attribute.source_url,
                "page_number": attribute.page_number,
                "row_number": attribute.row_number,
                "evidence_chunk_id": attribute.evidence_chunk_id,
            }
            for attribute in attributes
        ],
    }
