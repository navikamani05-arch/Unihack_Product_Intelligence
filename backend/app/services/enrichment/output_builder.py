"""Builds a provenance-inclusive, commerce-ready enrichment output."""
from __future__ import annotations

from typing import Any

from app.models.product import ProductRecord
from app.services.enrichment.confidence_engine import authority_for_source
from app.services.text_normalization import normalize_product_name


def evidence_payload(attribute: Any) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for chunk in attribute.evidence_chunks:
        authority, _ = authority_for_source(chunk.source_type, chunk.source_url)
        output.append({
            "evidence_chunk_id": chunk.stable_chunk_id,
            "source_type": chunk.source_type,
            "source_identifier": chunk.source_identifier,
            "source_url": chunk.source_url,
            "page_number": chunk.page_number,
            "row_number": chunk.row_number,
            "quote": chunk.snippet_text,
            "authority": authority,
        })
    if not output and (attribute.source_identifier or attribute.source_url):
        authority, _ = authority_for_source(attribute.source_type, attribute.source_url)
        output.append({
            "evidence_chunk_id": attribute.evidence_chunk_id,
            "source_type": attribute.source_type,
            "source_identifier": attribute.source_identifier,
            "source_url": attribute.source_url,
            "page_number": attribute.page_number,
            "row_number": attribute.row_number,
            "quote": None,
            "authority": authority,
        })
    return output


def build_output(product: ProductRecord, run: Any, enriched_attributes: list[dict[str, Any]], conflicts: list[dict[str, Any]], sources: list[dict[str, Any]]) -> dict[str, Any]:
    """Produces a result that never labels inferred values as externally verified."""
    attributes = {
        item["name"]: {
            "attribute_id": item.get("attribute_id"),
            "name": item["name"],
            "raw_value": item.get("raw_value"),
            "normalized_value": item.get("normalized_value"),
            "unit": item.get("unit"),
            "confidence": item.get("confidence"),
            "evidence": item.get("evidence", []),
            "validation_status": item.get("validation_status"),
            "validation_explanation": item.get("validation_explanation"),
        }
        for item in enriched_attributes
    }
    return {
        "product_id": product.id,
        "product": {"id": product.id, "sku": product.sku, "name": product.name, "manufacturer": product.manufacturer, "category": product.category},
        "manufacturer": product.manufacturer,
        "brand": next(
            (
                item.get("normalized_value") or item.get("raw_value")
                for item in enriched_attributes
                if str(item.get("name", "")).strip().casefold().replace("_", " ") in {"brand", "brand name", "e1 brand", "unilog brand", "dib brand"}
                and (item.get("normalized_value") or item.get("raw_value"))
            ),
            None,
        ),
        "part_number": product.sku,
        "product_name": normalize_product_name(product.name, product.sku) or product.name,
        "category": run.category,
        "category_path": run.category_path or [],
        "category_confidence": run.category_confidence,
        "category_is_official": bool((run.product_understanding or {}).get("category_is_official")),
        "attributes": attributes,
        "sources": sources,
        "conflicts": conflicts,
        "missing_attributes": run.missing_attributes or [],
        "overall_confidence": run.overall_confidence,
        "status": run.product_status,
        "confidence_note": "Extraction confidence is evidence-based and is not ground-truth accuracy.",
    }
