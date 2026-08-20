"""Persistent background execution for LLM product extraction."""
from __future__ import annotations

from datetime import datetime
from inspect import signature
from math import ceil
from threading import Thread
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models.conflict import EvidenceChunk
from app.models.extraction import ExtractionJob
from app.models.ingestion import IngestionJob, RawDocumentSource
from app.models.product import ProductAttribute, ProductRecord
from app.schemas.product_schema import ExtractionAPIResponse, ProductExtractionResponse, ExtractionStatusResponse
from app.services.llm_extraction_service import (
    LLMExtractionError,
    LLMExtractionService,
)
from app.services.reference_data_service import ReferenceDataService
from app.utils.logger import logger


class ExtractionJobError(Exception):
    """Domain error for extraction-task lifecycle failures."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


class ExtractionCancelled(Exception):
    """Raised internally when a worker observes a persisted cancellation request."""


class ExtractionJobService:
    """Create, execute, monitor, and cancel persisted extraction tasks."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _now() -> datetime:
        return datetime.utcnow()

    @staticmethod
    def _chunk_payload(chunk: EvidenceChunk, source: RawDocumentSource, job: IngestionJob) -> Dict[str, Any]:
        stable_id = chunk.stable_chunk_id or f"chunk_{chunk.id}"
        if not chunk.stable_chunk_id:
            chunk.stable_chunk_id = stable_id

        source_type = chunk.source_type or job.source_type
        is_pdf = source_type == "pdf"
        is_csv = source_type == "csv"
        return {
            "evidence_chunk_id": stable_id,
            "chunk_id": stable_id,
            "text": chunk.snippet_text,
            "source_type": source_type,
            "source_identifier": chunk.source_identifier or source.file_name,
            "source_url": chunk.source_url or source.source_url,
            "page_number": chunk.page_number if is_pdf else None,
            "row_number": chunk.row_number or (chunk.page_number if is_csv else None),
        }

    def load_context(self, ingestion_job_id: int) -> tuple[IngestionJob, List[Dict[str, Any]], Dict[str, EvidenceChunk]]:
        """Load only evidence linked to the requested ingestion job and its sources."""
        job = self.db.query(IngestionJob).filter(IngestionJob.id == ingestion_job_id).first()
        if not job:
            raise ExtractionJobError("Ingestion job not found.", 404)

        sources = self.db.query(RawDocumentSource).filter(RawDocumentSource.job_id == ingestion_job_id).all()
        if not sources:
            raise ExtractionJobError("No document sources found for this job.", 404)

        source_by_id = {source.id: source for source in sources}
        chunks: List[Dict[str, Any]] = []
        chunk_objects: Dict[str, EvidenceChunk] = {}
        job_chunks = self.db.query(EvidenceChunk).filter(EvidenceChunk.job_id == ingestion_job_id).all()
        for chunk in job_chunks:
            source = source_by_id.get(chunk.source_id)
            if source is None:
                continue
            payload = self._chunk_payload(chunk, source, job)
            chunks.append(payload)
            chunk_objects[payload["evidence_chunk_id"]] = chunk

        if not chunks:
            raise ExtractionJobError("No evidence chunks available for extraction.")

        return job, chunks, chunk_objects

    def source_metadata(self, job: IngestionJob, sources: Optional[List[RawDocumentSource]] = None) -> Dict[str, Any]:
        if sources is None:
            sources = self.db.query(RawDocumentSource).filter(RawDocumentSource.job_id == job.id).all()
        return {
            "job_id": job.id,
            "source_type": job.source_type,
            "sources": [
                {"source_id": source.id, "file_name": source.file_name, "source_url": source.source_url}
                for source in sources
            ],
        }

    def create_task(self, ingestion_job_id: int, total_evidence_count: int) -> ExtractionJob:
        total_batches = ceil(total_evidence_count / max(1, int(settings.llm_batch_size)))
        task = ExtractionJob(
            ingestion_job_id=ingestion_job_id,
            status="QUEUED",
            total_batches=total_batches,
            total_evidence_count=total_evidence_count,
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    @staticmethod
    def _result_from_snapshot(snapshot: Optional[dict[str, Any]]) -> Optional[ExtractionAPIResponse]:
        if not snapshot:
            return None
        return ExtractionAPIResponse.model_validate(snapshot)

    @classmethod
    def status_payload(cls, task: ExtractionJob) -> dict[str, Any]:
        return {
            "job_id": task.ingestion_job_id,
            "task_id": task.id,
            "status": task.status,
            "current_batch": task.current_batch,
            "total_batches": task.total_batches,
            "processed_evidence_count": task.processed_evidence_count,
            "total_evidence_count": task.total_evidence_count,
            "extracted_product_count": task.extracted_product_count,
            "error": task.error_message,
            "cancellation_requested": bool(task.cancellation_requested),
            "created_at": task.created_at,
            "started_at": task.started_at,
            "completed_at": task.completed_at,
            "result": cls._result_from_snapshot(task.result_snapshot),
        }

    def latest_task(self, ingestion_job_id: int) -> ExtractionJob:
        task = (
            self.db.query(ExtractionJob)
            .filter(ExtractionJob.ingestion_job_id == ingestion_job_id)
            .order_by(ExtractionJob.id.desc())
            .first()
        )
        if not task:
            raise ExtractionJobError("No extraction task found for this ingestion job.", 404)
        return task

    def request_cancel(self, task_id: int) -> ExtractionJob:
        task = self.db.query(ExtractionJob).filter(ExtractionJob.id == task_id).first()
        if not task:
            raise ExtractionJobError("Extraction task not found.", 404)
        if task.status in {"COMPLETED", "FAILED", "CANCELLED"}:
            return task
        task.cancellation_requested = True
        if task.status == "QUEUED":
            task.status = "CANCELLED"
            task.completed_at = self._now()
        self.db.commit()
        self.db.refresh(task)
        return task

    def _set_failed(self, task: ExtractionJob, message: str) -> None:
        self.db.rollback()
        task = self.db.query(ExtractionJob).filter(ExtractionJob.id == task.id).one()
        task.status = "FAILED"
        task.error_message = message
        task.completed_at = self._now()
        self.db.commit()

    def _persist_extraction_result(
        self,
        job_id: int,
        validated_products: List[ProductExtractionResponse],
        chunks: List[Dict[str, Any]],
        chunk_objects: Dict[str, EvidenceChunk],
    ) -> ExtractionAPIResponse:
        product_ids: List[int] = []
        for validated in validated_products:
            product = None
            if validated.sku:
                product = self.db.query(ProductRecord).filter(ProductRecord.sku == validated.sku).first()

            if product is None:
                product = ProductRecord(
                    sku=validated.sku,
                    sku_evidence_chunk_id=validated.sku_evidence_chunk_id,
                    sku_source_type=validated.sku_source_type,
                    sku_source_identifier=validated.sku_source_identifier,
                    sku_source_url=validated.sku_source_url,
                    sku_page_number=validated.sku_page_number,
                    sku_row_number=validated.sku_row_number,
                    name=validated.product_name,
                    description=validated.description,
                    category=validated.category,
                    manufacturer=validated.brand,
                    status="draft",
                )
                self.db.add(product)
                self.db.flush()
            else:
                product.name = validated.product_name
                product.sku_evidence_chunk_id = validated.sku_evidence_chunk_id
                product.sku_source_type = validated.sku_source_type
                product.sku_source_identifier = validated.sku_source_identifier
                product.sku_source_url = validated.sku_source_url
                product.sku_page_number = validated.sku_page_number
                product.sku_row_number = validated.sku_row_number
                product.description = validated.description
                product.category = validated.category
                product.manufacturer = validated.brand

            product_ids.append(product.id)
            for attribute_data in validated.attributes:
                citation = attribute_data.evidence_chunk_id
                chunk = chunk_objects.get(citation or "")
                if chunk is None:
                    logger.warning("Attribute '%s' cites unknown evidence '%s'.", attribute_data.attribute_name, citation)
                    continue

                attribute = ProductAttribute(
                    product_id=product.id,
                    attribute_name=attribute_data.attribute_name,
                    raw_value=attribute_data.raw_value,
                    normalized_value=attribute_data.normalized_value,
                    unit=attribute_data.unit,
                    confidence_score=attribute_data.confidence_score,
                    is_verified=False,
                    source_type=attribute_data.source_type,
                    source_identifier=attribute_data.source_identifier,
                    source_url=attribute_data.source_url,
                    page_number=attribute_data.page_number,
                    row_number=attribute_data.row_number,
                    evidence_chunk_id=citation,
                )
                self.db.add(attribute)
                self.db.flush()
                chunk.attribute_id = attribute.id

            try:
                ReferenceDataService(self.db).validate_extracted_product(product)
            except Exception as reference_exc:
                logger.error("Reference-data validation failed for product %s: %s", product.id, reference_exc)

        self.db.commit()
        return ExtractionAPIResponse(
            job_id=job_id,
            product_id=product_ids[0] if product_ids else None,
            product_ids=product_ids,
            extracted_data=validated_products[0] if validated_products else None,
            extracted_products=validated_products,
            status="success",
        )

    def execute(self, task_id: int) -> None:
        """Run one extraction task using an isolated database session."""
        task = self.db.query(ExtractionJob).filter(ExtractionJob.id == task_id).first()
        if not task:
            logger.error("Extraction task %s was not found by worker.", task_id)
            return
        if task.status == "CANCELLED" or task.cancellation_requested:
            task.status = "CANCELLED"
            task.completed_at = task.completed_at or self._now()
            self.db.commit()
            return

        task.status = "PROCESSING"
        task.started_at = task.started_at or self._now()
        self.db.commit()

        try:
            job, chunks, chunk_objects = self.load_context(task.ingestion_job_id)
            sources = self.db.query(RawDocumentSource).filter(RawDocumentSource.job_id == job.id).all()

            def cancellation_check() -> bool:
                self.db.expire(task)
                self.db.refresh(task)
                return bool(task.cancellation_requested)

            def progress_callback(batch_index: int, total_batches: int, processed_count: int, product_count: int) -> None:
                self.db.expire(task)
                self.db.refresh(task)
                if task.cancellation_requested:
                    raise ExtractionCancelled()
                task.current_batch = batch_index
                task.total_batches = total_batches
                task.processed_evidence_count = processed_count
                task.extracted_product_count = product_count
                self.db.commit()

            source_metadata = self.source_metadata(job, sources)
            extraction_callable = LLMExtractionService.extract_from_chunks
            extraction_kwargs = {}
            supported_parameters = signature(extraction_callable).parameters
            if "progress_callback" in supported_parameters:
                extraction_kwargs["progress_callback"] = progress_callback
            if "cancellation_check" in supported_parameters:
                extraction_kwargs["cancellation_check"] = cancellation_check
            extracted_payload = extraction_callable(chunks, source_metadata, **extraction_kwargs)
            extracted_products_data = extracted_payload.get("products", [])
            validated_products = [ProductExtractionResponse.model_validate(product) for product in extracted_products_data]
            validated_products = LLMExtractionService._apply_provenance_to_multi(validated_products, chunks)
            response = self._persist_extraction_result(
                task.ingestion_job_id,
                validated_products,
                chunks,
                chunk_objects,
            )
            response.task_id = task.id
            response.extraction_status_url = f"/api/v1/extract/{task.ingestion_job_id}/status"
            task.status = "COMPLETED"
            task.current_batch = task.total_batches
            task.processed_evidence_count = task.total_evidence_count
            task.extracted_product_count = len(validated_products)
            task.result_snapshot = response.model_dump(mode="json")
            task.error_message = None
            task.completed_at = self._now()
            self.db.commit()
        except ExtractionCancelled:
            self.db.rollback()
            task = self.db.query(ExtractionJob).filter(ExtractionJob.id == task_id).one()
            task.status = "CANCELLED"
            task.error_message = "Extraction cancelled by request."
            task.completed_at = self._now()
            self.db.commit()
        except LLMExtractionError as exc:
            if str(exc).casefold().startswith("extraction cancelled"):
                self.db.rollback()
                task = self.db.query(ExtractionJob).filter(ExtractionJob.id == task_id).one()
                task.status = "CANCELLED"
                task.error_message = "Extraction cancelled by request."
                task.completed_at = self._now()
                self.db.commit()
            else:
                self._set_failed(task, str(exc))
                logger.error("Extraction task %s failed: %s", task_id, exc)
        except Exception as exc:
            logger.exception("Extraction task %s failed unexpectedly.", task_id)
            self._set_failed(task, "The extraction task failed unexpectedly.")

    @staticmethod
    def process_in_background(task_id: int) -> None:
        db = SessionLocal()
        try:
            ExtractionJobService(db).execute(task_id)
        finally:
            db.close()

    @staticmethod
    def launch_in_background(task_id: int) -> None:
        Thread(
            target=ExtractionJobService.process_in_background,
            args=(task_id,),
            name=f"extraction-{task_id}",
            daemon=True,
        ).start()

    @staticmethod
    def recover_pending_tasks() -> None:
        """Resume persisted queued/interrupted tasks in a single-process deployment."""
        db = SessionLocal()
        try:
            pending = (
                db.query(ExtractionJob)
                .filter(ExtractionJob.status.in_(["QUEUED", "PROCESSING"]))
                .all()
            )
            task_ids = [task.id for task in pending if not task.cancellation_requested]
            for task in pending:
                if task.status == "PROCESSING":
                    task.status = "QUEUED"
            db.commit()
        finally:
            db.close()

        for task_id in task_ids:
            Thread(
                target=ExtractionJobService.process_in_background,
                args=(task_id,),
                name=f"extraction-recovery-{task_id}",
                daemon=True,
            ).start()


__all__ = ["ExtractionJobError", "ExtractionCancelled", "ExtractionJobService"]

