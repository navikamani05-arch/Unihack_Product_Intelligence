"""Orchestrates additive Phase 6 enrichment using only persisted source-backed data."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session, joinedload

from app.models.conflict import DataConflict, EvidenceChunk
from app.models.enrichment import EnrichmentBatch, EnrichmentReviewDecision, EnrichmentRun
from app.models.product import ProductAttribute, ProductRecord
from app.models.reference_data import ProductNormalizationDecision
from app.services.enrichment.attribute_schema import discover_attribute_schema
from app.services.enrichment.category_classifier import classify_category
from app.services.enrichment.confidence_engine import attribute_confidence, overall_confidence, product_status
from app.services.enrichment.output_builder import build_output, evidence_payload
from app.services.enrichment.product_understanding import build_product_understanding
from app.services.reference_data_service import ReferenceDataService, comparison_value


class EnrichmentPipeline:
    """Sequential pipeline; it never creates a fact without persisted source evidence."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _now() -> datetime:
        return datetime.utcnow()

    def _stage(self, run: EnrichmentRun, stage: str, status: str, message: str) -> None:
        progress = list(run.progress_log or [])
        progress.append({"stage": stage, "status": status, "message": message, "timestamp": self._now().isoformat()})
        run.stage = stage
        run.progress_log = progress
        run.updated_at = self._now()
        self.db.flush()

    def _product_or_raise(self, product_id: int) -> ProductRecord:
        product = (
            self.db.query(ProductRecord)
            .options(joinedload(ProductRecord.attributes).joinedload(ProductAttribute.evidence_chunks))
            .filter(ProductRecord.id == product_id)
            .first()
        )
        if not product:
            raise LookupError(f"Product {product_id} was not found.")
        return product

    @staticmethod
    def _attribute_validation(attribute: ProductAttribute) -> tuple[str, Optional[str], bool]:
        decisions = []
        # Reference decisions are stored independently to preserve original attributes.
        # The caller supplies a session-level preloaded list through the private marker.
        decisions = list(getattr(attribute, "_enrichment_decisions", []) or [])
        invalid = next((item for item in decisions if item.status in {"NOT_IN_OFFICIAL_UOM", "BRAND_MANUFACTURER_MISMATCH", "REJECTED"}), None)
        unavailable = next((item for item in decisions if item.status == "REFERENCE_DATA_UNAVAILABLE"), None)
        if invalid:
            return "INVALID_REFERENCE_DATA", invalid.explanation, True
        if unavailable:
            return "REFERENCE_DATA_UNAVAILABLE", unavailable.explanation, False
        return "SOURCE_BACKED", None, False

    def _sources(self, product: ProductRecord) -> list[dict[str, Any]]:
        seen: set[tuple[Any, ...]] = set()
        items: list[dict[str, Any]] = []
        for attribute in product.attributes:
            for evidence in evidence_payload(attribute):
                key = (evidence.get("source_type"), evidence.get("source_identifier"), evidence.get("source_url"), evidence.get("page_number"), evidence.get("row_number"))
                if key not in seen:
                    seen.add(key)
                    items.append(evidence)
        if product.sku_source_identifier or product.sku_source_url:
            sku_source = {
                "evidence_chunk_id": product.sku_evidence_chunk_id,
                "source_type": product.sku_source_type,
                "source_identifier": product.sku_source_identifier,
                "source_url": product.sku_source_url,
                "page_number": product.sku_page_number,
                "row_number": product.sku_row_number,
                "quote": None,
                "authority": "unknown",
            }
            key = (sku_source["source_type"], sku_source["source_identifier"], sku_source["source_url"], sku_source["page_number"], sku_source["row_number"])
            if key not in seen:
                items.append(sku_source)
        return items

    def _conflicts(self, product_id: int) -> list[dict[str, Any]]:
        rows = self.db.query(DataConflict).filter(DataConflict.product_id == product_id).order_by(DataConflict.id.desc()).all()
        return [
            {
                "id": item.id,
                "attribute_name": item.attribute_name,
                "conflict_type": item.conflict_type,
                "severity": item.severity,
                "status": item.status,
                "resolution_status": getattr(item, "resolution_status", None),
                "suggested_value": item.suggested_value,
                "suggestion_reason": item.suggestion_reason,
                "agreement_count": item.agreement_count,
                "total_sources": item.total_sources,
                "evidence_snapshot": item.evidence_snapshot,
            }
            for item in rows
        ]

    def analyze(
        self,
        product_id: int,
        *,
        batch: Optional[EnrichmentBatch] = None,
        use_llm: bool = False,
        mode: str = "SOURCE_ONLY",
    ) -> EnrichmentRun:
        product = self._product_or_raise(product_id)
        run = EnrichmentRun(product_id=product.id, batch_id=batch.id if batch else None, status="running", stage="product_understanding", started_at=self._now(), progress_log=[])
        self.db.add(run)
        self.db.flush()
        try:
            understanding = build_product_understanding(product)
            run.product_understanding = understanding
            self._stage(run, "product_understanding", "completed", "Built a product understanding from existing source-backed product fields.")

            category = classify_category(self.db, product, understanding)
            run.category = category.get("category")
            run.category_path = category.get("category_path") or []
            run.category_confidence = category.get("confidence")
            run.product_understanding = {**understanding, "category_reason": category.get("reason"), "category_is_official": category.get("is_official", False)}
            self._stage(run, "category_classification", "completed" if category.get("category") else "warning", category.get("reason") or "No category could be established.")

            schema = discover_attribute_schema(self.db, product, category)
            run.schema_snapshot = schema
            self._stage(run, "attribute_schema_discovery", "completed", f"Discovered {len(schema)} relevant attribute definitions from active reference data and evidence.")

            search_terms = understanding.get("search_terms") or []
            if mode == "DISCOVERY_ENABLED":
                # Controlled discovery is isolated in its own persisted run. It may return an
                # explicit no-provider state; it never fabricates sources or attaches evidence
                # to this product without a verified identity match.
                from app.services.discovery_service import DiscoveryService

                self.db.flush()
                discovery_run = DiscoveryService(self.db).run(product.id)
                discovery_summary = dict(discovery_run.summary or {})
                run.product_understanding = {
                    **(run.product_understanding or {}),
                    "discovery_run_id": discovery_run.id,
                    "discovery_status": discovery_run.status,
                    "discovery_summary": discovery_summary,
                }
                stage_status = "completed" if discovery_run.verified_count else "warning"
                self._stage(
                    run,
                    "source_discovery",
                    stage_status,
                    discovery_summary.get("message")
                    or f"Controlled discovery completed with {discovery_run.verified_count} verified source(s); no unverified source was used.",
                )
            else:
                message = "Prepared source discovery search terms; Source Only mode reuses existing evidence and does not query external sources."
                self._stage(run, "source_discovery", "skipped", message if search_terms else "No reliable search term is available; no source was fabricated.")

            if use_llm:
                self._stage(run, "evidence_extraction", "completed", "Reused existing persisted LLM extraction; no unsupported fact generation was performed.")
            else:
                self._stage(run, "evidence_extraction", "completed", "Reused persisted extraction values and their existing evidence links.")

            # This only records advisory reference-data decisions or applies existing approved normalizations.
            ReferenceDataService(self.db).validate_extracted_product(product)
            self.db.flush()
            product = self._product_or_raise(product_id)

            decisions_by_attribute: dict[int, list[ProductNormalizationDecision]] = {}
            for decision in self.db.query(ProductNormalizationDecision).filter(ProductNormalizationDecision.product_id == product.id).all():
                if decision.attribute_id is not None:
                    decisions_by_attribute.setdefault(decision.attribute_id, []).append(decision)
            enriched: list[dict[str, Any]] = []
            invalid_reference = False
            for attribute in product.attributes:
                attribute._enrichment_decisions = decisions_by_attribute.get(attribute.id, [])
                validation_status, explanation, invalid = self._attribute_validation(attribute)
                evidence = evidence_payload(attribute)
                confidence = attribute_confidence(attribute, len(evidence), invalid)
                invalid_reference = invalid_reference or invalid
                enriched.append({
                    "attribute_id": attribute.id,
                    "name": attribute.attribute_name,
                    "raw_value": attribute.raw_value,
                    "normalized_value": attribute.normalized_value,
                    "unit": attribute.unit,
                    "confidence": confidence,
                    "validation_status": validation_status,
                    "validation_explanation": explanation,
                    "evidence": evidence,
                })
            self._stage(run, "reference_validation", "warning" if invalid_reference else "completed", "Validated existing values against available official reference datasets without fabricating replacements.")

            conflicts = self._conflicts(product.id)
            self._stage(run, "conflict_detection", "warning" if conflicts else "completed", f"Loaded {len(conflicts)} existing source-scoped conflict record(s); no conflict was auto-resolved.")

            required = {comparison_value(item["name"]) for item in schema if item.get("required")}
            present = {comparison_value(item["name"]) for item in enriched if item.get("raw_value") or item.get("normalized_value")}
            # Core fields live on ProductRecord and remain source-backed through the existing
            # extraction/provenance path, rather than being duplicated as ProductAttribute rows.
            if product.manufacturer:
                present.add(comparison_value("manufacturer"))
            if product.name:
                present.add(comparison_value("product_name"))
            if product.sku:
                present.add(comparison_value("sku_or_product_id"))
            missing = sorted(item for item in required if item not in present)
            confidence = overall_confidence(enriched)
            state = product_status(missing_required=missing, conflicts=conflicts, validation_invalid=invalid_reference, confidence=confidence)

            sources = self._sources(product)
            run.source_count = len({(item.get("source_type"), item.get("source_identifier"), item.get("source_url")) for item in sources})
            run.evidence_count = sum(len(item["evidence"]) for item in enriched)
            run.attribute_count = len(enriched)
            run.conflict_count = len(conflicts)
            run.overall_confidence = confidence
            run.product_status = state
            run.missing_attributes = missing
            run.status = "completed"
            run.stage = "completed"
            run.completed_at = self._now()
            self._stage(run, "output_generation", "completed", "Generated a canonical output that preserves raw values, evidence, confidence, conflicts, and review status.")
            run.output_snapshot = build_output(product, run, enriched, conflicts, sources)
            run.stage = "completed"
            self.db.commit()
            self.db.refresh(run)
            return run
        except Exception as exc:
            run.status = "failed"
            run.stage = "failed"
            run.completed_at = self._now()
            self._stage(run, "failed", "failed", f"Enrichment failed without altering source data: {exc}")
            self.db.commit()
            raise

    def batch(self, product_ids: list[int], retry_failed: bool = False, mode: str = "SOURCE_ONLY") -> EnrichmentBatch:
        unique_ids = list(dict.fromkeys(product_ids))
        batch = EnrichmentBatch(status="running", total_products=len(unique_ids), requested_product_ids=unique_ids, started_at=self._now())
        self.db.add(batch)
        self.db.flush()
        for product_id in unique_ids:
            try:
                run = self.analyze(product_id, batch=batch, mode=mode)
                batch.successful_count += 1
                if run.product_status != "READY":
                    batch.review_count += 1
            except Exception:
                batch.failed_count += 1
            batch.processed_count += 1
            self.db.flush()
        batch.status = "completed" if batch.failed_count == 0 else "completed_with_errors"
        batch.completed_at = self._now()
        self.db.commit()
        self.db.refresh(batch)
        return batch

    def latest(self, product_id: int) -> EnrichmentRun | None:
        return self.db.query(EnrichmentRun).filter_by(product_id=product_id).order_by(EnrichmentRun.id.desc()).first()

    def output(self, run: EnrichmentRun) -> dict[str, Any]:
        return run.output_snapshot or {}

    def review(self, run: EnrichmentRun, action: str, attribute_id: Optional[int], value: Optional[str], reason: Optional[str]) -> EnrichmentReviewDecision:
        attribute = None
        if attribute_id is not None:
            attribute = self.db.query(ProductAttribute).filter_by(id=attribute_id, product_id=run.product_id).first()
            if not attribute:
                raise LookupError("The selected attribute does not belong to this enriched product.")
        if action == "EDIT" and not value:
            raise ValueError("A reviewer value is required for EDIT; source values are not overwritten.")
        decision = EnrichmentReviewDecision(
            enrichment_run_id=run.id,
            product_id=run.product_id,
            attribute_id=attribute_id,
            decision=action,
            reviewer_value=value,
            reason=reason,
            evidence_snapshot=evidence_payload(attribute) if attribute else None,
        )
        self.db.add(decision)
        self.db.commit()
        self.db.refresh(decision)
        return decision

    def reviews(self, run_id: int) -> list[dict[str, Any]]:
        rows = self.db.query(EnrichmentReviewDecision).filter_by(enrichment_run_id=run_id).order_by(EnrichmentReviewDecision.id.desc()).all()
        return [{"id": row.id, "attribute_id": row.attribute_id, "decision": row.decision, "value": row.reviewer_value, "reason": row.reason, "evidence": row.evidence_snapshot, "created_at": row.created_at} for row in rows]

    def evidence(self, run: EnrichmentRun) -> list[dict[str, Any]]:
        output = self.output(run)
        return output.get("sources", [])

    def conflicts(self, run: EnrichmentRun) -> list[dict[str, Any]]:
        return self.output(run).get("conflicts", [])

    def attributes(self, run: EnrichmentRun) -> list[dict[str, Any]]:
        return list(self.output(run).get("attributes", {}).values())
