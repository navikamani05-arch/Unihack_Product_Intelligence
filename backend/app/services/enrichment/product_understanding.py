"""Source-aware product understanding for Phase 6 enrichment."""
from __future__ import annotations

import re
from typing import Any

from app.models.product import ProductRecord
from app.services.reference_data_service import is_placeholder


GENERIC_TERMS = {"product", "item", "part", "unit", "equipment", "component"}


def _words(value: str | None) -> list[str]:
    return [word for word in re.findall(r"[A-Za-z0-9][A-Za-z0-9/-]*", value or "") if word]


def build_product_understanding(product: ProductRecord) -> dict[str, Any]:
    """Build a transparent understanding object without claiming verification."""
    description = (product.description or "").strip()
    name = (product.name or "").strip()
    manufacturer = None if is_placeholder(product.manufacturer) else product.manufacturer
    tokens = _words(description or name)
    product_type = " ".join(tokens[:6]).strip() or None
    ambiguity: list[str] = []
    if not product.sku:
        ambiguity.append("No explicit SKU / product ID is available in the source-backed record.")
    if not manufacturer:
        ambiguity.append("No non-placeholder manufacturer is available.")
    if not description:
        ambiguity.append("No source-backed description is available.")

    supplied = {
        "name": bool(name), "description": bool(description), "manufacturer": bool(manufacturer), "identifier": bool(product.sku),
    }
    search_terms: list[str] = []
    if manufacturer and product.sku:
        search_terms.append(f"{manufacturer} {product.sku}")
    if product.sku and product_type:
        search_terms.append(f"{product.sku} {product_type}")
    if manufacturer and description:
        search_terms.append(f"{manufacturer} {description}")
    if product.sku:
        search_terms.append(product.sku)

    return {
        "probable_product_name": {"value": name or product_type, "origin": "directly_supplied" if name else "inferred"},
        "probable_manufacturer": {"value": manufacturer, "origin": "directly_supplied" if manufacturer else "missing"},
        "probable_brand": {"value": None, "origin": "missing"},
        "product_type": {"value": product_type, "origin": "inferred" if product_type else "missing"},
        "identifiers": [{"value": product.sku, "type": "sku_or_product_id", "origin": "directly_supplied"}] if product.sku else [],
        "search_terms": list(dict.fromkeys(search_terms)),
        "alternate_search_terms": list(dict.fromkeys([term for term in search_terms if product.sku not in term]))[:3],
        "ambiguity_flags": ambiguity,
        "supplied_fields": supplied,
    }
