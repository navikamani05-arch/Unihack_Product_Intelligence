"""Phase 4 evaluation service.

Rule-quality evaluation validates persisted generated products against transparent baseline checks.
It never presents those checks as ground-truth accuracy. Ground-truth comparison is enabled only
when a user has uploaded an official expected-output CSV/XLSX dataset.
"""
from __future__ import annotations

import re
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

import pandas as pd
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.models.evaluation import (
    EvaluationExpectedDataset,
    EvaluationFieldResult,
    EvaluationProductResult,
    EvaluationRun,
)
from app.models.product import ProductAttribute, ProductRecord
from app.schemas.evaluation_schema import (
    EvaluationFailureResponse,
    EvaluationFailuresResponse,
    EvaluationFieldResponse,
    EvaluationProductResponse,
    EvaluationSummaryResponse,
    FieldMetricResponse,
    GroundTruthAvailabilityResponse,
    GroundTruthComparisonResponse,
    GroundTruthComparisonRow,
)
from app.services.llm_extraction_service import LLMExtractionService
from app.services.official_ground_truth_service import aggregate as official_aggregate
from app.services.official_ground_truth_service import identify_column as identify_official_column
from app.services.official_ground_truth_service import load_frame as load_official_frame
from app.services.official_ground_truth_service import profile_frame as profile_official_frame


RAW_INPUT_COLUMNS = {
    "manufacturer_part_number": "Mfg_Part_Num",
    "source_description": "Part_Desc",
    "e1_brand": "E1_Brand",
    "unilog_brand": "Unilog_Brand",
    "dib_brand": "DIB_Brand",
    "source_manufacturer": "Part_Manuf",
}
PLACEHOLDERS = {
    "-- unbranded --",
    "-- no unilog brand --",
    "-- no dib brand --",
    "unbranded",
    "n/a",
    "na",
    "none",
    "null",
    "unknown",
    "not available",
    "not found in provided sources",
}
METRICS = (
    ("manufacturer", "Manufacturer normalization compliance"),
    ("brand", "Brand normalization compliance"),
    ("uom", "UOM compliance"),
    ("lov", "LOV value compliance"),
    ("required", "Required-field completeness"),
    ("character_limit", "Character-limit compliance"),
    ("placeholder", "Placeholder removal"),
    ("title_formula", "Product title formula compliance"),
    ("description_format", "Description format compliance"),
    ("evidence", "Evidence/provenance coverage"),
    ("authority", "Source-authority compliance"),
    ("normalization", "Normalization consistency"),
)
IDENTIFIER_ALIASES = (
    "mfg part num",
    "manufacturer part number",
    "manufacturer_part_number",
    "mpn",
    "sku",
    "part number",
    "product id",
)


class EvaluationDomainError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class EvaluationService:
    """Provides transparent quality checks and optional expected-output comparison."""

    @staticmethod
    def _dataset_path() -> Path:
        path = Path(settings.evaluation_input_dataset_path)
        if not path.is_absolute():
            path = Path(__file__).resolve().parents[2] / path
        return path

    @staticmethod
    def _clean(value: Any) -> Optional[str]:
        if value is None or pd.isna(value):
            return None
        cleaned = str(value).strip()
        if not cleaned or cleaned.lower() in PLACEHOLDERS:
            return None
        return cleaned

    @classmethod
    def _load_csv(cls) -> pd.DataFrame:
        path = cls._dataset_path()
        if not path.exists():
            raise EvaluationDomainError(f"Input dataset not found: {path}", 404)
        frame = pd.read_csv(path, dtype="string", keep_default_na=False)
        missing = [column for column in RAW_INPUT_COLUMNS.values() if column not in frame.columns]
        if missing:
            raise EvaluationDomainError(
                "Input dataset does not match the supplied Unilog raw-input schema; missing: "
                + ", ".join(missing)
            )
        return frame

    @staticmethod
    def _normalized_name(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()

    @classmethod
    def _is_placeholder(cls, value: Optional[str]) -> bool:
        return cls._clean(value) is None

    @staticmethod
    def _field(attribute_name: str) -> str:
        return re.sub(r"[^a-z0-9]+", "_", attribute_name.lower()).strip("_")

    @classmethod
    def _attributes(cls, product: ProductRecord) -> dict[str, list[ProductAttribute]]:
        values: dict[str, list[ProductAttribute]] = defaultdict(list)
        for attribute in product.attributes:
            values[cls._field(attribute.attribute_name)].append(attribute)
        return values

    @classmethod
    def _attribute_value(cls, values: dict[str, list[ProductAttribute]], *aliases: str) -> Optional[str]:
        for alias in aliases:
            attributes = values.get(cls._field(alias), [])
            for attribute in attributes:
                value = cls._clean(attribute.normalized_value or attribute.raw_value)
                if value:
                    return value
        return None

    @classmethod
    def _product_for_key(cls, db: Session, key: Optional[str]) -> Optional[ProductRecord]:
        if not key:
            return None
        return (
            db.query(ProductRecord)
            .options(joinedload(ProductRecord.attributes))
            .filter(ProductRecord.sku == key)
            .first()
        )

    @classmethod
    def _snapshot(cls, product: ProductRecord) -> dict[str, Any]:
        attributes = {}
        for attribute in product.attributes:
            attributes[attribute.attribute_name] = {
                "raw_value": attribute.raw_value,
                "normalized_value": attribute.normalized_value,
                "unit": attribute.unit,
                "confidence_score": attribute.confidence_score,
                "source_type": attribute.source_type,
                "source_identifier": attribute.source_identifier,
                "source_url": attribute.source_url,
                "page_number": attribute.page_number,
                "row_number": attribute.row_number,
                "evidence_chunk_id": attribute.evidence_chunk_id,
            }
        return {
            "sku": product.sku,
            "name": product.name,
            "description": product.description,
            "manufacturer": product.manufacturer,
            "category": product.category,
            "sku_provenance": {
                "source_type": product.sku_source_type,
                "source_identifier": product.sku_source_identifier,
                "source_url": product.sku_source_url,
                "page_number": product.sku_page_number,
                "row_number": product.sku_row_number,
                "evidence_chunk_id": product.sku_evidence_chunk_id,
            },
            "attributes": attributes,
        }

    @classmethod
    def _result(cls, product_result: EvaluationProductResult, field: str, check: str,
                outcome: str, generated: Optional[str], details: str,
                severity: str = "LOW", expected: Optional[str] = None,
                normalized_expected: Optional[str] = None,
                normalized_generated: Optional[str] = None) -> EvaluationFieldResult:
        return EvaluationFieldResult(
            product_result=product_result,
            field_name=field,
            check_name=check,
            outcome=outcome,
            expected_value=expected,
            generated_value=generated,
            normalized_expected_value=normalized_expected,
            normalized_generated_value=normalized_generated,
            details=details,
            severity=severity,
        )

    @classmethod
    def _missing_output_checks(cls, result: EvaluationProductResult) -> list[EvaluationFieldResult]:
        return [
            cls._result(
                result, name, name, "MISSING", None,
                "No generated product record matched this source Mfg_Part_Num; rule compliance was not scored.",
                "HIGH",
            )
            for name, _ in METRICS
        ]

    @classmethod
    def _rule_checks(cls, result: EvaluationProductResult, product: ProductRecord) -> list[EvaluationFieldResult]:
        attributes = cls._attributes(product)
        all_values = [product.sku, product.name, product.description, product.manufacturer, product.category]
        all_values.extend(a.normalized_value or a.raw_value for a in product.attributes)
        technical = [a for a in product.attributes if a.unit]
        allowed_uoms = {item.strip().lower() for item in settings.evaluation_allowed_uoms.split(",") if item.strip()}
        recognized_sources = {"pdf", "csv", "website", "manufacturer_documentation", "manufacturer_website", "structured_catalog", "distributor"}

        manufacturer = cls._clean(product.manufacturer)
        brand = cls._attribute_value(attributes, "brand", "manufacturer brand", "unilog brand")
        required = [cls._clean(product.sku), cls._clean(product.name), manufacturer]
        title_terms = re.findall(r"[A-Za-z0-9]+", product.name or "")
        description = cls._clean(product.description)
        placeholder_values = [value for value in all_values if value and cls._is_placeholder(value)]
        bad_units = [a.unit for a in technical if (a.unit or "").strip().lower() not in allowed_uoms]
        duplicate_units = [
            a for a in product.attributes
            if a.raw_value and a.normalized_value
            and LLMExtractionService.normalize_value_for_comparison(a.raw_value, a.unit)
            != LLMExtractionService.normalize_value_for_comparison(a.normalized_value, a.unit)
        ]
        evidence_values = [a for a in product.attributes if cls._clean(a.normalized_value or a.raw_value)]
        evidence_ok = [
            a for a in evidence_values
            if a.evidence_chunk_id and a.source_type and (
                a.source_type.lower() != "pdf" or a.page_number is not None
            ) and (a.source_type.lower() != "website" or a.source_url)
        ]
        authority_values = [a for a in evidence_values if (a.source_type or "").lower() in recognized_sources]

        checks = [
            cls._result(result, "manufacturer", "manufacturer", "PASS" if manufacturer else "MISSING", manufacturer,
                        "Manufacturer is present and not a placeholder." if manufacturer else "Manufacturer is missing or placeholder.", "HIGH"),
            cls._result(result, "brand", "brand", "PASS" if brand else "MISSING", brand,
                        "Brand is present and not a placeholder." if brand else "No non-placeholder generated brand was found.", "MEDIUM"),
            cls._result(result, "uom", "uom", "SKIPPED" if not technical else ("PASS" if not bad_units else "FAIL"),
                        ", ".join(str(a.unit) for a in technical) or None,
                        "No unit-bearing generated attributes to evaluate." if not technical else ("All units satisfy the configured baseline list." if not bad_units else "Units outside the configured baseline list: " + ", ".join(map(str, bad_units))), "MEDIUM"),
            cls._result(result, "lov", "lov", "SKIPPED", None,
                        "No official controlled vocabulary was supplied with the raw-input dataset; LOV compliance is not scored.", "LOW"),
            cls._result(result, "required", "required", "PASS" if all(required) else "MISSING",
                        ", ".join(value for value in required if value) or None,
                        "SKU, product title, and manufacturer are present." if all(required) else "One or more baseline required fields are missing.", "HIGH"),
            cls._result(result, "character_limit", "character_limit", "PASS" if (len(product.name or "") <= settings.evaluation_title_max_length and len(product.description or "") <= settings.evaluation_description_max_length) else "FAIL",
                        product.name, f"Configured limits: title ≤ {settings.evaluation_title_max_length}, description ≤ {settings.evaluation_description_max_length} characters.", "MEDIUM"),
            cls._result(result, "placeholder", "placeholder", "PASS" if not placeholder_values else "FAIL", None,
                        "No placeholder values remain." if not placeholder_values else "Placeholder values remain in generated output.", "MEDIUM"),
            cls._result(result, "title_formula", "title_formula", "PASS" if len(title_terms) >= 2 else "FAIL", product.name,
                        "Baseline title rule requires at least two alphanumeric terms; no official title formula was supplied.", "LOW"),
            cls._result(result, "description_format", "description_format", "PASS" if description and len(description) >= 20 and "\n\n\n" not in (product.description or "") else "MISSING", description,
                        "Baseline description rule requires a non-placeholder description of at least 20 characters without excessive blank lines.", "LOW"),
            cls._result(result, "evidence", "evidence", "PASS" if evidence_values and len(evidence_ok) == len(evidence_values) else "FAIL", str(len(evidence_ok)),
                        f"{len(evidence_ok)}/{len(evidence_values)} populated attributes retain sufficient provenance.", "HIGH"),
            cls._result(result, "authority", "authority", "PASS" if evidence_values and len(authority_values) == len(evidence_values) else "FAIL", str(len(authority_values)),
                        f"{len(authority_values)}/{len(evidence_values)} populated attributes use recognized source types.", "MEDIUM"),
            cls._result(result, "normalization", "normalization", "PASS" if not duplicate_units else "FAIL", None,
                        "Normalized values are comparison-consistent." if not duplicate_units else "Raw and normalized comparison forms differ for one or more attributes.", "MEDIUM"),
        ]
        return checks

    @classmethod
    def _summarize(cls, run: EvaluationRun) -> dict[str, Any]:
        results = [field for product in run.products for field in product.fields]
        generated_products = [product for product in run.products if product.generated_product_id]
        metrics = []
        for key, label in METRICS:
            fields = [field for field in results if field.check_name == key and field.outcome != "SKIPPED" and field.generated_value is not None or field.check_name == key and field.outcome in {"PASS", "FAIL", "MISSING"}]
            # Missing generated records are intentionally not included in compliance denominators.
            fields = [field for field in fields if field.product_result.generated_product_id]
            passed = sum(field.outcome == "PASS" for field in fields)
            metrics.append({
                "name": key, "label": label, "passed": passed, "evaluated": len(fields),
                "compliance_percentage": round(passed * 100 / len(fields), 1) if fields else None,
                "unavailable_reason": "No official controlled vocabulary was supplied." if key == "lov" else ("No matched generated product records were available." if not fields else None),
            })
        all_scored = [field for field in results if field.product_result.generated_product_id and field.outcome in {"PASS", "FAIL", "MISSING"} and field.check_name != "lov"]
        passed = sum(field.outcome == "PASS" for field in all_scored)
        missing = sum(field.outcome == "MISSING" for field in all_scored)
        failures = [field for field in results if field.outcome in {"FAIL", "MISSING"}]
        return {
            "metrics": metrics,
            "overall_score": round(passed * 100 / len(all_scored), 1) if all_scored else None,
            "missing_attribute_rate": round(missing * 100 / len(all_scored), 1) if all_scored else None,
            "invalid_lov_values": 0,
            "invalid_uom_values": sum(field.check_name == "uom" and field.outcome == "FAIL" for field in results),
            "character_limit_violations": sum(field.check_name == "character_limit" and field.outcome == "FAIL" for field in results),
            "human_review_candidates": len({field.product_result_id for field in failures}),
            "products_with_generated_output": len(generated_products),
            "fields_evaluated": len(all_scored),
        }

    @classmethod
    def run_rule_quality(cls, db: Session) -> EvaluationRun:
        frame = cls._load_csv()
        run = EvaluationRun(mode="rule_quality", status="completed", dataset_path=str(cls._dataset_path()), products_processed=len(frame), ground_truth_available=0)
        db.add(run)
        db.flush()
        for index, row in frame.iterrows():
            raw = {column: str(row[column]) for column in RAW_INPUT_COLUMNS.values()}
            key = cls._clean(row[RAW_INPUT_COLUMNS["manufacturer_part_number"]])
            product = cls._product_for_key(db, key)
            result = EvaluationProductResult(
                run=run, input_row_number=int(index) + 2, input_product_key=key,
                source_description=cls._clean(row[RAW_INPUT_COLUMNS["source_description"]]),
                generated_product_id=product.id if product else None,
                status="passed" if product else "human_review",
                human_review_reason=None if product else "No generated product record matched Mfg_Part_Num.",
                input_snapshot=raw, generated_snapshot=cls._snapshot(product) if product else {},
            )
            db.add(result)
            db.flush()
            checks = cls._rule_checks(result, product) if product else cls._missing_output_checks(result)
            db.add_all(checks)
            if product:
                scored = [check for check in checks if check.outcome in {"PASS", "FAIL", "MISSING"} and check.check_name != "lov"]
                result.quality_score = round(100 * sum(check.outcome == "PASS" for check in scored) / len(scored), 1) if scored else None
        db.flush()
        db.refresh(run)
        run.summary_json = cls._summarize(run)
        run.products_with_generated_output = run.summary_json["products_with_generated_output"]
        run.fields_evaluated = run.summary_json["fields_evaluated"]
        run.overall_score = run.summary_json["overall_score"]
        db.commit()
        db.refresh(run)
        return run

    @classmethod
    def _expected_dataset(cls, db: Session) -> Optional[EvaluationExpectedDataset]:
        return db.query(EvaluationExpectedDataset).order_by(EvaluationExpectedDataset.uploaded_at.desc()).first()

    @classmethod
    def ground_truth_availability(cls, db: Session) -> GroundTruthAvailabilityResponse:
        expected = cls._expected_dataset(db)
        if not expected:
            return GroundTruthAvailabilityResponse(official_ground_truth_available=False, message="Official ground truth dataset not available.")
        return GroundTruthAvailabilityResponse(
            official_ground_truth_available=True,
            message="Official expected-output dataset is available for comparison.",
            expected_dataset_path=expected.file_path,
            file_name=expected.file_name,
            row_count=expected.row_count or 0,
            column_count=len(expected.columns_json or []),
            detected_columns=expected.columns_json or [],
            identifier_column=expected.identifier_column,
        )

    @classmethod
    def ground_truth_schema(cls, db: Session):
        from app.schemas.evaluation_schema import GroundTruthColumnProfile, GroundTruthSchemaProfileResponse
        expected = cls._expected_dataset(db)
        if not expected:
            return GroundTruthSchemaProfileResponse(official_ground_truth_available=False, message="Official ground truth dataset not available.")
        path = Path(expected.file_path)
        if not path.exists():
            raise EvaluationDomainError("Registered official expected-output dataset file is no longer available.", 404)
        frame = load_official_frame(path)
        profiles = profile_official_frame(frame)
        return GroundTruthSchemaProfileResponse(
            official_ground_truth_available=True,
            message="Schema profile is based only on observed headers and values in the uploaded official expected-output file; unknown meanings are not inferred.",
            file_name=expected.file_name,
            row_count=len(frame),
            column_count=len(frame.columns),
            identifier_column=expected.identifier_column,
            columns=[GroundTruthColumnProfile(**profile) for profile in profiles],
        )

    @classmethod
    def register_expected_dataset(cls, db: Session, uploaded_path: Path, file_name: str) -> EvaluationExpectedDataset:
        if uploaded_path.suffix.lower() not in {".csv", ".xlsx"}:
            raise EvaluationDomainError("Expected output must be a CSV or XLSX file.")
        try:
            frame = pd.read_csv(uploaded_path, dtype="string", keep_default_na=False) if uploaded_path.suffix.lower() == ".csv" else pd.read_excel(uploaded_path, dtype="string", keep_default_na=False)
        except Exception as error:
            raise EvaluationDomainError(f"Could not read expected output dataset: {error}") from error
        columns = [str(column) for column in frame.columns]
        identifier = identify_official_column(columns)
        if not identifier:
            raise EvaluationDomainError("Expected output requires an identifier column such as Mfg_Part_Num, MPN, SKU, or Product ID.")
        destination = cls._dataset_path().parent / "expected"
        destination.mkdir(parents=True, exist_ok=True)
        stored_path = destination / file_name
        shutil.copy2(uploaded_path, stored_path)
        dataset = EvaluationExpectedDataset(file_name=file_name, file_path=str(stored_path), identifier_column=identifier, columns_json=columns, row_count=len(frame))
        db.add(dataset)
        db.commit()
        db.refresh(dataset)
        return dataset

    @classmethod
    def latest_summary(cls, db: Session) -> EvaluationSummaryResponse:
        run = db.query(EvaluationRun).filter(EvaluationRun.mode == "rule_quality").order_by(EvaluationRun.created_at.desc()).first()
        availability = cls.ground_truth_availability(db)
        if not run:
            return EvaluationSummaryResponse(status="not_run", message="Rule-based Quality Evaluation has not been run yet.", official_ground_truth_available=availability.official_ground_truth_available)
        summary = run.summary_json or {}
        return EvaluationSummaryResponse(run_id=run.id, mode="rule_quality", status=run.status, message="Rule-based Quality Score is computed from transparent checks, not ground-truth accuracy.", official_ground_truth_available=availability.official_ground_truth_available, products_processed=run.products_processed, products_with_generated_output=run.products_with_generated_output, fields_evaluated=run.fields_evaluated, rule_based_quality_score=run.overall_score, ground_truth_accuracy=None, missing_attribute_rate=summary.get("missing_attribute_rate"), invalid_lov_values=summary.get("invalid_lov_values", 0), invalid_uom_values=summary.get("invalid_uom_values", 0), character_limit_violations=summary.get("character_limit_violations", 0), human_review_candidates=summary.get("human_review_candidates", 0), metrics=[FieldMetricResponse(**metric) for metric in summary.get("metrics", [])], generated_at=run.created_at)

    @classmethod
    def product_result(cls, db: Session, result_id: int) -> EvaluationProductResponse:
        result = db.query(EvaluationProductResult).options(joinedload(EvaluationProductResult.fields)).filter(EvaluationProductResult.id == result_id).first()
        if not result:
            raise EvaluationDomainError("Evaluation product result not found.", 404)
        return EvaluationProductResponse(id=result.id, run_id=result.run_id, input_row_number=result.input_row_number, input_product_key=result.input_product_key, source_description=result.source_description, generated_product_id=result.generated_product_id, status=result.status, quality_score=result.quality_score, human_review_reason=result.human_review_reason, input_snapshot=result.input_snapshot or {}, generated_snapshot=result.generated_snapshot or {}, fields=[EvaluationFieldResponse.model_validate(field) for field in result.fields])

    @classmethod
    def failures(cls, db: Session, run_id: Optional[int] = None) -> EvaluationFailuresResponse:
        if run_id is None:
            latest = db.query(EvaluationRun).filter(EvaluationRun.mode == "rule_quality").order_by(EvaluationRun.created_at.desc()).first()
            if not latest:
                return EvaluationFailuresResponse()
            run_id = latest.id
        fields = (db.query(EvaluationFieldResult).join(EvaluationProductResult).filter(EvaluationProductResult.run_id == run_id, EvaluationFieldResult.outcome.in_(["FAIL", "MISSING"])).order_by(EvaluationProductResult.input_row_number, EvaluationFieldResult.id).all())
        return EvaluationFailuresResponse(run_id=run_id, total_failures=len(fields), failures=[EvaluationFailureResponse(product_result_id=field.product_result_id, input_row_number=field.product_result.input_row_number, input_product_key=field.product_result.input_product_key, generated_product_id=field.product_result.generated_product_id, status=field.product_result.status, field=EvaluationFieldResponse.model_validate(field)) for field in fields])

    @classmethod
    def ground_truth_comparison(cls, db: Session, product_id: int) -> GroundTruthComparisonResponse:
        expected = cls._expected_dataset(db)
        if not expected:
            return GroundTruthComparisonResponse(official_ground_truth_available=False, message="Official ground truth dataset not available.")
        product = db.query(ProductRecord).options(joinedload(ProductRecord.attributes)).filter(ProductRecord.id == product_id).first()
        if not product:
            raise EvaluationDomainError("Generated product not found.", 404)
        path = Path(expected.file_path)
        frame = pd.read_csv(path, dtype="string", keep_default_na=False) if path.suffix.lower() == ".csv" else pd.read_excel(path, dtype="string", keep_default_na=False)
        rows = frame[frame[expected.identifier_column].astype(str).str.strip() == (product.sku or "")]
        if rows.empty:
            return GroundTruthComparisonResponse(official_ground_truth_available=True, message="No expected-output row matched this generated product identifier.")
        generated = cls._snapshot(product)
        attrs = cls._attributes(product)
        comparisons = []
        for column, value in rows.iloc[0].items():
            if column == expected.identifier_column:
                continue
            expected_value = cls._clean(value)
            normalized = cls._normalized_name(column)
            generated_value = generated.get("name") if normalized in {"title", "product title", "product name", "name"} else generated.get("description") if normalized == "description" else generated.get("manufacturer") if normalized in {"manufacturer", "manufacturer name"} else generated.get("category") if normalized == "category" else cls._attribute_value(attrs, column)
            if expected_value is None and cls._clean(generated_value) is None:
                outcome = "EXACT_MATCH"
            elif expected_value is None or cls._clean(generated_value) is None:
                outcome = "MISSING"
            elif expected_value == generated_value:
                outcome = "EXACT_MATCH"
            elif LLMExtractionService.normalize_value_for_comparison(expected_value) == LLMExtractionService.normalize_value_for_comparison(generated_value):
                outcome = "NORMALIZED_MATCH"
            else:
                expected_tokens = set(cls._normalized_name(expected_value).split())
                generated_tokens = set(cls._normalized_name(generated_value or "").split())
                outcome = "PARTIAL_MATCH" if expected_tokens and len(expected_tokens & generated_tokens) / len(expected_tokens | generated_tokens) >= 0.6 else "INCORRECT"
            comparisons.append(GroundTruthComparisonRow(field_name=str(column), expected_value=expected_value, generated_value=generated_value, result=outcome))
        return GroundTruthComparisonResponse(official_ground_truth_available=True, message="Comparison uses the uploaded official expected-output row.", rows=comparisons)

    @classmethod
    def run_ground_truth(cls, db: Session) -> EvaluationRun:
        """Compare stored generated records only against an uploaded official expected dataset."""
        expected = cls._expected_dataset(db)
        if not expected:
            raise EvaluationDomainError("Official ground truth dataset not available.", 409)
        path = Path(expected.file_path)
        if not path.exists():
            raise EvaluationDomainError("Registered official expected-output dataset file is no longer available.", 404)
        frame = pd.read_csv(path, dtype="string", keep_default_na=False) if path.suffix.lower() == ".csv" else pd.read_excel(path, dtype="string", keep_default_na=False)
        run = EvaluationRun(mode="ground_truth", status="completed", dataset_path=str(cls._dataset_path()), expected_dataset_path=str(path), ground_truth_available=1, products_processed=len(frame))
        db.add(run)
        db.flush()
        match_outcomes = {"EXACT_MATCH", "NORMALIZED_MATCH"}
        for index, row in frame.iterrows():
            key = cls._clean(row[expected.identifier_column])
            product = cls._product_for_key(db, key)
            result = EvaluationProductResult(
                run=run,
                input_row_number=int(index) + 2,
                input_product_key=key,
                source_description=None,
                generated_product_id=product.id if product else None,
                status="passed" if product else "human_review",
                quality_score=None,
                human_review_reason=None if product else "No generated product record matched the official expected-output identifier.",
                input_snapshot={expected.identifier_column: key},
                generated_snapshot=cls._snapshot(product) if product else {},
            )
            db.add(result)
            db.flush()
            attrs = cls._attributes(product) if product else {}
            field_results = []
            for column, raw_expected in row.items():
                if column == expected.identifier_column:
                    continue
                expected_value = cls._clean(raw_expected)
                normalized_column = cls._normalized_name(str(column))
                if not product:
                    generated_value = None
                elif normalized_column in {"title", "product title", "product name", "name"}:
                    generated_value = product.name
                elif normalized_column == "description":
                    generated_value = product.description
                elif normalized_column in {"manufacturer", "manufacturer name"}:
                    generated_value = product.manufacturer
                elif normalized_column == "category":
                    generated_value = product.category
                else:
                    generated_value = cls._attribute_value(attrs, str(column))
                normalized_expected = LLMExtractionService.normalize_value_for_comparison(expected_value) if expected_value else None
                normalized_generated = LLMExtractionService.normalize_value_for_comparison(generated_value) if generated_value else None
                if expected_value is None and cls._clean(generated_value) is None:
                    outcome = "EXACT_MATCH"
                elif expected_value is None or cls._clean(generated_value) is None:
                    outcome = "MISSING"
                elif expected_value == generated_value:
                    outcome = "EXACT_MATCH"
                elif normalized_expected == normalized_generated:
                    outcome = "NORMALIZED_MATCH"
                else:
                    expected_tokens = set((normalized_expected or "").split())
                    generated_tokens = set((normalized_generated or "").split())
                    outcome = "PARTIAL_MATCH" if expected_tokens and len(expected_tokens & generated_tokens) / len(expected_tokens | generated_tokens) >= 0.6 else "INCORRECT"
                field_results.append(cls._result(
                    result, str(column), "ground_truth_comparison", outcome, generated_value,
                    "Official expected-output comparison.", "HIGH" if outcome in {"MISSING", "INCORRECT"} else "LOW",
                    expected=expected_value, normalized_expected=normalized_expected,
                    normalized_generated=normalized_generated,
                ))
            db.add_all(field_results)
            scored = [field for field in field_results if field.expected_value is not None]
            result.quality_score = round(100 * sum(field.outcome in match_outcomes for field in scored) / len(scored), 1) if scored else None
        db.flush()
        db.refresh(run)
        fields = [field for product_result in run.products for field in product_result.fields if field.expected_value is not None]
        exact = sum(field.outcome == "EXACT_MATCH" for field in fields)
        normalized = sum(field.outcome == "NORMALIZED_MATCH" for field in fields)
        partial = sum(field.outcome == "PARTIAL_MATCH" for field in fields)
        missing = sum(field.outcome == "MISSING" for field in fields)
        incorrect = sum(field.outcome == "INCORRECT" for field in fields)
        accuracy = round((exact + normalized) * 100 / len(fields), 1) if fields else None
        run.products_with_generated_output = sum(product.generated_product_id is not None for product in run.products)
        run.fields_evaluated = len(fields)
        run.overall_score = accuracy
        generated_products = db.query(ProductRecord).options(joinedload(ProductRecord.attributes)).all()
        aggregate = official_aggregate(frame, generated_products, expected.identifier_column)
        # The official comparator is the authoritative metric surface. It excludes
        # unsupported/unknown delivery-format columns from accuracy denominators.
        official_accuracy = aggregate.get("overall_match_rate")
        run.products_with_generated_output = aggregate.get("products_matched", 0)
        run.fields_evaluated = aggregate.get("comparable_fields", 0)
        run.overall_score = official_accuracy
        run.summary_json = {
            "ground_truth_accuracy": official_accuracy,
            "exact_matches": aggregate.get("exact_matches", 0),
            "normalized_matches": aggregate.get("normalized_matches", 0),
            "partial_matches": aggregate.get("partial_matches", 0),
            "missing": aggregate.get("missing_values", 0),
            "incorrect": aggregate.get("incorrect_values", 0),
            "aggregate": aggregate,
            "metrics": [{
                "name": "ground_truth_accuracy",
                "label": "Ground-Truth Accuracy",
                "passed": aggregate.get("exact_matches", 0) + aggregate.get("normalized_matches", 0),
                "evaluated": aggregate.get("comparable_fields", 0),
                "compliance_percentage": official_accuracy,
                "unavailable_reason": None,
            }],
        }
        db.commit()
        db.refresh(run)
        return run

    @classmethod
    def ground_truth_summary(cls, db: Session) -> EvaluationSummaryResponse:
        availability = cls.ground_truth_availability(db)
        if not availability.official_ground_truth_available:
            return EvaluationSummaryResponse(mode="ground_truth", status="unavailable", message="Official ground truth dataset not available.", official_ground_truth_available=False)
        run = db.query(EvaluationRun).filter(EvaluationRun.mode == "ground_truth").order_by(EvaluationRun.created_at.desc()).first()
        if not run:
            return EvaluationSummaryResponse(mode="ground_truth", status="not_run", message="Official expected-output dataset is available; run Ground-Truth Evaluation to calculate accuracy.", official_ground_truth_available=True)
        summary = run.summary_json or {}
        from app.schemas.evaluation_schema import GroundTruthAggregateResponse
        aggregate = summary.get("aggregate")
        return EvaluationSummaryResponse(
            run_id=run.id,
            mode="ground_truth",
            status=run.status,
            message="Ground-Truth Accuracy is calculated only against the uploaded official expected-output dataset. Unsupported and unknown delivery-format columns are excluded from accuracy denominators and reported separately.",
            official_ground_truth_available=True,
            products_processed=run.products_processed,
            products_with_generated_output=run.products_with_generated_output,
            fields_evaluated=run.fields_evaluated,
            rule_based_quality_score=None,
            ground_truth_accuracy=summary.get("ground_truth_accuracy"),
            metrics=[FieldMetricResponse(**metric) for metric in summary.get("metrics", [])],
            ground_truth=GroundTruthAggregateResponse(**aggregate) if aggregate else None,
            generated_at=run.created_at,
        )
