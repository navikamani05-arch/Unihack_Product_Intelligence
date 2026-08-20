"""Transparent confidence and status calculation for source-backed enrichment."""
from __future__ import annotations

from typing import Any


AUTHORITY_WEIGHT = {
    "manufacturer_document": 1.0,
    "manufacturer_website": 0.92,
    "manufacturer": 0.92,
    "authorized_distributor": 0.78,
    "distributor": 0.7,
    "catalog": 0.62,
    "csv": 0.55,
    "pdf": 0.75,
    "website": 0.65,
    "unknown": 0.45,
}


def authority_for_source(source_type: str | None, source_url: str | None = None) -> tuple[str, float]:
    source = (source_type or "unknown").casefold()
    if "manufacturer" in source:
        return "manufacturer", AUTHORITY_WEIGHT["manufacturer"]
    if "distributor" in source:
        return "authorized_distributor", AUTHORITY_WEIGHT["authorized_distributor"]
    if source in AUTHORITY_WEIGHT:
        return source, AUTHORITY_WEIGHT[source]
    if source_url:
        return "website", AUTHORITY_WEIGHT["website"]
    return "unknown", AUTHORITY_WEIGHT["unknown"]


def attribute_confidence(attribute: Any, evidence_count: int, has_validation_issue: bool = False) -> float | None:
    """Calculates confidence from the existing extraction score and observable evidence quality."""
    if attribute.raw_value is None and attribute.normalized_value is None:
        return None
    _, authority = authority_for_source(attribute.source_type, attribute.source_url)
    extraction = attribute.confidence_score if attribute.confidence_score is not None else 0.5
    evidence_quality = 1.0 if evidence_count else 0.55
    normalization = 0.9 if attribute.normalized_value and attribute.normalized_value != attribute.raw_value else 1.0
    penalty = 0.65 if has_validation_issue else 1.0
    return round(max(0.0, min(1.0, authority * extraction * evidence_quality * normalization * penalty)), 4)


def overall_confidence(attributes: list[dict[str, Any]]) -> float | None:
    values = [item["confidence"] for item in attributes if item.get("confidence") is not None]
    return round(sum(values) / len(values), 4) if values else None


def product_status(*, missing_required: list[str], conflicts: list[dict[str, Any]], validation_invalid: bool, confidence: float | None) -> str:
    critical = any((item.get("severity") or "").upper() == "CRITICAL" and (item.get("resolution_status") or "unresolved").casefold() in {"unresolved", "human_review"} for item in conflicts)
    if critical:
        return "CONFLICTING_DATA"
    if validation_invalid:
        return "INVALID_REFERENCE_DATA"
    if missing_required:
        return "INSUFFICIENT_DATA"
    if confidence is not None and confidence >= 0.8 and not conflicts:
        return "READY"
    return "NEEDS_REVIEW"
