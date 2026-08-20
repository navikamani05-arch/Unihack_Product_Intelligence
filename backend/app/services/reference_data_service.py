"""Official-reference-data import and explainable resolution services for Phase 5.

No service in this module treats an LLM-proposed value as approved unless it
matches an active imported official reference dataset.
"""
from __future__ import annotations

import hashlib
import json
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable, Optional

import pandas as pd
from sqlalchemy.orm import Session

from app.models.product import ProductAttribute, ProductRecord
from app.models.reference_data import (
    BrandMaster,
    FractionConversion,
    LOVEntry,
    ManufacturerMaster,
    ProductNormalizationDecision,
    ReferenceDataset,
    UOMEntry,
)

PLACEHOLDER_VALUES = {
    "unbranded", "no unilog brand", "no dib brand", "not available", "n a", "na", "none", "null", "unknown",
}
DATASET_TYPES = {
    "manufacturer_brand": "Manufacturer/Brand Master",
    "lov": "Unilog LOV",
    "uom": "UOM Master",
    "fraction": "Decimal/Fraction Master",
    "faucets_lov": "Faucets LOV",
    "fittings_lov": "Fittings LOV",
}


def comparison_value(value: Any) -> str:
    """Canonical comparison key that preserves official display values separately."""
    if value is None:
        return ""
    text = str(value).strip().casefold()
    text = re.sub(r"[®™]", "", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def is_placeholder(value: Any) -> bool:
    compact = comparison_value(value)
    return not compact or compact in PLACEHOLDER_VALUES


def _clean(value: Any) -> Optional[str]:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def _split_values(value: Any) -> list[str]:
    text = _clean(value)
    if not text:
        return []
    return [part.strip() for part in re.split(r"[;\n|]", text) if part.strip()]


class ReferenceDataService:
    """Keeps official display values immutable and exposes deterministic decisions."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def infer_dataset_type(file_name: str, requested_type: Optional[str] = None) -> str:
        if requested_type and requested_type in DATASET_TYPES:
            return requested_type
        name = file_name.casefold()
        if "manufacturer" in name and "brand" in name:
            return "manufacturer_brand"
        if "decimal" in name and "fraction" in name:
            return "fraction"
        if "uom" in name or "unit" in name:
            return "uom"
        if "faucet" in name:
            return "faucets_lov"
        if "fitting" in name:
            return "fittings_lov"
        if "lov" in name:
            return "lov"
        raise ValueError("Unable to infer reference dataset type; provide a supported dataset_type.")

    @staticmethod
    def _read_sheets(path: Path) -> dict[str, pd.DataFrame]:
        if path.suffix.casefold() == ".csv":
            return {"CSV": pd.read_csv(path, header=None, dtype=str, keep_default_na=False)}
        if path.suffix.casefold() not in {".xlsx", ".xls"}:
            raise ValueError("Reference data must be CSV, XLSX, or XLS.")
        return pd.read_excel(path, sheet_name=None, header=None, dtype=str, keep_default_na=False)

    @staticmethod
    def _detect_header(raw: pd.DataFrame, required_groups: list[set[str]]) -> tuple[int, list[str]]:
        for index in range(min(12, len(raw))):
            headers = [_clean(value) or "" for value in raw.iloc[index].tolist()]
            normalized = [comparison_value(value).replace(" ", "_") for value in headers]
            available = set(normalized)
            if all(group & available for group in required_groups):
                return index, headers
        raise ValueError("Could not detect required official reference-data headers in the first 12 rows.")

    @staticmethod
    def _column(frame: pd.DataFrame, aliases: Iterable[str]) -> Optional[str]:
        lookup = {comparison_value(column).replace(" ", "_"): column for column in frame.columns}
        for alias in aliases:
            if alias in lookup:
                return lookup[alias]
        return None

    def _active_datasets(self, *types: str) -> list[ReferenceDataset]:
        return (
            self.db.query(ReferenceDataset)
            .filter(ReferenceDataset.dataset_type.in_(types), ReferenceDataset.is_active.is_(True), ReferenceDataset.status == "available")
            .order_by(ReferenceDataset.imported_at.desc(), ReferenceDataset.id.desc())
            .all()
        )

    def _active_dataset(self, *types: str) -> Optional[ReferenceDataset]:
        datasets = self._active_datasets(*types)
        return datasets[0] if datasets else None

    def registry(self) -> list[dict[str, Any]]:
        rows = self.db.query(ReferenceDataset).order_by(ReferenceDataset.dataset_type, ReferenceDataset.id.desc()).all()
        present = {row.dataset_type for row in rows if row.is_active and row.status == "available"}
        output = [self._dataset_payload(row) for row in rows]
        for dataset_type, label in DATASET_TYPES.items():
            if dataset_type not in present and not any(row["dataset_type"] == dataset_type for row in output):
                output.append({"dataset_type": dataset_type, "name": label, "status": "not_available", "is_active": False, "row_count": None})
        return output

    @staticmethod
    def _dataset_payload(dataset: ReferenceDataset) -> dict[str, Any]:
        return {
            "id": dataset.id, "dataset_type": dataset.dataset_type, "name": dataset.name,
            "file_name": dataset.file_name, "version": dataset.version, "row_count": dataset.row_count,
            "status": dataset.status, "is_active": dataset.is_active, "checksum": dataset.checksum,
            "imported_at": dataset.imported_at, "sheet_names": dataset.sheet_names,
            "import_statistics": dataset.import_statistics,
        }

    def import_dataset(self, path: Path, dataset_type: Optional[str] = None, version: Optional[str] = None) -> dict[str, Any]:
        dataset_type = self.infer_dataset_type(path.name, dataset_type)
        contents = path.read_bytes()
        checksum = hashlib.sha256(contents).hexdigest()
        sheets = self._read_sheets(path)
        rows_imported = duplicates = empty_removed = 0
        detected_headers: list[str] = []
        # Only one official import of a dataset type is active at a time. Historical
        # imports remain preserved but cannot influence current approvals.
        self.db.query(ReferenceDataset).filter_by(dataset_type=dataset_type, is_active=True).update({"is_active": False})
        dataset = ReferenceDataset(
            dataset_type=dataset_type, name=DATASET_TYPES[dataset_type], file_name=path.name,
            version=version, file_path=str(path), checksum=checksum, status="importing", is_active=True,
            sheet_names=list(sheets),
        )
        self.db.add(dataset)
        self.db.flush()
        for sheet_name, raw in sheets.items():
            statistics = self._import_sheet(dataset, dataset_type, raw)
            rows_imported += statistics["rows_imported"]
            duplicates += statistics["duplicates"]
            empty_removed += statistics["empty_removed"]
            detected_headers.extend(statistics["headers"])
        dataset.row_count = rows_imported
        dataset.status = "available"
        from datetime import datetime
        dataset.imported_at = datetime.utcnow()
        dataset.import_statistics = {"rows_imported": rows_imported, "duplicates": duplicates, "empty_rows_removed": empty_removed, "headers_detected": sorted(set(detected_headers))}
        self.db.commit()
        self.db.refresh(dataset)
        payload = self._dataset_payload(dataset)
        payload.update({"duplicate_rows": duplicates, "empty_rows_removed": empty_removed, "headers_detected": sorted(set(detected_headers))})
        return payload

    def _frame(self, raw: pd.DataFrame, required: list[set[str]]) -> tuple[pd.DataFrame, list[str]]:
        header_index, headers = self._detect_header(raw, required)
        frame = raw.iloc[header_index + 1 :].copy()
        frame.columns = headers
        frame = frame.replace(r"^\s*$", None, regex=True).dropna(how="all")
        return frame, [header for header in headers if header]

    def _import_sheet(self, dataset: ReferenceDataset, dataset_type: str, raw: pd.DataFrame) -> dict[str, Any]:
        if dataset_type == "manufacturer_brand":
            frame, headers = self._frame(raw, [{"manufacturer_name", "manufacturer"}, {"brand_name", "brand"}])
            return self._import_manufacturers(dataset, frame, headers)
        if dataset_type in {"lov", "faucets_lov", "fittings_lov"}:
            frame, headers = self._frame(raw, [{"attribute_label", "attribute"}, {"attribute_values", "attribute_value", "values"}])
            return self._import_lov(dataset, frame, headers)
        if dataset_type == "uom":
            frame, headers = self._frame(raw, [{"uom", "abbreviation", "unit", "uom_abbreviation"}])
            return self._import_uom(dataset, frame, headers)
        frame, headers = self._frame(raw, [{"decimal", "decimal_value"}, {"fraction", "fraction_value"}])
        return self._import_fraction(dataset, frame, headers)

    def _import_manufacturers(self, dataset: ReferenceDataset, frame: pd.DataFrame, headers: list[str]) -> dict[str, Any]:
        manufacturer_col = self._column(frame, ["manufacturer_name", "manufacturer"])
        manufacturer_code_col = self._column(frame, ["manufacturer_code", "mfr_code", "manufacturer_id"])
        manufacturer_alias_col = self._column(frame, ["alternate_names", "manufacturer_aliases", "aliases"])
        brand_col = self._column(frame, ["brand_name", "brand"])
        brand_code_col = self._column(frame, ["brand_code", "brand_id"])
        brand_alias_col = self._column(frame, ["brand_alternate_names", "brand_aliases"])
        imported = duplicates = empty = source_rows = 0
        cache: dict[str, ManufacturerMaster] = {}
        for _, row in frame.iterrows():
            manufacturer = _clean(row.get(manufacturer_col)) if manufacturer_col else None
            brand = _clean(row.get(brand_col)) if brand_col else None
            if not manufacturer and not brand:
                empty += 1; continue
            source_rows += 1
            master = None
            if manufacturer:
                key = comparison_value(manufacturer)
                master = cache.get(key) or self.db.query(ManufacturerMaster).filter_by(dataset_id=dataset.id, comparison_value=key).first()
                if not master:
                    master = ManufacturerMaster(dataset_id=dataset.id, display_value=manufacturer, comparison_value=key, manufacturer_code=_clean(row.get(manufacturer_code_col)) if manufacturer_code_col else None, aliases=_split_values(row.get(manufacturer_alias_col)) if manufacturer_alias_col else [])
                    self.db.add(master); self.db.flush(); imported += 1
                else:
                    duplicates += 1
                cache[key] = master
            if brand and not is_placeholder(brand):
                brand_key = comparison_value(brand)
                exists = self.db.query(BrandMaster).filter_by(dataset_id=dataset.id, manufacturer_code=master.manufacturer_code if master else None, comparison_value=brand_key).first()
                if exists:
                    duplicates += 1
                else:
                    self.db.add(BrandMaster(dataset_id=dataset.id, manufacturer_master_id=master.id if master else None, manufacturer_code=master.manufacturer_code if master else None, display_value=brand, comparison_value=brand_key, brand_code=_clean(row.get(brand_code_col)) if brand_code_col else None, aliases=_split_values(row.get(brand_alias_col)) if brand_alias_col else [])); imported += 1
        return {"rows_imported": source_rows, "duplicates": duplicates, "empty_removed": empty, "headers": headers}

    def _import_lov(self, dataset: ReferenceDataset, frame: pd.DataFrame, headers: list[str]) -> dict[str, Any]:
        cols = {
            "classpath": self._column(frame, ["classpath", "class_path"]), "leaf": self._column(frame, ["leaf_node", "leaf"]),
            "label": self._column(frame, ["attribute_label", "attribute"]), "values": self._column(frame, ["attribute_values", "attribute_value", "values"]),
            "normalized_label": self._column(frame, ["normalized_label"]), "normalized_values": self._column(frame, ["normalized_values"]),
            "filtering": self._column(frame, ["filtering_y_n", "filtering", "filtering_flag"]), "guidelines": self._column(frame, ["guidelines", "guideline"]), "remarks": self._column(frame, ["remarks", "remark"]),
        }
        imported = empty = 0
        for _, row in frame.iterrows():
            label = _clean(row.get(cols["label"])) if cols["label"] else None
            values = _clean(row.get(cols["values"])) if cols["values"] else None
            if not label or not values:
                empty += 1; continue
            self.db.add(LOVEntry(dataset_id=dataset.id, classpath=_clean(row.get(cols["classpath"])) if cols["classpath"] else None, classpath_comparison=comparison_value(row.get(cols["classpath"])) if cols["classpath"] else None, leaf_node=_clean(row.get(cols["leaf"])) if cols["leaf"] else None, attribute_label=label, attribute_comparison=comparison_value(label), attribute_values=values, normalized_label=_clean(row.get(cols["normalized_label"])) if cols["normalized_label"] else None, normalized_values=_clean(row.get(cols["normalized_values"])) if cols["normalized_values"] else None, filtering_flag=_clean(row.get(cols["filtering"])) if cols["filtering"] else None, guidelines=_clean(row.get(cols["guidelines"])) if cols["guidelines"] else None, remarks=_clean(row.get(cols["remarks"])) if cols["remarks"] else None)); imported += 1
        return {"rows_imported": imported, "duplicates": 0, "empty_removed": empty, "headers": headers}

    def _import_uom(self, dataset: ReferenceDataset, frame: pd.DataFrame, headers: list[str]) -> dict[str, Any]:
        source_col = self._column(frame, ["abbreviation", "uom", "unit", "uom_abbreviation"])
        display_col = self._column(frame, ["display_uom", "display_value", "normalized_uom"])
        terms_col = self._column(frame, ["terms", "term", "aliases", "full_term", "synonyms"])
        imported = duplicates = empty = 0
        for _, row in frame.iterrows():
            canonical = (_clean(row.get(display_col)) if display_col else None) or (_clean(row.get(source_col)) if source_col else None)
            if not canonical:
                empty += 1; continue
            key = comparison_value(canonical)
            if self.db.query(UOMEntry).filter_by(dataset_id=dataset.id, comparison_value=key).first():
                duplicates += 1; continue
            source_value = _clean(row.get(source_col)) if source_col else None
            terms = list(dict.fromkeys([term for term in [canonical, source_value, *(_split_values(row.get(terms_col)) if terms_col else [])] if term]))
            self.db.add(UOMEntry(dataset_id=dataset.id, display_value=canonical, comparison_value=key, terms=terms)); imported += 1
        return {"rows_imported": imported, "duplicates": duplicates, "empty_removed": empty, "headers": headers}

    def _import_fraction(self, dataset: ReferenceDataset, frame: pd.DataFrame, headers: list[str]) -> dict[str, Any]:
        decimal_col = self._column(frame, ["decimal", "decimal_value"])
        fraction_col = self._column(frame, ["fraction", "fraction_value"])
        imported = duplicates = empty = 0
        for _, row in frame.iterrows():
            decimal, fraction = (_clean(row.get(decimal_col)) if decimal_col else None), (_clean(row.get(fraction_col)) if fraction_col else None)
            if not decimal or not fraction:
                empty += 1; continue
            key = comparison_value(decimal)
            if self.db.query(FractionConversion).filter_by(dataset_id=dataset.id, comparison_value=key).first():
                duplicates += 1; continue
            self.db.add(FractionConversion(dataset_id=dataset.id, original_value=decimal, comparison_value=key, fraction_value=fraction)); imported += 1
        return {"rows_imported": imported, "duplicates": duplicates, "empty_removed": empty, "headers": headers}

    @staticmethod
    def _unavailable(value: Optional[str], label: str) -> dict[str, Any]:
        return {"input": value, "canonical_name": None, "match_type": "reference_data_unavailable", "status": "REFERENCE_DATA_UNAVAILABLE", "confidence": None, "candidates": [], "reference_dataset": None, "explanation": f"No active official {label} dataset has been imported; the value is not approved."}

    def resolve_manufacturer(self, value: Optional[str]) -> dict[str, Any]:
        dataset = self._active_dataset("manufacturer_brand")
        if not dataset: return self._unavailable(value, "manufacturer/brand master")
        if is_placeholder(value):
            return {"input": value, "canonical_name": None, "manufacturer_code": None, "match_type": "empty", "status": "NOT_FOUND", "confidence": None, "candidates": [], "reference_dataset": dataset.name, "explanation": "The supplied manufacturer is empty or a placeholder."}
        key = comparison_value(value)
        all_rows = self.db.query(ManufacturerMaster).filter_by(dataset_id=dataset.id).all()
        matches = [row for row in all_rows if key in {row.comparison_value, comparison_value(row.manufacturer_code), *{comparison_value(alias) for alias in (row.aliases or [])}}]
        if len(matches) == 1:
            match = matches[0]
            is_alias = key in {comparison_value(alias) for alias in (match.aliases or [])}
            is_exact = key in {match.comparison_value, comparison_value(match.manufacturer_code)}
            return {"input": value, "canonical_name": match.display_value, "manufacturer_code": match.manufacturer_code, "match_type": "exact" if is_exact else "alias" if is_alias else "normalized", "status": "APPROVED", "confidence": 1.0 if is_exact else 0.98, "candidates": [], "reference_dataset": dataset.name, "explanation": "Matched an official manufacturer master value or alias."}
        candidates = sorted(((SequenceMatcher(None, key, row.comparison_value).ratio(), row) for row in all_rows), reverse=True, key=lambda item: item[0])[:5]
        visible = [{"display_value": row.display_value, "code": row.manufacturer_code, "score": round(score, 3)} for score, row in candidates if score >= 0.55]
        if candidates and candidates[0][0] >= 0.86 and (len(candidates) == 1 or candidates[0][0] - candidates[1][0] >= 0.08):
            score, row = candidates[0]
            return {"input": value, "canonical_name": row.display_value, "manufacturer_code": row.manufacturer_code, "match_type": "fuzzy", "status": "CANDIDATE", "confidence": round(score, 3), "candidates": visible, "reference_dataset": dataset.name, "explanation": "A unique fuzzy candidate was found and requires review before approval."}
        if visible:
            return {"input": value, "canonical_name": None, "manufacturer_code": None, "match_type": "ambiguous", "status": "AMBIGUOUS", "confidence": None, "candidates": visible, "reference_dataset": dataset.name, "explanation": "Multiple manufacturer candidates are plausible; none was selected."}
        return {"input": value, "canonical_name": None, "manufacturer_code": None, "match_type": "not_found", "status": "NOT_FOUND", "confidence": None, "candidates": [], "reference_dataset": dataset.name, "explanation": "No official manufacturer master match was found."}

    def resolve_brand(self, brand_value: Optional[str], manufacturer_value: Optional[str] = None) -> dict[str, Any]:
        dataset = self._active_dataset("manufacturer_brand")
        if not dataset: return self._unavailable(brand_value, "manufacturer/brand master")
        if is_placeholder(brand_value):
            return {"input": brand_value, "canonical_name": None, "brand_code": None, "match_type": "empty", "status": "NOT_FOUND", "confidence": None, "candidates": [], "reference_dataset": dataset.name, "explanation": "The supplied brand is empty or a Unilog placeholder."}
        manufacturer = self.resolve_manufacturer(manufacturer_value) if manufacturer_value else None
        key = comparison_value(brand_value)
        brands = [brand for brand in self.db.query(BrandMaster).filter_by(dataset_id=dataset.id).all() if key in {brand.comparison_value, comparison_value(brand.brand_code), *{comparison_value(alias) for alias in (brand.aliases or [])}}]
        if not brands:
            return {"input": brand_value, "canonical_name": None, "brand_code": None, "match_type": "not_found", "status": "NOT_FOUND", "confidence": None, "candidates": [], "reference_dataset": dataset.name, "explanation": "No official brand master match was found."}
        if manufacturer and manufacturer.get("status") == "APPROVED":
            valid = [brand for brand in brands if brand.manufacturer_code == manufacturer.get("manufacturer_code")]
            if not valid:
                return {"input": brand_value, "canonical_name": None, "brand_code": None, "match_type": "manufacturer_mismatch", "status": "BRAND_MANUFACTURER_MISMATCH", "confidence": None, "candidates": [{"display_value": brand.display_value, "code": brand.brand_code, "manufacturer_code": brand.manufacturer_code} for brand in brands], "reference_dataset": dataset.name, "explanation": "The matching official brand belongs to a different manufacturer; no correction was made."}
            brands = valid
        if len(brands) == 1:
            brand = brands[0]
            alias_match = key in {comparison_value(alias) for alias in (brand.aliases or [])}
            exact_match = key in {brand.comparison_value, comparison_value(brand.brand_code)}
            return {"input": brand_value, "canonical_name": brand.display_value, "brand_code": brand.brand_code, "manufacturer_code": brand.manufacturer_code, "match_type": "exact" if exact_match else "alias" if alias_match else "normalized", "status": "APPROVED", "confidence": 1.0 if exact_match else 0.98, "candidates": [], "reference_dataset": dataset.name, "explanation": "Matched an official brand/master-manufacturer pairing."}
        return {"input": brand_value, "canonical_name": None, "brand_code": None, "match_type": "ambiguous", "status": "AMBIGUOUS", "confidence": None, "candidates": [{"display_value": brand.display_value, "code": brand.brand_code, "manufacturer_code": brand.manufacturer_code} for brand in brands], "reference_dataset": dataset.name, "explanation": "More than one official brand pairing matches; none was selected."}

    def resolve_attribute(self, classpath: Optional[str], leaf_node: Optional[str], attribute: str, candidate_value: Optional[str]) -> dict[str, Any]:
        datasets = self._active_datasets("lov", "faucets_lov", "fittings_lov")
        base = {"allowed": False, "status": "REFERENCE_DATA_UNAVAILABLE", "canonical_attribute_label": None, "canonical_value": None, "normalized_value": None, "filtering_flag": None, "guideline": None, "remarks": None, "confidence": None, "match_type": "reference_data_unavailable", "reference_dataset": None}
        if not datasets:
            return base | {"explanation": "No active official LOV dataset has been imported; the candidate is not approved."}
        dataset_ids = [dataset.id for dataset in datasets]
        query = self.db.query(LOVEntry).filter(LOVEntry.dataset_id.in_(dataset_ids), LOVEntry.attribute_comparison == comparison_value(attribute))
        if classpath:
            query = query.filter(LOVEntry.classpath_comparison == comparison_value(classpath))
        entries = query.all()
        if leaf_node:
            entries = [entry for entry in entries if comparison_value(entry.leaf_node) == comparison_value(leaf_node)]
        if not entries:
            return base | {"status": "NOT_IN_APPROVED_LOV", "match_type": "attribute_not_found", "reference_dataset": None, "explanation": "No approved LOV entry exists for this category-scoped attribute."}
        candidate_key = comparison_value(candidate_value)
        for entry in entries:
            approved = _split_values(entry.normalized_values) or _split_values(entry.attribute_values)
            for value in approved:
                if candidate_key == comparison_value(value):
                    canonical = value
                    return {"allowed": True, "status": "APPROVED", "canonical_attribute_label": entry.normalized_label or entry.attribute_label, "canonical_value": canonical, "normalized_value": canonical, "filtering_flag": entry.filtering_flag, "guideline": entry.guidelines, "remarks": entry.remarks, "confidence": 1.0 if candidate_value == canonical else 0.96, "match_type": "exact" if candidate_value == canonical else "normalized", "reference_dataset": entry.dataset.name, "explanation": "Matched a category-scoped approved LOV value."}
        first = entries[0]
        return {"allowed": False, "status": "NOT_IN_APPROVED_LOV", "canonical_attribute_label": first.normalized_label or first.attribute_label, "canonical_value": None, "normalized_value": None, "filtering_flag": first.filtering_flag, "guideline": first.guidelines, "remarks": first.remarks, "confidence": None, "match_type": "not_in_lov", "reference_dataset": first.dataset.name, "explanation": "The candidate value is not present in the approved category-scoped LOV; no replacement was invented."}

    def normalize_uom(self, value: Optional[str], uom: Optional[str] = None) -> dict[str, Any]:
        dataset = self._active_dataset("uom")
        original = value if value is not None else uom
        if not dataset:
            return {"original_value": original, "normalized_value": original, "uom": None, "uom_source": "unavailable", "normalization_rule": None, "status": "REFERENCE_DATA_UNAVAILABLE", "reference_dataset": None, "explanation": "No official UOM master has been imported; no value was approved or altered."}
        value_for_parse = re.sub(r"\b([A-Za-z]+)(?:\s+\1)+\b", r"\1", value or "", flags=re.IGNORECASE)
        match = re.match(r"^\s*(.+?)\s*([A-Za-z.]+)\s*$", value_for_parse) if value else None
        numeric, candidate = (match.group(1).strip(), match.group(2).strip()) if match else (None, uom)
        key = comparison_value(candidate)
        entries = self.db.query(UOMEntry).filter_by(dataset_id=dataset.id).all()
        entry = next((item for item in entries if item.comparison_value == key or key in {comparison_value(term) for term in (item.terms or [])}), None)
        if not entry:
            return {"original_value": original, "normalized_value": original, "uom": candidate, "uom_source": "official_master", "normalization_rule": None, "status": "NOT_IN_OFFICIAL_UOM", "reference_dataset": dataset.name, "explanation": "The UOM is not in the imported official master; no replacement was invented."}
        normalized = f"{numeric} {entry.display_value}" if numeric else entry.display_value
        normalized = re.sub(rf"\s+{re.escape(entry.display_value)}(?:\s+{re.escape(entry.display_value)})+$", f" {entry.display_value}", normalized, flags=re.I)
        return {"original_value": original, "normalized_value": normalized, "uom": entry.display_value, "uom_source": "official_master", "normalization_rule": "official_uom_alias_and_spacing", "status": "APPROVED", "reference_dataset": dataset.name, "explanation": "Normalized using an imported official UOM master term."}

    def normalize_fraction(self, value: Optional[str]) -> dict[str, Any]:
        dataset = self._active_dataset("fraction")
        if not dataset:
            return {"original_value": value, "normalized_value": value, "status": "REFERENCE_DATA_UNAVAILABLE", "normalization_rule": None, "reference_dataset": None, "explanation": "No official decimal/fraction dataset has been imported; no conversion was made."}
        match = re.match(r"^\s*(\d+)?(?:\.(\d+))?\s*(.*)$", value or "")
        if not match or not match.group(2):
            return {"original_value": value, "normalized_value": value, "status": "NOT_FOUND", "normalization_rule": None, "reference_dataset": dataset.name, "explanation": "No exact decimal portion was available for official lookup conversion."}
        whole, decimal, suffix = match.group(1) or "0", f"0.{match.group(2)}", match.group(3).strip()
        row = self.db.query(FractionConversion).filter_by(dataset_id=dataset.id, comparison_value=comparison_value(decimal)).first()
        if not row:
            return {"original_value": value, "normalized_value": value, "status": "NOT_FOUND", "normalization_rule": None, "reference_dataset": dataset.name, "explanation": "No exact official decimal-to-fraction lookup exists; no approximation was made."}
        core = row.fraction_value if whole == "0" else f"{whole} {row.fraction_value}"
        return {"original_value": value, "normalized_value": f"{core} {suffix}".strip(), "status": "APPROVED", "normalization_rule": "official_exact_decimal_fraction_lookup", "reference_dataset": dataset.name, "explanation": "Converted using an exact imported official decimal/fraction lookup."}

    def _decision(self, product: ProductRecord, attribute: Optional[ProductAttribute], dataset: Optional[ReferenceDataset], decision_type: str, original: Optional[str], result: dict[str, Any], provenance: Optional[dict[str, Any]] = None) -> None:
        canonical = result.get("canonical_name") or result.get("canonical_value") or result.get("normalized_value")
        self.db.add(ProductNormalizationDecision(product_id=product.id, attribute_id=attribute.id if attribute else None, reference_dataset_id=dataset.id if dataset else None, decision_type=decision_type, original_value=original, canonical_value=canonical, status=result.get("status", "REFERENCE_DATA_UNAVAILABLE"), match_type=result.get("match_type"), confidence=result.get("confidence"), explanation=result.get("explanation", "No explanation returned."), provenance_snapshot=provenance))

    def validate_extracted_product(self, product: ProductRecord) -> None:
        """Record approval decisions after LLM extraction without weakening evidence or isolation rules."""
        attributes = self.db.query(ProductAttribute).filter_by(product_id=product.id).all()
        manufacturer_attr = next((item for item in attributes if comparison_value(item.attribute_name) in {"manufacturer", "manufacturer name"}), None)
        brand_attr = next((item for item in attributes if comparison_value(item.attribute_name) in {"brand", "brand name", "manufacturer brand", "e1 brand", "unilog brand", "dib brand"}), None)
        manufacturer_value = manufacturer_attr.raw_value if manufacturer_attr else product.manufacturer
        if manufacturer_value:
            result = self.resolve_manufacturer(manufacturer_value)
            manufacturer_provenance = self._provenance(manufacturer_attr) if manufacturer_attr else {"source_type": product.sku_source_type, "source_identifier": product.sku_source_identifier, "source_url": product.sku_source_url, "page_number": product.sku_page_number, "row_number": product.sku_row_number, "evidence_chunk_id": product.sku_evidence_chunk_id}
            self._decision(product, manufacturer_attr, self._active_dataset("manufacturer_brand"), "manufacturer_resolution", manufacturer_value, result, manufacturer_provenance)
            if result.get("status") == "APPROVED":
                product.manufacturer = result.get("canonical_name")
        if brand_attr:
            result = self.resolve_brand(brand_attr.raw_value, manufacturer_value)
            self._decision(product, brand_attr, self._active_dataset("manufacturer_brand"), "brand_resolution", brand_attr.raw_value, result, self._provenance(brand_attr))
            if result.get("status") == "APPROVED":
                brand_attr.normalized_value = result.get("canonical_name")
        for attribute in attributes:
            if comparison_value(attribute.attribute_name) in {"manufacturer", "manufacturer name", "brand", "brand name", "manufacturer brand", "e1 brand", "unilog brand", "dib brand"}:
                continue
            lov = self.resolve_attribute(product.category, None, attribute.attribute_name, attribute.raw_value)
            self._decision(product, attribute, self._active_dataset("lov", "faucets_lov", "fittings_lov"), "lov_validation", attribute.raw_value, lov, self._provenance(attribute))
            if lov.get("status") == "APPROVED":
                attribute.normalized_value = lov.get("normalized_value") or attribute.normalized_value
            uom = self.normalize_uom(attribute.raw_value, attribute.unit)
            self._decision(product, attribute, self._active_dataset("uom"), "uom_normalization", attribute.raw_value, uom, self._provenance(attribute))
            if uom.get("status") == "APPROVED":
                attribute.unit = uom.get("uom")
                attribute.normalized_value = uom.get("normalized_value") or attribute.normalized_value

    @staticmethod
    def _provenance(attribute: ProductAttribute) -> dict[str, Any]:
        return {"source_type": attribute.source_type, "source_identifier": attribute.source_identifier, "source_url": attribute.source_url, "page_number": attribute.page_number, "row_number": attribute.row_number, "evidence_chunk_id": attribute.evidence_chunk_id}
