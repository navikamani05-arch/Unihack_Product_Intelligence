"""Configurable, explicitly provisional category classification."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.reference_data import LOVEntry, ReferenceDataset
from app.models.product import ProductRecord
from app.services.reference_data_service import comparison_value


# These are transparent provisional cues, not official Unilog categories.
PROVISIONAL_CATEGORY_CUES: dict[str, tuple[str, ...]] = {
    "Valves": ("valve", "ball valve", "gate valve", "check valve"),
    "Motors": ("motor", "rpm", "horsepower", "kw", "kilowatt"),
    "Pumps": ("pump", "impeller", "gpm", "flow rate"),
    "Fasteners": ("bolt", "screw", "nut", "washer", "fastener"),
    "Fittings": ("fitting", "elbow", "coupling", "adapter", "tee"),
    "Electrical Components": ("voltage", "circuit", "relay", "switch", "electrical"),
}


def classify_category(db: Session, product: ProductRecord, understanding: dict[str, Any]) -> dict[str, Any]:
    text = comparison_value(" ".join(filter(None, [product.name, product.description, product.category])))
    official_categories = (
        db.query(LOVEntry)
        .join(ReferenceDataset)
        .filter(ReferenceDataset.is_active.is_(True), ReferenceDataset.status == "available", LOVEntry.classpath.isnot(None))
        .all()
    )
    for entry in official_categories:
        if entry.classpath_comparison and entry.classpath_comparison in text:
            return {
                "category": entry.classpath,
                "category_path": [part.strip() for part in entry.classpath.split(">") if part.strip()],
                "confidence": 0.9,
                "reason": "Matched an active official reference-data category path in source-backed product text.",
                "evidence": [],
                "is_official": True,
            }
    matches = [(category, cue) for category, cues in PROVISIONAL_CATEGORY_CUES.items() for cue in cues if cue in text]
    if matches:
        category, cue = matches[0]
        return {
            "category": category,
            "category_path": [category],
            "confidence": 0.62 if len(matches) == 1 else 0.48,
            "reason": f"Provisional keyword classification based on source-backed term '{cue}'.",
            "evidence": [],
            "is_official": False,
        }
    return {
        "category": product.category,
        "category_path": [product.category] if product.category else [],
        "confidence": 0.35 if product.category else 0.0,
        "reason": "No official category reference or confident source-backed category cue is available.",
        "evidence": [],
        "is_official": False,
    }
