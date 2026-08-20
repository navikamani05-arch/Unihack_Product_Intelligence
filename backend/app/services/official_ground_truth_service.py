from __future__ import annotations

from collections import defaultdict
from typing import Any, Optional

import pandas as pd

from app.services.llm_extraction_service import LLMExtractionService
from app.services.text_normalization import normalize_product_name


# These mappings are based only on exact observed headers in the supplied official file
# and on field names already supported by the application's ProductRecord/Commerce Output.
DIRECT_MAPPINGS = {
    # Keys are normalized with normalize_name(), so underscores and hyphens become spaces.
    "mfg part num": ("sku", "product identifier", "SUPPORTED", "exact identifier comparison"),
    "manufacturer part number": ("sku", "product identifier", "SUPPORTED", "alternate identifier header; compared to generated SKU"),
    "product name": ("name", "product information", "SUPPORTED", "direct ProductRecord name comparison"),
    "product title": ("name", "product information", "SUPPORTED", "direct ProductRecord name comparison"),
    "manufacturer name": ("manufacturer", "product information", "SUPPORTED", "direct ProductRecord manufacturer comparison"),
    "part desc": ("description", "description", "SUPPORTED", "direct ProductRecord description comparison"),
}
ROLE_HEADERS = {
    "mfr url": ("reference/provenance URL", "UNSUPPORTED", "source/reference URL is not a generated Commerce Output value"),
    "ref url 1": ("reference/provenance URL", "UNSUPPORTED", "source/reference URL is not a generated Commerce Output value"),
    "ref url 2": ("reference/provenance URL", "UNSUPPORTED", "source/reference URL is not a generated Commerce Output value"),
    "ref url 3": ("reference/provenance URL", "UNSUPPORTED", "source/reference URL is not a generated Commerce Output value"),
    "ref url 4": ("reference/provenance URL", "UNSUPPORTED", "source/reference URL is not a generated Commerce Output value"),
    "ref url 5": ("reference/provenance URL", "UNSUPPORTED", "source/reference URL is not a generated Commerce Output value"),
    "part_number": ("alternate product identifier", "UNSUPPORTED", "no separate generated field for this identifier exists"),
    "sku my part number": ("alternate product identifier", "UNSUPPORTED", "no separate generated field for this identifier exists"),
    "dept": ("classification", "UNSUPPORTED", "department hierarchy is not a canonical generated field"),
    "class": ("classification", "UNSUPPORTED", "class hierarchy is not a canonical generated field"),
    "fine": ("classification", "UNSUPPORTED", "fine hierarchy is not a canonical generated field"),
    "classpath": ("classification", "UNSUPPORTED", "classpath hierarchy is not a canonical generated field"),
    "e1 brand": ("brand/reference alias", "UNSUPPORTED", "source/reference alias is not the canonical generated brand"),
    "unilog brand": ("brand/reference alias", "UNSUPPORTED", "source/reference alias is not the canonical generated brand"),
    "dib brand": ("brand/reference alias", "UNSUPPORTED", "source/reference alias is not the canonical generated brand"),
    "part manuf": ("source manufacturer", "UNSUPPORTED", "source manufacturer is distinct from canonical manufacturer output"),
    "trade name": ("product information", "UNKNOWN", "header is descriptive but no direct Commerce Output field is defined"),
    "alternate part number": ("alternate product identifier", "UNSUPPORTED", "no separate generated field for this identifier exists"),
    "upc": ("product identifier", "UNSUPPORTED", "Commerce Output has no supported UPC field"),
    "ean": ("product identifier", "UNSUPPORTED", "Commerce Output has no supported EAN field"),
    "gtin": ("product identifier", "UNSUPPORTED", "Commerce Output has no supported GTIN field"),
    "unspsc": ("classification", "UNSUPPORTED", "Commerce Output has no supported UNSPSC field"),
}

DESCRIPTION_HEADERS = {"mobile desc", "invoice desc", "short desc", "long desc1", "retail desc", "marketing description"}
FEATURE_PREFIXES = ("item features ",)
ATTRIBUTE_LABEL_PREFIX = "attribute label "
ATTRIBUTE_VALUE_PREFIX = "attribute value "
ATTRIBUTE_UOM_PREFIX = "attribute uom "


def normalize_name(value: str) -> str:
    return " ".join(str(value).lower().replace("_", " ").replace("-", " ").split())


def clean(value: Any) -> Optional[str]:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text if text else None


def load_frame(path) -> pd.DataFrame:
    return pd.read_csv(path, dtype="string", keep_default_na=False) if str(path).lower().endswith(".csv") else pd.read_excel(path, dtype="string", keep_default_na=False)


def identify_column(columns: list[str]) -> Optional[str]:
    """Select the canonical generated-SKU comparison column without guessing from arbitrary order."""
    normalized = {normalize_name(column): column for column in columns}
    for preferred in ("mfg part num", "manufacturer part number", "sku", "product id", "product identifier"):
        if preferred in normalized:
            return normalized[preferred]
    for column in columns:
        if normalize_name(column) in {"part number", "my part number"}:
            return column
    return None


def _profile_status(name: str) -> tuple[str, str, Optional[str], Optional[str]]:
    normalized = normalize_name(name)
    if normalized in DIRECT_MAPPINGS:
        mapped, role, status, reason = DIRECT_MAPPINGS[normalized]
        return role, status, mapped, "exact"
    if normalized in ROLE_HEADERS:
        role, status, reason = ROLE_HEADERS[normalized]
        return role, status, None, reason
    if normalized == "brand name":
        return "brand", "SUPPORTED", "brand", "direct generated brand attribute comparison"
    if normalized in DESCRIPTION_HEADERS:
        return "description variant", "UNSUPPORTED", None, "delivery-format description variant has no distinct generated field"
    if normalized.startswith(FEATURE_PREFIXES):
        return "feature", "UNSUPPORTED", None, "feature slot has no fixed generated Commerce Output field"
    if normalized in {"with", "standard/approvals", "prop 65", "application", "includes", "warranty", "warranty information"}:
        return "product information", "UNKNOWN", None, "header meaning is observable, but no direct generated Commerce Output mapping is established"
    if normalized == "product name":
        return "product information", "SUPPORTED", "name", "direct ProductRecord name comparison"
    if normalized.startswith(ATTRIBUTE_LABEL_PREFIX):
        return "attribute schema label", "UNKNOWN", None, "label column defines the paired dynamic attribute name"
    if normalized.startswith(ATTRIBUTE_VALUE_PREFIX):
        return "attribute value", "PARTIALLY_SUPPORTED", None, "compared dynamically using the paired ATTRIBUTE_LABEL column when present"
    if normalized.startswith(ATTRIBUTE_UOM_PREFIX):
        return "attribute UOM", "PARTIALLY_SUPPORTED", None, "compared only when the paired dynamic attribute exposes a unit"
    if normalized in {"product image", "alternate image 1", "alternate image 2", "alternate image 3", "alternate image 4", "sds", "sds 1", "specification sheet", "instruction/installation manual", "service manual", "owners/user manual", "line drawing", "mtr", "rohs", "full engineering drawing", "energy star guide", "technical bulletin", "submittal", "compatibility chart", "size chart", "product label/insert", "video link", "video link 1"}:
        return "media/document delivery field", "UNSUPPORTED", None, "Commerce Output does not currently expose this media/document delivery field"
    if normalized in {"list price", "selling qty", "selling uom", "standard packaging information", "length", "length uom", "height", "height uom", "width", "width uom", "weight", "weight uom", "volume", "volume uom", "country of origin", "discontinued", "actual image (yes/no)"}:
        return "commerce/delivery field", "UNSUPPORTED", None, "Commerce Output does not currently expose this delivery-format field"
    return "unknown", "UNKNOWN", None, "column meaning or mapping cannot be established from the current application schema"


def profile_frame(frame: pd.DataFrame) -> list[dict[str, Any]]:
    profiles = []
    for column in frame.columns:
        values = [clean(value) for value in frame[column].tolist()]
        nonempty = [value for value in values if value is not None]
        role, status, mapped, reason = _profile_status(str(column))
        profiles.append({
            "name": str(column),
            "pandas_dtype": str(frame[column].dtype),
            "nonempty_count": len(nonempty),
            "empty_count": len(values) - len(nonempty),
            "unique_count": len(set(nonempty)),
            "sample_values": list(dict.fromkeys(nonempty))[:5],
            "max_string_length": max((len(value) for value in nonempty), default=0),
            "role": role,
            "comparison_status": status,
            "mapped_field": mapped,
            "comparison_mode": "exact/normalized/partial" if status == "SUPPORTED" else ("dynamic attribute" if status == "PARTIALLY_SUPPORTED" else None),
            "reason": reason,
        })
    return profiles


def _attributes(product) -> dict[str, list[Any]]:
    values: dict[str, list[Any]] = defaultdict(list)
    for attribute in product.attributes:
        values[normalize_name(attribute.attribute_name)].append(attribute)
    return values


def _source_data_available(product, attrs: dict[str, list[Any]], column: str, mapped: Optional[str], row: Optional[pd.Series] = None) -> bool:
    """Return whether a usable source-backed value exists for this expected field.

    This intentionally does not inspect the official expected value. It only uses the
    generated product and its persisted source-backed attributes, so a missing value is
    not mislabeled as a pipeline failure when the source never supplied that field.
    """
    if product is None:
        return False
    normalized = normalize_name(column)
    if mapped == "sku":
        return bool(clean(product.sku))
    if mapped == "name":
        return bool(clean(product.name) or clean(product.description))
    if mapped == "manufacturer":
        return bool(clean(product.manufacturer))
    if normalized == "brand name":
        return any(clean(attr.normalized_value or attr.raw_value) for key in ("brand", "brand name", "manufacturer brand", "e1 brand", "unilog brand", "dib brand") for attr in attrs.get(key, []))
    if normalized.startswith(ATTRIBUTE_VALUE_PREFIX) and row is not None:
        suffix = normalized[len(ATTRIBUTE_VALUE_PREFIX):]
        label = clean(row.get(f"ATTRIBUTE_LABEL {suffix}"))
        return bool(label and attrs.get(normalize_name(label)))
    if normalized.startswith(ATTRIBUTE_UOM_PREFIX) and row is not None:
        suffix = normalized[len(ATTRIBUTE_UOM_PREFIX):]
        label = clean(row.get(f"ATTRIBUTE_LABEL {suffix}"))
        return bool(label and attrs.get(normalize_name(label)))
    return bool(attrs.get(normalized))


def _direct_generated(product, attrs: dict[str, list[Any]], column: str, row: Optional[pd.Series] = None) -> tuple[Optional[str], str, Optional[str], str]:
    normalized = normalize_name(column)
    role, status, mapped, reason = _profile_status(column)
    if normalized in DIRECT_MAPPINGS:
        generated = {"sku": product.sku, "name": normalize_product_name(product.name, product.sku) or product.name, "manufacturer": product.manufacturer, "description": product.description}.get(mapped)
        return clean(generated), status, mapped, reason
    if normalized == "brand name":
        for key in ("brand", "brand name", "manufacturer brand", "e1 brand", "unilog brand", "dib brand"):
            for attr in attrs.get(key, []):
                value = clean(attr.normalized_value or attr.raw_value)
                if value:
                    return value, status, "brand", reason
        return None, status, "brand", reason
    if normalized.startswith(ATTRIBUTE_VALUE_PREFIX) and row is not None:
        suffix = normalized[len(ATTRIBUTE_VALUE_PREFIX):]
        label = clean(row.get(f"ATTRIBUTE_LABEL {suffix}"))
        if label:
            for attr in attrs.get(normalize_name(label), []):
                return clean(attr.normalized_value or attr.raw_value), status, label, reason
        return None, status, label, reason
    if normalized.startswith(ATTRIBUTE_UOM_PREFIX) and row is not None:
        suffix = normalized[len(ATTRIBUTE_UOM_PREFIX):]
        label = clean(row.get(f"ATTRIBUTE_LABEL {suffix}"))
        if label:
            for attr in attrs.get(normalize_name(label), []):
                return clean(attr.unit), status, f"{label} UOM", reason
        return None, status, label, reason
    # Existing tests and future explicitly named dynamic attributes may compare by exact attribute name.
    for attr in attrs.get(normalized, []):
        return clean(attr.normalized_value or attr.raw_value), "PARTIALLY_SUPPORTED", normalized, "matched an existing generated dynamic attribute by normalized name"
    return None, status, mapped, reason


def compare_values(expected: Optional[str], generated: Optional[str]) -> str:
    if expected is None and generated is None:
        return "EXACT_MATCH"
    if expected is None or generated is None:
        return "MISSING"
    if expected == generated:
        return "EXACT_MATCH"
    expected_normalized = LLMExtractionService.normalize_value_for_comparison(expected)
    generated_normalized = LLMExtractionService.normalize_value_for_comparison(generated)
    if expected_normalized == generated_normalized:
        return "NORMALIZED_MATCH"
    expected_tokens = set(normalize_name(expected_normalized).split())
    generated_tokens = set(normalize_name(generated_normalized).split())
    if expected_tokens and generated_tokens and len(expected_tokens & generated_tokens) / len(expected_tokens | generated_tokens) >= 0.6:
        return "PARTIAL_MATCH"
    return "INCORRECT"


def comparable_columns(frame: pd.DataFrame) -> list[str]:
    columns = []
    profiles = {item["name"]: item for item in profile_frame(frame)}
    for column, profile in profiles.items():
        if profile["comparison_status"] in {"SUPPORTED", "PARTIALLY_SUPPORTED"}:
            columns.append(column)
    return columns


def generated_keys(products) -> set[str]:
    return {clean(product.sku) for product in products if clean(product.sku)}


def aggregate(frame: pd.DataFrame, products, identifier_column: str, max_mismatches: int = 500) -> dict[str, Any]:
    profiles = {item["name"]: item for item in profile_frame(frame)}
    product_by_key = {clean(product.sku): product for product in products if clean(product.sku)}
    expected_keys = {clean(value) for value in frame[identifier_column].tolist() if clean(value)}
    matched_keys = expected_keys & set(product_by_key)
    mismatch_rows: list[dict[str, Any]] = []
    counters = defaultdict(lambda: {"expected_nonempty": 0, "exact_matches": 0, "normalized_matches": 0, "partial_matches": 0, "missing": 0, "incorrect": 0, "source_data_unavailable": 0, "pipeline_missing": 0, "evaluated": 0})
    mapped_fields: dict[str, Optional[str]] = {}
    for index, row in frame.iterrows():
        key = clean(row.get(identifier_column))
        product = product_by_key.get(key)
        attrs = _attributes(product) if product else {}
        comparison_columns = comparable_columns(frame)
        if product:
            known_attribute_names = set(attrs)
            for column in frame.columns:
                if column == identifier_column or column in comparison_columns:
                    continue
                profile_status = profiles.get(column, {}).get("comparison_status")
                if profile_status == "UNKNOWN" and normalize_name(column) in known_attribute_names:
                    comparison_columns.append(column)
        for column in comparison_columns:
            if column == identifier_column:
                continue
            expected = clean(row.get(column))
            generated, status, mapped, reason = _direct_generated(product, attrs, column, row) if product else (None, profiles[column]["comparison_status"], profiles[column].get("mapped_field"), profiles[column]["reason"])
            # Empty official cells are not valid accuracy denominators; they are reported separately by profile.
            if expected is None:
                continue
            metric_key = mapped or column
            mapped_fields[metric_key] = mapped
            counters[metric_key]["expected_nonempty"] += 1
            outcome = compare_values(expected, generated)
            source_available = _source_data_available(product, attrs, column, mapped, row)
            availability = "available" if source_available else "source_data_unavailable"
            if outcome == "MISSING":
                if source_available:
                    counters[metric_key]["pipeline_missing"] += 1
                else:
                    counters[metric_key]["source_data_unavailable"] += 1
            counters[metric_key]["evaluated"] += 1
            counters[metric_key][outcome.lower() + ("_matches" if outcome in {"EXACT_MATCH", "NORMALIZED_MATCH", "PARTIAL_MATCH"} else "") if False else "exact_matches"] += 0
            if outcome == "EXACT_MATCH": counters[metric_key]["exact_matches"] += 1
            elif outcome == "NORMALIZED_MATCH": counters[metric_key]["normalized_matches"] += 1
            elif outcome == "PARTIAL_MATCH": counters[metric_key]["partial_matches"] += 1
            elif outcome == "MISSING": counters[metric_key]["missing"] += 1
            else: counters[metric_key]["incorrect"] += 1
            if outcome in {"PARTIAL_MATCH", "MISSING", "INCORRECT"} and len(mismatch_rows) < max_mismatches:
                mismatch_rows.append({"product_key": key, "expected_row_number": int(index) + 2, "field_name": column, "mapped_field": mapped, "expected_value": expected, "generated_value": generated, "result": outcome, "availability": availability, "reason": reason})
    field_metrics = []
    for field_name, counts in counters.items():
        evaluated = counts["evaluated"]
        field_metrics.append({
            "field_name": field_name,
            "mapped_field": mapped_fields.get(field_name),
            **counts,
            "exact_match_rate": round(counts["exact_matches"] * 100 / evaluated, 1) if evaluated else None,
            "match_rate": round((counts["exact_matches"] + counts["normalized_matches"]) * 100 / evaluated, 1) if evaluated else None,
            "missing_value_rate": round(counts["missing"] * 100 / evaluated, 1) if evaluated else None,
            "comparison_status": profiles.get(field_name, {}).get("comparison_status", "SUPPORTED"),
            "reason": profiles.get(field_name, {}).get("reason"),
        })
    expected_nonempty_fields = sum(item["expected_nonempty"] for item in counters.values())
    exact = sum(item["exact_matches"] for item in counters.values())
    normalized = sum(item["normalized_matches"] for item in counters.values())
    partial = sum(item["partial_matches"] for item in counters.values())
    missing = sum(item["missing"] for item in counters.values())
    incorrect = sum(item["incorrect"] for item in counters.values())
    evaluated = sum(item["evaluated"] for item in counters.values())
    profiles_list = list(profiles.values())
    unsupported = [item["name"] for item in profiles_list if item["comparison_status"] == "UNSUPPORTED" and item["nonempty_count"]]
    unknown = [item["name"] for item in profiles_list if item["comparison_status"] == "UNKNOWN" and item["nonempty_count"]]
    return {
        "total_expected_products": len(frame),
        "products_matched": len(matched_keys),
        "products_missing_from_output": len(expected_keys - set(product_by_key)),
        "unexpected_products": len(set(product_by_key) - expected_keys),
        "expected_nonempty_fields": expected_nonempty_fields,
        "comparable_fields": evaluated,
        "exact_matches": exact,
        "normalized_matches": normalized,
        "partial_matches": partial,
        "missing_values": missing,
        "incorrect_values": incorrect,
        "source_data_unavailable": sum(item["source_data_unavailable"] for item in counters.values()),
        "pipeline_missing": sum(item["pipeline_missing"] for item in counters.values()),
        "overall_evaluation_rate": round((exact + normalized + partial + missing + incorrect) * 100 / expected_nonempty_fields, 1) if expected_nonempty_fields else None,
        "overall_match_rate": round((exact + normalized) * 100 / evaluated, 1) if evaluated else None,
        "overall_missing_value_rate": round(missing * 100 / evaluated, 1) if evaluated else None,
        "field_metrics": field_metrics,
        "mismatches": mismatch_rows,
        "unsupported_columns": unsupported,
        "unknown_columns": unknown,
        "lov_comparison_available": False,
        "uom_comparison_available": any("ATTRIBUTE_UOM" in column for column in frame.columns),
        "character_limits_available": False,
    }
