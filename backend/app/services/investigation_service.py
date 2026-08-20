"""Product investigation orchestration and explainable multi-source matching."""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
from itertools import combinations
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from sqlalchemy.orm import Session

from app.models.conflict import EvidenceChunk
from app.models.ingestion import IngestionJob, RawDocumentSource
from app.models.investigation import InvestigationSourceJob, ProductInvestigation
from app.models.product import ProductAttribute, ProductRecord
from app.schemas.investigation_schema import (
    AttributeComparisonResponse,
    AvailableIngestionJobResponse,
    IdentityFieldResponse,
    InvestigationComparisonResponse,
    InvestigationDocumentSourceResponse,
    InvestigationResponse,
    InvestigationSourceJobResponse,
    ProductMatchResponse,
    SourceAttributeValueResponse,
    SourceIdentityResponse,
)


NOT_FOUND = "Not found in provided sources"
IDENTITY_FIELDS = (
    "product_name",
    "brand",
    "sku",
    "product_id",
    "model_number",
    "part_number",
    "catalog_number",
    "type_series",
    "category",
)
IDENTIFIER_FIELDS = {"sku", "product_id", "model_number", "part_number", "catalog_number"}
ATTRIBUTE_ALIASES = {
    "product_name": {"product_name", "product", "name", "product_title"},
    "brand": {"brand", "manufacturer", "make", "vendor"},
    "sku": {"sku", "product_sku"},
    "product_id": {"product_id", "product_identifier", "product_number"},
    "model_number": {"model", "model_number", "model_no"},
    "part_number": {"part", "part_number", "part_no"},
    "catalog_number": {"catalog_number", "catalogue_number", "catalog_no"},
    "type_series": {"type_series", "series", "product_series", "type"},
    "category": {"category", "product_category"},
}
IDENTITY_LABEL_PATTERNS = {
    "product_name": re.compile(r"\b(?:product\s*name|product\s*title|name)\b\s*[:#-]\s*(?P<value>[^\n;|]{1,255})", re.I),
    "brand": re.compile(r"\b(?:brand|manufacturer|make)\b\s*[:#-]\s*(?P<value>[^\n;|]{1,255})", re.I),
    "sku": re.compile(r"\bsku\b\s*[:#-]\s*(?P<value>[A-Za-z0-9][A-Za-z0-9._/\-]{1,99})", re.I),
    "product_id": re.compile(r"\bproduct\s*(?:id|identifier|number|no\.?)\b\s*[:#-]\s*(?P<value>[A-Za-z0-9][A-Za-z0-9._/\-]{1,99})", re.I),
    "model_number": re.compile(r"\bmodel\s*(?:number|no\.?)\b\s*[:#-]\s*(?P<value>[A-Za-z0-9][A-Za-z0-9._/\-]{1,99})", re.I),
    "part_number": re.compile(r"\bpart\s*(?:number|no\.?)\b\s*[:#-]\s*(?P<value>[A-Za-z0-9][A-Za-z0-9._/\-]{1,99})", re.I),
    "catalog_number": re.compile(r"\bcatalog(?:ue)?\s*(?:number|no\.?)\b\s*[:#-]\s*(?P<value>[A-Za-z0-9][A-Za-z0-9._/\-]{1,99})", re.I),
    "type_series": re.compile(r"\b(?:type\s*series|series|type)\b\s*[:#-]\s*(?P<value>[^\n;|]{1,255})", re.I),
    "category": re.compile(r"\b(?:category|product\s*category)\b\s*[:#-]\s*(?P<value>[^\n;|]{1,255})", re.I),
}


class InvestigationError(Exception):
    """Expected investigation domain error suitable for a client response."""


@dataclass
class _SourceProfile:
    job_id: int
    source_type: str
    identities: List[IdentityFieldResponse]
    attributes: List[SourceAttributeValueResponse]
    product_ids: List[int]

    def value(self, field: str) -> Optional[str]:
        item = next((item for item in self.identities if item.field == field), None)
        if not item or item.value == NOT_FOUND:
            return None
        return item.value


def _normal_key(value: Optional[str]) -> str:
    """Normalize a comparison key without mutating persisted source values."""
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()


def _value_equal(left: Optional[str], right: Optional[str]) -> bool:
    return bool(_normal_key(left) and _normal_key(left) == _normal_key(right))


def _name_similarity(left: Optional[str], right: Optional[str]) -> float:
    """Use token overlap plus character similarity for transparent product-name comparison."""
    left_key, right_key = _normal_key(left), _normal_key(right)
    if not left_key or not right_key:
        return 0.0
    left_tokens, right_tokens = set(left_key.split()), set(right_key.split())
    jaccard = len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
    sequence = SequenceMatcher(None, left_key, right_key).ratio()
    return max(jaccard, sequence)


class ProductInvestigationService:
    """Keeps investigation data strictly limited to its explicitly attached ingestion jobs."""

    @staticmethod
    def create(db: Session, name: str, description: Optional[str]) -> ProductInvestigation:
        investigation = ProductInvestigation(
            name=name.strip(),
            description=description.strip() if description and description.strip() else None,
            status="draft",
        )
        db.add(investigation)
        db.commit()
        db.refresh(investigation)
        return investigation

    @staticmethod
    def get_or_raise(db: Session, investigation_id: int) -> ProductInvestigation:
        investigation = (
            db.query(ProductInvestigation)
            .filter(ProductInvestigation.id == investigation_id)
            .first()
        )
        if not investigation:
            raise InvestigationError("Product investigation not found")
        return investigation

    @classmethod
    def _job_summary(cls, db: Session, attachment: InvestigationSourceJob) -> InvestigationSourceJobResponse:
        job = attachment.job
        sources = db.query(RawDocumentSource).filter(RawDocumentSource.job_id == attachment.job_id).all()
        chunk_count = db.query(EvidenceChunk).filter(EvidenceChunk.job_id == attachment.job_id).count()
        return InvestigationSourceJobResponse(
            id=attachment.id,
            job_id=attachment.job_id,
            job_name=job.job_name,
            status=job.status,
            source_type=job.source_type,
            source_count=len(sources),
            evidence_chunk_count=chunk_count,
            sources=[
                InvestigationDocumentSourceResponse(
                    id=source.id,
                    filename=source.file_name,
                    source_url=source.source_url,
                )
                for source in sources
            ],
            attached_at=attachment.created_at,
        )

    @classmethod
    def serialize(cls, db: Session, investigation: ProductInvestigation) -> InvestigationResponse:
        # The relationship is the sole source of attached job IDs. No global evidence query is used.
        attachments = (
            db.query(InvestigationSourceJob)
            .filter(InvestigationSourceJob.investigation_id == investigation.id)
            .order_by(InvestigationSourceJob.created_at)
            .all()
        )
        return InvestigationResponse(
            id=investigation.id,
            name=investigation.name,
            description=investigation.description,
            status=investigation.status,
            created_at=investigation.created_at,
            updated_at=investigation.updated_at,
            source_jobs=[cls._job_summary(db, attachment) for attachment in attachments],
        )

    @classmethod
    def list_investigations(cls, db: Session) -> List[InvestigationResponse]:
        investigations = db.query(ProductInvestigation).order_by(ProductInvestigation.created_at.desc()).all()
        return [cls.serialize(db, investigation) for investigation in investigations]

    @classmethod
    def list_available_jobs(cls, db: Session) -> List[AvailableIngestionJobResponse]:
        jobs = (
            db.query(IngestionJob)
            .filter(IngestionJob.status == "completed")
            .order_by(IngestionJob.created_at.desc())
            .all()
        )
        return [
            AvailableIngestionJobResponse(
                id=job.id,
                job_name=job.job_name,
                status=job.status,
                source_type=job.source_type,
                created_at=job.created_at,
                source_count=db.query(RawDocumentSource).filter(RawDocumentSource.job_id == job.id).count(),
                evidence_chunk_count=db.query(EvidenceChunk).filter(EvidenceChunk.job_id == job.id).count(),
            )
            for job in jobs
        ]

    @classmethod
    def attach_job(
        cls, db: Session, investigation_id: int, job_id: int
    ) -> ProductInvestigation:
        investigation = cls.get_or_raise(db, investigation_id)
        job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
        if not job:
            raise InvestigationError("Ingestion job not found")
        if job.status != "completed":
            raise InvestigationError("Only completed ingestion jobs can be attached")
        if not db.query(RawDocumentSource).filter(RawDocumentSource.job_id == job_id).first():
            raise InvestigationError("The ingestion job has no valid document sources")
        if db.query(InvestigationSourceJob).filter(
            InvestigationSourceJob.investigation_id == investigation_id,
            InvestigationSourceJob.job_id == job_id,
        ).first():
            raise InvestigationError("This ingestion job is already attached to the investigation")

        db.add(InvestigationSourceJob(investigation_id=investigation_id, job_id=job_id))
        investigation.status = "active"
        db.commit()
        db.refresh(investigation)
        return investigation

    @classmethod
    def delete(cls, db: Session, investigation_id: int) -> None:
        investigation = cls.get_or_raise(db, investigation_id)
        # Cascade deletes relationship rows only; jobs, sources, evidence, products, and attributes remain intact.
        db.delete(investigation)
        db.commit()

    @staticmethod
    def _field_from_attribute(attribute_name: str) -> Optional[str]:
        normalized = _normal_key(attribute_name).replace(" ", "_")
        for field, aliases in ATTRIBUTE_ALIASES.items():
            if normalized in aliases:
                return field
        return None

    @staticmethod
    def _identity_from_chunk(field: str, chunk: EvidenceChunk) -> Optional[IdentityFieldResponse]:
        pattern = IDENTITY_LABEL_PATTERNS[field]
        match = pattern.search(chunk.snippet_text or "")
        if not match:
            return None
        value = match.group("value").strip().strip(".,;:")
        if not value:
            return None
        return IdentityFieldResponse(
            field=field,
            value=value,
            source_type=chunk.source_type,
            source_identifier=chunk.source_identifier,
            source_url=chunk.source_url,
            page_number=chunk.page_number,
            row_number=chunk.row_number,
            evidence_chunk_id=chunk.stable_chunk_id,
        )

    @classmethod
    def _profile_for_job(cls, db: Session, job: IngestionJob) -> _SourceProfile:
        """Build a profile using only chunks, attributes, and SKU citations belonging to one job."""
        chunks = (
            db.query(EvidenceChunk)
            .filter(EvidenceChunk.job_id == job.id)
            .order_by(EvidenceChunk.id)
            .all()
        )
        identity_by_field: Dict[str, IdentityFieldResponse] = {}

        # Explicit source labels have priority and keep their exact per-source provenance.
        for chunk in chunks:
            for field in IDENTITY_FIELDS:
                if field not in identity_by_field:
                    candidate = cls._identity_from_chunk(field, chunk)
                    if candidate:
                        identity_by_field[field] = candidate

        # ProductAttribute stores the stable evidence citation assigned during extraction. Querying
        # only those citations includes every attribute from this job even when one evidence chunk
        # supports more than one attribute, while excluding same-named sources from other jobs.
        scoped_chunk_ids = {chunk.stable_chunk_id for chunk in chunks if chunk.stable_chunk_id}
        attribute_rows: List[ProductAttribute] = (
            db.query(ProductAttribute)
            .filter(ProductAttribute.evidence_chunk_id.in_(scoped_chunk_ids))
            .order_by(ProductAttribute.id)
            .all()
            if scoped_chunk_ids
            else []
        )
        chunk_by_id = {chunk.stable_chunk_id: chunk for chunk in chunks if chunk.stable_chunk_id}
        product_ids = sorted({attribute.product_id for attribute in attribute_rows if attribute.product_id})
        attribute_values: List[SourceAttributeValueResponse] = []

        for attribute in attribute_rows:
            value = attribute.normalized_value or attribute.raw_value
            if value is None or not str(value).strip():
                continue
            chunk = chunk_by_id.get(attribute.evidence_chunk_id)
            attribute_values.append(
                SourceAttributeValueResponse(
                    job_id=job.id,
                    source_type=attribute.source_type or (chunk.source_type if chunk else job.source_type),
                    attribute_name=attribute.attribute_name,
                    value=str(value),
                    unit=attribute.unit,
                    confidence_score=attribute.confidence_score,
                    source_identifier=attribute.source_identifier or (chunk.source_identifier if chunk else None),
                    source_url=attribute.source_url or (chunk.source_url if chunk else None),
                    page_number=attribute.page_number if attribute.page_number is not None else (chunk.page_number if chunk else None),
                    row_number=attribute.row_number if attribute.row_number is not None else (chunk.row_number if chunk else None),
                    evidence_chunk_id=attribute.evidence_chunk_id,
                    evidence_snippet=chunk.snippet_text if chunk else None,
                )
            )
            field = cls._field_from_attribute(attribute.attribute_name)
            if field and field not in identity_by_field:
                identity_by_field[field] = IdentityFieldResponse(
                    field=field,
                    value=str(value),
                    source_type=attribute.source_type or (chunk.source_type if chunk else job.source_type),
                    source_identifier=attribute.source_identifier or (chunk.source_identifier if chunk else None),
                    source_url=attribute.source_url or (chunk.source_url if chunk else None),
                    page_number=attribute.page_number if attribute.page_number is not None else (chunk.page_number if chunk else None),
                    row_number=attribute.row_number if attribute.row_number is not None else (chunk.row_number if chunk else None),
                    evidence_chunk_id=attribute.evidence_chunk_id,
                )

        # A SKU is eligible only when its own stored evidence chunk belongs to this attached job.
        sku_products = (
            db.query(ProductRecord)
            .filter(ProductRecord.sku_evidence_chunk_id.in_(scoped_chunk_ids))
            .all()
            if scoped_chunk_ids
            else []
        )
        product_ids = sorted(set(product_ids) | {product.id for product in sku_products})

        # Reuse extraction outputs only after a source-scoped attribute or SKU citation has established membership.
        if product_ids and chunks:
            products = db.query(ProductRecord).filter(ProductRecord.id.in_(product_ids)).all()
            fallback_chunk = chunks[0]
            for product in products:
                fallback_values = {
                    "product_name": product.name,
                    "brand": product.manufacturer,
                    "category": product.category,
                }
                if product.sku and product.sku_evidence_chunk_id in scoped_chunk_ids:
                    fallback_values["sku"] = product.sku
                for field, value in fallback_values.items():
                    if value and field not in identity_by_field:
                        identity_by_field[field] = IdentityFieldResponse(
                            field=field,
                            value=str(value),
                            source_type=fallback_chunk.source_type or job.source_type,
                            source_identifier=fallback_chunk.source_identifier,
                            source_url=fallback_chunk.source_url,
                            page_number=fallback_chunk.page_number,
                            row_number=fallback_chunk.row_number,
                            evidence_chunk_id=fallback_chunk.stable_chunk_id,
                        )

        identities = [
            identity_by_field.get(field, IdentityFieldResponse(field=field, value=NOT_FOUND))
            for field in IDENTITY_FIELDS
        ]
        return _SourceProfile(
            job_id=job.id,
            source_type=job.source_type,
            identities=identities,
            attributes=attribute_values,
            product_ids=product_ids,
        )

    @staticmethod
    def _technical_values(profile: _SourceProfile) -> Dict[str, List[str]]:
        values: Dict[str, List[str]] = defaultdict(list)
        for attribute in profile.attributes:
            key = _normal_key(attribute.attribute_name)
            if key and key not in {"product name", "brand", "manufacturer", "category", "sku"}:
                values[key].append(attribute.value)
        return values

    @classmethod
    def _match_pair(cls, left: _SourceProfile, right: _SourceProfile) -> ProductMatchResponse:
        score = 0
        reasons: List[str] = []
        strong_signal_count = 0
        identifier_mismatch = False

        identifier_labels = {
            "sku": "SKU",
            "product_id": "Product ID",
            "model_number": "Model number",
            "part_number": "Part number",
            "catalog_number": "Catalog number",
        }
        for field in sorted(IDENTIFIER_FIELDS):
            left_value, right_value = left.value(field), right.value(field)
            label = identifier_labels[field]
            if left_value and right_value:
                if _value_equal(left_value, right_value):
                    score += 55
                    strong_signal_count += 1
                    reasons.append(f"{label} matches: {left_value}")
                    break
                identifier_mismatch = True
                reasons.append(
                    f"Explicit {label} values differ: {left_value} vs {right_value}"
                )

        left_brand, right_brand = left.value("brand"), right.value("brand")
        if left_brand and right_brand:
            if _value_equal(left_brand, right_brand):
                score += 15
                strong_signal_count += 1
                reasons.append(f"Brand matches: {left_brand}")
            else:
                score -= 15
                reasons.append(f"Brands differ: {left_brand} vs {right_brand}")

        similarity = _name_similarity(left.value("product_name"), right.value("product_name"))
        if similarity >= 0.82:
            score += 25
            strong_signal_count += 1
            reasons.append("Product names are highly similar")
        elif similarity >= 0.55:
            score += 12
            reasons.append("Product names are partially similar")

        left_category, right_category = left.value("category"), right.value("category")
        if left_category and right_category and _value_equal(left_category, right_category):
            score += 10
            strong_signal_count += 1
            reasons.append(f"Category matches: {left_category}")

        left_type, right_type = left.value("type_series"), right.value("type_series")
        if left_type and right_type and _value_equal(left_type, right_type):
            score += 10
            strong_signal_count += 1
            reasons.append(f"Type series matches: {left_type}")

        left_attributes, right_attributes = cls._technical_values(left), cls._technical_values(right)
        technical_matches = 0
        for attribute_name in sorted(set(left_attributes) & set(right_attributes)):
            if any(_value_equal(a, b) for a in left_attributes[attribute_name] for b in right_attributes[attribute_name]):
                technical_matches += 1
                if technical_matches <= 2:
                    display = attribute_name.replace("_", " ").title()
                    reasons.append(f"{display} specification matches")
        if technical_matches:
            score += min(30, technical_matches * 15)
            strong_signal_count += min(technical_matches, 2)

        if identifier_mismatch:
            score = min(score, 20)
        # A name by itself is deliberately never enough for a possible or high-confidence match.
        if strong_signal_count <= 1:
            score = min(score, 35)
        score = max(0, min(100, score))

        if identifier_mismatch:
            status = "LIKELY_DIFFERENT_PRODUCT"
        elif score >= 80 and strong_signal_count >= 3:
            status = "HIGH_CONFIDENCE_MATCH"
        elif score >= 55:
            status = "POSSIBLE_MATCH"
        else:
            # Similar naming alone remains weak evidence, not proof that sources describe different products.
            status = "LOW_CONFIDENCE_MATCH"

        if not reasons:
            reasons.append("No compatible source-backed identity or technical attribute signals were found")
        return ProductMatchResponse(
            source_job_ids=[left.job_id, right.job_id],
            match_score=score,
            match_status=status,
            reasons=reasons,
        )

    @classmethod
    def comparison(cls, db: Session, investigation_id: int) -> InvestigationComparisonResponse:
        investigation = cls.get_or_raise(db, investigation_id)
        attachments = (
            db.query(InvestigationSourceJob)
            .filter(InvestigationSourceJob.investigation_id == investigation.id)
            .order_by(InvestigationSourceJob.created_at)
            .all()
        )
        profiles = [cls._profile_for_job(db, attachment.job) for attachment in attachments]
        # Import lazily to keep the shared profile builder independent while enriching the
        # existing comparison response with the same source-scoped conflict assessment.
        from app.services.conflict_detection_service import ConflictDetectionService

        conflict_report = ConflictDetectionService.analyze_profiles(investigation.id, profiles)
        conflict_by_attribute = {
            _normal_key(summary.attribute_name): summary
            for summary in conflict_report.attribute_summaries
        }

        comparison_rows: Dict[str, List[SourceAttributeValueResponse]] = defaultdict(list)
        for profile in profiles:
            for attribute in profile.attributes:
                comparison_rows[attribute.attribute_name].append(attribute)
        attributes = []
        for name in sorted(comparison_rows, key=str.casefold):
            values = comparison_rows[name]
            distinct = {_normal_key(item.value) for item in values if _normal_key(item.value)}
            summary = conflict_by_attribute.get(_normal_key(name))
            attributes.append(
                AttributeComparisonResponse(
                    attribute_name=name,
                    values=values,
                    different_values_detected=(summary.status != "NO_CONFLICT") if summary else len(distinct) > 1,
                    conflict_status=summary.status if summary else "NO_CONFLICT",
                    conflict_severity=summary.severity if summary else None,
                    agreement_count=summary.agreement_count if summary else len({item.job_id for item in values}),
                    total_sources=summary.total_sources if summary else len(profiles),
                )
            )

        return InvestigationComparisonResponse(
            investigation_id=investigation.id,
            investigation_name=investigation.name,
            status=investigation.status,
            source_identities=[
                SourceIdentityResponse(
                    job_id=profile.job_id,
                    source_type=profile.source_type,
                    product_ids=profile.product_ids,
                    identity_fields=profile.identities,
                )
                for profile in profiles
            ],
            matches=[cls._match_pair(left, right) for left, right in combinations(profiles, 2)],
            attributes=attributes,
        )
