from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.models.catalog import CatalogBatch, CatalogItem
from app.models.commerce_output import CommerceOutput
from app.models.conflict import DataConflict, EvidenceChunk
from app.models.discovery import DiscoveryRun
from app.models.enrichment import EnrichmentReviewDecision, EnrichmentRun
from app.models.evaluation import EvaluationExpectedDataset, EvaluationRun
from app.models.product import ProductAttribute, ProductRecord
from app.models.reference_data import ReferenceDataset, ProductNormalizationDecision
from app.schemas.dashboard_schema import (
    DashboardMetric,
    DashboardOverviewResponse,
    DashboardPipelineStage,
    DashboardProductDetailResponse,
    DashboardProductListItem,
    DashboardProductListResponse,
)
from app.services.catalog_service import CatalogService


class DashboardDomainError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class DashboardService:
    """Read-only evaluator dashboard aggregation over persisted source-backed records."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _iso(value: Any) -> Optional[str]:
        return value.isoformat() if hasattr(value, "isoformat") else value

    @staticmethod
    def _clean(value: Any) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def latest_batch(self) -> Optional[CatalogBatch]:
        completed = (
            self.db.query(CatalogBatch)
            .filter(CatalogBatch.status == "COMPLETED")
            .order_by(CatalogBatch.completed_at.desc(), CatalogBatch.id.desc())
            .first()
        )
        return completed or self.db.query(CatalogBatch).order_by(CatalogBatch.created_at.desc(), CatalogBatch.id.desc()).first()

    def _reference_availability(self) -> dict[str, Any]:
        active = (
            self.db.query(ReferenceDataset)
            .filter(ReferenceDataset.is_active.is_(True), ReferenceDataset.status.in_(["available", "imported", "active"]))
            .order_by(ReferenceDataset.id.asc())
            .all()
        )
        return {
            "status": "AVAILABLE" if active else "REFERENCE_DATA_UNAVAILABLE",
            "active_dataset_count": len(active),
            "datasets": [
                {"id": row.id, "name": row.name, "dataset_type": row.dataset_type, "version": row.version, "status": row.status}
                for row in active
            ],
            "explanation": "Official reference datasets are available for the imported registry." if active else "No active official reference dataset has been imported.",
        }

    def _ground_truth_availability(self) -> dict[str, Any]:
        expected = self.db.query(EvaluationExpectedDataset).order_by(EvaluationExpectedDataset.id.desc()).first()
        if expected:
            return {
                "status": "AVAILABLE",
                "message": "Official expected-output dataset is available for comparison.",
                "file_name": expected.file_name,
                "row_count": expected.row_count,
            }
        return {
            "status": "UNAVAILABLE",
            "message": "Official ground truth dataset not available.",
            "accuracy": None,
        }

    def _discovery_availability(self) -> dict[str, Any]:
        provider = (settings.discovery_provider or "none").strip()
        configured = bool(settings.discovery_provider_api_key)
        status = "AVAILABLE" if configured else "PROVIDER_NOT_CONFIGURED"
        return {
            "provider": provider,
            "status": status,
            "configured": configured,
            "explanation": "Controlled discovery is available through the configured provider." if configured else "No external discovery provider is configured; user-provided URLs remain the only optional discovery input.",
        }

    def _catalog_snapshot(self, batch: Optional[CatalogBatch]) -> Optional[dict[str, Any]]:
        if not batch:
            return None
        return {
            "id": batch.id,
            "dataset_name": batch.dataset_name,
            "filename": batch.file_name,
            "source_type": batch.source_type,
            "status": batch.status,
            "total_items": batch.total_items,
            "processed_items": batch.processed_items,
            "successful_items": batch.successful_items,
            "review_items": batch.review_items,
            "failed_items": batch.failed_items,
            "invalid_items": batch.invalid_items,
            "progress_percentage": round((batch.processed_items * 100 / batch.total_items), 1) if batch.total_items else 0.0,
            "created_at": self._iso(batch.created_at),
            "started_at": self._iso(batch.started_at),
            "completed_at": self._iso(batch.completed_at),
        }

    def overview(self) -> dict[str, Any]:
        batch = self.latest_batch()
        reference = self._reference_availability()
        ground_truth = self._ground_truth_availability()
        discovery = self._discovery_availability()
        latest_summary: dict[str, Any] = {}
        if batch:
            try:
                latest_summary = CatalogService(self.db).aggregation(batch.id)
            except Exception:
                latest_summary = {}

        total_products = int(latest_summary.get("processed", 0)) if latest_summary else 0
        ready = int(latest_summary.get("ready", 0)) if latest_summary else 0
        review = int(latest_summary.get("review_required", 0)) if latest_summary else 0
        conflicts = int(latest_summary.get("conflicts", 0)) if latest_summary else 0
        failed = int(latest_summary.get("failed", 0)) if latest_summary else 0
        evidence_coverage = (latest_summary.get("metrics") or {}).get("evidence_coverage")
        rule_quality = (latest_summary.get("metrics") or {}).get("rule_based_quality_score")
        commerce_count = (
            self.db.query(func.count(CatalogItem.id))
            .filter(CatalogItem.batch_id == batch.id, CatalogItem.commerce_output_id.isnot(None))
            .scalar()
            if batch else 0
        )
        demo_item = (
            self.db.query(CatalogItem)
            .filter(CatalogItem.batch_id == batch.id, CatalogItem.product_id.isnot(None))
            .order_by(CatalogItem.row_number.asc())
            .first()
            if batch else None
        )

        metrics = [
            DashboardMetric(key="products_processed", label="Products processed", value=total_products, explanation="Persisted products processed in the selected completed catalog batch."),
            DashboardMetric(key="ready_products", label="Ready products", value=ready, explanation="Products whose persisted enrichment result reached READY status."),
            DashboardMetric(key="review_queue", label="Needs review", value=review, explanation="Products with unresolved issues, missing data, conflicts, or non-ready output state."),
            DashboardMetric(key="evidence_coverage", label="Evidence coverage", value=evidence_coverage, status="AVAILABLE" if evidence_coverage is not None else "UNAVAILABLE", explanation="Coverage computed from persisted enrichment evidence counts."),
            DashboardMetric(key="conflict_rate", label="Conflict rate", value=(latest_summary.get("metrics") or {}).get("conflict_rate"), status="AVAILABLE" if latest_summary else "UNAVAILABLE", explanation="Rate computed from persisted product conflicts in the selected batch."),
            DashboardMetric(key="rule_based_quality_score", label="Rule-based quality score", value=rule_quality, status="AVAILABLE" if rule_quality is not None else "UNAVAILABLE", explanation="Existing rule-based quality metric; it is not ground-truth accuracy."),
            DashboardMetric(key="commerce_outputs", label="Commerce outputs", value=int(commerce_count or 0), explanation="Catalog rows linked to persisted Commerce Output snapshots."),
            DashboardMetric(key="ground_truth_accuracy", label="Ground-truth accuracy", value=None, status="UNAVAILABLE", explanation=ground_truth["message"]),
        ]
        pipeline = [
            DashboardPipelineStage(key="ingestion", label="Ingestion", count=int(batch.total_items if batch else 0), explanation="Rows accepted into the selected catalog batch."),
            DashboardPipelineStage(key="product_understanding", label="Product understanding", count=total_products, explanation="Rows materialized into source-backed products."),
            DashboardPipelineStage(key="attribute_extraction", label="Attribute extraction", count=int(batch.successful_items if batch else 0), explanation="Rows with successful persisted processing."),
            DashboardPipelineStage(key="conflict_detection", label="Conflict detection", count=conflicts, explanation="Products with persisted conflicts."),
            DashboardPipelineStage(key="review", label="Human review", count=review, explanation="Products routed to review rather than auto-approved."),
            DashboardPipelineStage(key="commerce_output", label="Commerce output", count=int(commerce_count or 0), explanation="Products with persisted canonical delivery snapshots."),
        ]
        return {
            "title": "AI Product Intelligence & Trust Engine",
            "subtitle": "Source-backed product intelligence, evidence verification, conflict detection, and commerce-ready delivery.",
            "latest_batch": self._catalog_snapshot(batch),
            "metrics": [metric.model_dump() for metric in metrics],
            "pipeline": [stage.model_dump() for stage in pipeline],
            "availability": {"reference_data": reference, "ground_truth": ground_truth, "discovery": discovery, "batch_summary": latest_summary},
            "demo_product_id": demo_item.product_id if demo_item else None,
            "generated_at": datetime.utcnow().isoformat(),
        }

    def _product_source_types(self, product: ProductRecord) -> list[str]:
        values = {a.source_type for a in product.attributes if a.source_type}
        if product.sku_source_type:
            values.add(product.sku_source_type)
        return sorted(values)

    def _latest_run(self, product_id: int) -> Optional[EnrichmentRun]:
        return self.db.query(EnrichmentRun).filter(EnrichmentRun.product_id == product_id).order_by(EnrichmentRun.id.desc()).first()

    def list_products(self, page: int = 1, page_size: int = 25, search: Optional[str] = None) -> dict[str, Any]:
        query = self.db.query(ProductRecord)
        if search:
            term = f"%{search.strip()}%"
            query = query.filter(or_(ProductRecord.sku.ilike(term), ProductRecord.name.ilike(term), ProductRecord.manufacturer.ilike(term)))
        total = query.count()
        products = query.order_by(ProductRecord.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
        items = [self._product_list_item(product) for product in products]
        return DashboardProductListResponse(items=items, total=total, page=page, page_size=page_size).model_dump()

    def _product_list_item(self, product: ProductRecord) -> dict[str, Any]:
        run = self._latest_run(product.id)
        output = self.db.query(CommerceOutput).filter(CommerceOutput.product_id == product.id).order_by(CommerceOutput.id.desc()).first()
        conflicts = self.db.query(DataConflict).filter(DataConflict.product_id == product.id).all()
        review_count = self.db.query(EnrichmentReviewDecision).filter(EnrichmentReviewDecision.product_id == product.id).count()
        return DashboardProductListItem(
            id=product.id,
            sku=product.sku,
            name=product.name,
            manufacturer=product.manufacturer,
            category=product.category,
            status=product.status,
            enrichment_status=run.product_status if run else None,
            commerce_status=output.status if output else None,
            confidence=run.overall_confidence if run else None,
            conflict_count=len(conflicts),
            review_count=review_count,
            evidence_count=run.evidence_count if run else 0,
            source_types=self._product_source_types(product),
        ).model_dump()

    def _raw_input(self, product: ProductRecord) -> dict[str, Any]:
        item = (
            self.db.query(CatalogItem)
            .join(CatalogBatch, CatalogBatch.id == CatalogItem.batch_id)
            .filter(CatalogItem.product_id == product.id)
            .order_by(CatalogItem.id.desc())
            .first()
        )
        if item:
            return {"batch_id": item.batch_id, "row_number": item.row_number, "filename": item.batch.file_name if item.batch else None, "input_snapshot": item.input_snapshot or {}}
        return {"input_snapshot": {}}

    @staticmethod
    def _attribute_value(attribute: ProductAttribute) -> Any:
        return {
            "id": attribute.id,
            "attribute_name": attribute.attribute_name,
            "raw_value": attribute.raw_value,
            "normalized_value": attribute.normalized_value,
            "unit": attribute.unit,
            "confidence": attribute.confidence_score,
            "source_type": attribute.source_type,
            "source_identifier": attribute.source_identifier,
            "source_url": attribute.source_url,
            "page_number": attribute.page_number,
            "row_number": attribute.row_number,
            "evidence_chunk_id": attribute.evidence_chunk_id,
            "is_verified": attribute.is_verified,
        }

    def _evidence(self, product: ProductRecord) -> list[dict[str, Any]]:
        attributes = {attribute.id: attribute for attribute in product.attributes}
        chunks = (
            self.db.query(EvidenceChunk)
            .filter(EvidenceChunk.attribute_id.in_(list(attributes)))
            .order_by(EvidenceChunk.id.asc())
            .all()
            if attributes else []
        )
        return [{
            "id": chunk.id,
            "stable_chunk_id": chunk.stable_chunk_id,
            "attribute_id": chunk.attribute_id,
            "attribute_name": attributes.get(chunk.attribute_id).attribute_name if attributes.get(chunk.attribute_id) else None,
            "snippet_text": chunk.snippet_text,
            "source_type": chunk.source_type,
            "source_identifier": chunk.source_identifier,
            "source_url": chunk.source_url,
            "page_number": chunk.page_number,
            "row_number": chunk.row_number,
            "job_id": chunk.job_id,
        } for chunk in chunks]

    def _conflicts(self, product_id: int) -> list[dict[str, Any]]:
        rows = self.db.query(DataConflict).filter(DataConflict.product_id == product_id).order_by(DataConflict.severity.desc(), DataConflict.id.desc()).all()
        return [{
            "id": row.id,
            "attribute_name": row.attribute_name,
            "conflict_type": row.conflict_type,
            "severity": row.severity,
            "status": row.status or row.resolution_status,
            "agreement_count": row.agreement_count,
            "total_sources": row.total_sources,
            "agreement_percentage": row.agreement_percentage,
            "source_a_name": row.source_a_name,
            "source_a_value": row.source_a_value,
            "source_b_name": row.source_b_name,
            "source_b_value": row.source_b_value,
            "suggested_value": row.suggested_value,
            "suggestion_reason": row.suggestion_reason,
            "evidence_snapshot": row.evidence_snapshot,
            "resolution_action": row.resolution_action,
            "resolution_reason": row.resolution_reason,
        } for row in rows]

    def detail(self, product_id: int) -> dict[str, Any]:
        product = (
            self.db.query(ProductRecord)
            .options(joinedload(ProductRecord.attributes))
            .filter(ProductRecord.id == product_id)
            .first()
        )
        if not product:
            raise DashboardDomainError("Product record not found.", 404)
        run = self._latest_run(product_id)
        output = self.db.query(CommerceOutput).filter(CommerceOutput.product_id == product_id).order_by(CommerceOutput.id.desc()).first()
        conflicts = self._conflicts(product_id)
        reviews = []
        if run:
            reviews = [{"id": row.id, "decision": row.decision, "attribute_id": row.attribute_id, "reviewer_value": row.reviewer_value, "reason": row.reason, "created_at": self._iso(row.created_at)} for row in self.db.query(EnrichmentReviewDecision).filter(EnrichmentReviewDecision.enrichment_run_id == run.id).order_by(EnrichmentReviewDecision.id.desc()).all()]
        discovery_run = self.db.query(DiscoveryRun).filter(DiscoveryRun.product_id == product_id).order_by(DiscoveryRun.id.desc()).first()
        discovery = None
        if discovery_run:
            discovery = {"id": discovery_run.id, "status": discovery_run.status, "provider": discovery_run.provider_name, "accepted_source_count": discovery_run.verified_count, "rejected_source_count": discovery_run.rejected_count, "evidence_count": discovery_run.evidence_count, "conflict_count": discovery_run.conflict_count, "created_at": self._iso(discovery_run.created_at)}
        run_snapshot = run.output_snapshot if run else {}
        output_payload = output.record_snapshot if output and output.record_snapshot else None
        before_after = {
            "before": self._raw_input(product),
            "after": output_payload or run_snapshot.get("record") or {"sku": product.sku, "name": product.name, "manufacturer": product.manufacturer, "category": product.category},
            "status": "AVAILABLE" if output_payload or run_snapshot else "UNAVAILABLE",
            "explanation": "The after view is built from persisted source-backed enrichment and Commerce Output snapshots; original input remains unchanged." if output_payload or run_snapshot else "No persisted enrichment result is available for this product.",
        }
        product_payload = {
            "id": product.id,
            "sku": product.sku,
            "sku_provenance": {"source_type": product.sku_source_type, "source_identifier": product.sku_source_identifier, "source_url": product.sku_source_url, "page_number": product.sku_page_number, "row_number": product.sku_row_number, "evidence_chunk_id": product.sku_evidence_chunk_id},
            "name": product.name,
            "description": product.description,
            "manufacturer": product.manufacturer,
            "category": product.category,
            "status": product.status,
        }
        explanation = []
        for attribute in product.attributes:
            explanation.append({"field": attribute.attribute_name, "value": attribute.normalized_value or attribute.raw_value, "raw_value": attribute.raw_value, "confidence": attribute.confidence_score, "source": {"source_type": attribute.source_type, "source_identifier": attribute.source_identifier, "source_url": attribute.source_url, "page_number": attribute.page_number, "row_number": attribute.row_number, "evidence_chunk_id": attribute.evidence_chunk_id}, "why": "Directly retained from the persisted source-backed attribute record; normalization and confidence remain visible for audit."})
        return DashboardProductDetailResponse(
            product=product_payload,
            raw_input=self._raw_input(product),
            before_after=before_after,
            pipeline=run.progress_log if run and isinstance(run.progress_log, list) else [],
            attributes=[self._attribute_value(attribute) for attribute in product.attributes],
            evidence=self._evidence(product),
            conflicts=conflicts,
            reviews=reviews,
            enrichment={"id": run.id, "status": run.status, "stage": run.stage, "product_status": run.product_status, "overall_confidence": run.overall_confidence, "missing_attributes": run.missing_attributes or [], "source_count": run.source_count, "evidence_count": run.evidence_count, "attribute_count": run.attribute_count, "conflict_count": run.conflict_count, "output_snapshot": run.output_snapshot} if run else None,
            discovery=discovery,
            commerce_output=output.record_snapshot if output else None,
            explanation=explanation,
            availability={"enrichment": "AVAILABLE" if run else "UNAVAILABLE", "evidence": "AVAILABLE" if self._evidence(product) else "UNAVAILABLE", "commerce_output": "AVAILABLE" if output else "UNAVAILABLE", "ground_truth_accuracy": "UNAVAILABLE"},
        ).model_dump()


__all__ = ["DashboardService", "DashboardDomainError"]

