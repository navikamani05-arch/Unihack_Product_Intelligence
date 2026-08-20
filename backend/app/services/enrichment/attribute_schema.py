"""Attribute schema discovery for enrichment without a single-category hardcode."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.product import ProductRecord
from app.models.reference_data import LOVEntry, ReferenceDataset
from app.services.reference_data_service import comparison_value


CORE_ATTRIBUTES = [
    {"name": "manufacturer", "data_type": "string", "required": True, "unit": None, "description": "Source-backed manufacturer."},
    {"name": "product_name", "data_type": "string", "required": True, "unit": None, "description": "Source-backed product title/name."},
    {"name": "sku_or_product_id", "data_type": "string", "required": True, "unit": None, "description": "Explicit source-backed identifier."},
]


def discover_attribute_schema(db: Session, product: ProductRecord, category: dict[str, Any]) -> list[dict[str, Any]]:
    """Return a deduplicated schema from active official LOVs plus persisted attributes."""
    schema = list(CORE_ATTRIBUTES)
    seen = {comparison_value(row["name"]) for row in schema}
    path = comparison_value(category.get("category") or "")
    active = db.query(ReferenceDataset.id).filter(ReferenceDataset.is_active.is_(True), ReferenceDataset.status == "available").subquery()
    lovs = db.query(LOVEntry).filter(LOVEntry.dataset_id.in_(active)).all()
    for entry in lovs:
        if path and entry.classpath_comparison and path not in entry.classpath_comparison and entry.classpath_comparison not in path:
            continue
        key = comparison_value(entry.attribute_label)
        if not key or key in seen:
            continue
        schema.append({
            "name": entry.attribute_label,
            "data_type": "string",
            "required": False,
            "unit": None,
            "allowed_values": entry.normalized_values or entry.attribute_values,
            "category": entry.classpath,
            "description": entry.guidelines or "Active official LOV-backed attribute.",
            "origin": "official_reference_data",
        })
        seen.add(key)
    for attribute in product.attributes:
        key = comparison_value(attribute.attribute_name)
        if key and key not in seen:
            schema.append({
                "name": attribute.attribute_name,
                "data_type": "string",
                "required": False,
                "unit": attribute.unit,
                "description": "Observed in existing source-backed product extraction.",
                "origin": "source_evidence",
            })
            seen.add(key)
    return schema
