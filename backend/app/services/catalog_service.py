"""Phase 9 catalog processing built on the existing source-backed services."""
from __future__ import annotations

import csv
import io
import json
import shutil
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd
from openpyxl import Workbook
from sqlalchemy.orm import Session, joinedload

from app.database import SessionLocal
from app.models.catalog import CatalogBatch, CatalogItem
from app.models.commerce_output import CommerceOutput
from app.models.conflict import DataConflict, EvidenceChunk
from app.models.enrichment import EnrichmentRun
from app.models.ingestion import IngestionJob, RawDocumentSource
from app.models.product import ProductAttribute, ProductRecord
from app.services.commerce_output_service import CommerceOutputService
from app.services.enrichment.pipeline import EnrichmentPipeline
from app.services.reference_data_service import comparison_value


STATUS_VALUES = {"QUEUED", "PROCESSING", "PAUSED", "COMPLETED", "FAILED", "CANCELLED"}
IDENTIFIER_ALIASES = {"sku", "mpn", "mfg part num", "mfg part number", "manufacturer part number", "part number", "part num", "product id", "product identifier", "item number", "item no", "part id", "catalog number", "catalog no", "identifier"}
DESCRIPTION_ALIASES = {"description", "part desc", "part description", "product description", "product name", "name", "title"}
MANUFACTURER_ALIASES = {"manufacturer", "part manuf", "part manufacturer", "mfg", "mfg name", "manufacturer name", "maker", "vendor"}
BRAND_ALIASES = {"brand", "e1 brand", "unilog brand", "dib brand", "brand name"}
PLACEHOLDER_VALUES = {"", "--", "n/a", "na", "none", "null", "unknown", "-- unbranded --", "-- no unilog brand --", "-- no dib brand --"}


class CatalogDomainError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _normalized_name(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().replace("_", " ").replace("-", " ").split())


def _clean(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return None if text.lower() in PLACEHOLDER_VALUES else text


def _read_frame(path: Path) -> pd.DataFrame:
    try:
        suffix = path.suffix.lower()
        if suffix == ".csv":
            return pd.read_csv(path, dtype="string", keep_default_na=False, on_bad_lines="error")
        if suffix == ".xlsx":
            return pd.read_excel(path, dtype="string", keep_default_na=False)
    except Exception as exc:
        raise CatalogDomainError(f"Could not parse catalog file: {exc}") from exc
    raise CatalogDomainError("Catalog must be a CSV or XLSX file.")


def _column(columns: list[str], aliases: set[str]) -> Optional[str]:
    normalized = {_normalized_name(column): column for column in columns}
    for alias in aliases:
        if alias in normalized:
            return normalized[alias]
    return None


class CatalogService:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _now() -> datetime:
        return datetime.utcnow()

    def create_batch(self, uploaded_path: Path, filename: str, dataset_name: Optional[str] = None) -> CatalogBatch:
        frame = _read_frame(uploaded_path)
        columns = [str(column) for column in frame.columns]
        if not columns:
            raise CatalogDomainError("Catalog contains no columns.")
        id_column = _column(columns, IDENTIFIER_ALIASES)
        description_column = _column(columns, DESCRIPTION_ALIASES)
        manufacturer_column = _column(columns, MANUFACTURER_ALIASES)
        brand_column = _column(columns, BRAND_ALIASES)
        if not id_column:
            raise CatalogDomainError("Catalog requires a product identifier column such as Mfg_Part_Num, MPN, SKU, or Product ID.")
        if not description_column:
            raise CatalogDomainError("Catalog requires a description column such as Part_Desc, Description, Product Name, or Title.")

        destination = Path("/home/ubuntu/ai-product-intelligence/backend/data/catalog_batches")
        destination.mkdir(parents=True, exist_ok=True)
        # Use a temporary unique name until the database id exists, then retain the original filename in metadata.
        staged_path = destination / f"pending_{datetime.utcnow().timestamp()}_{filename}"
        shutil.copy2(uploaded_path, staged_path)
        batch = CatalogBatch(
            dataset_name=dataset_name or filename,
            file_name=filename,
            file_path=str(staged_path),
            source_type=Path(filename).suffix.lower().lstrip("."),
            detected_columns=columns,
            status="QUEUED",
            configuration_snapshot={"identifier_column": id_column, "description_column": description_column, "manufacturer_column": manufacturer_column, "brand_column": brand_column, "required_input_fields": [id_column, description_column, manufacturer_column] if manufacturer_column else [id_column, description_column]},
        )
        self.db.add(batch)
        self.db.flush()

        raw_records = frame.fillna("").to_dict(orient="records")
        identifiers = [str(row.get(id_column, "")).strip() for row in raw_records]
        duplicate_counts = Counter(value.casefold() for value in identifiers if value)
        duplicate_values = sorted({value for value in identifiers if value and duplicate_counts[value.casefold()] > 1})
        missing_counts: Counter[str] = Counter()
        failure_counts: Counter[str] = Counter()
        warnings_by_row: dict[str, list[str]] = {}
        invalid_count = 0
        for index, raw_row in enumerate(raw_records):
            snapshot = {str(key): (None if value is None else str(value)) for key, value in raw_row.items()}
            row_number = index + 2
            errors: list[str] = []
            warnings: list[str] = []
            identifier = str(raw_row.get(id_column, "")).strip()
            if not _clean(identifier):
                errors.append(f"Missing required product identifier: {id_column}")
                missing_counts[id_column] += 1
            elif duplicate_counts[identifier.casefold()] > 1:
                errors.append("Duplicate product identifier in catalog.")
            if not _clean(raw_row.get(description_column)):
                errors.append(f"Missing required description: {description_column}")
                missing_counts[description_column] += 1
            if manufacturer_column and not _clean(raw_row.get(manufacturer_column)):
                errors.append(f"Missing manufacturer: {manufacturer_column}")
                missing_counts[manufacturer_column] += 1
            if brand_column and not _clean(raw_row.get(brand_column)):
                warnings.append(f"Brand value is missing or a placeholder: {brand_column}")
            if identifier and len(identifier) > 255:
                warnings.append("Identifier exceeds the storage display length; original value is retained in input_snapshot.")
            if warnings:
                warnings_by_row[str(row_number)] = warnings
            if errors:
                invalid_count += 1
                if any("product identifier" in error for error in errors):
                    failure_counts[id_column] += 1
                if any("description" in error for error in errors):
                    failure_counts[description_column] += 1
                if manufacturer_column and any("manufacturer" in error for error in errors):
                    failure_counts[manufacturer_column] += 1
                if any("Duplicate product identifier" in error for error in errors):
                    failure_counts["duplicate_identifier"] += 1
            item = CatalogItem(
                batch_id=batch.id,
                row_number=row_number,
                identifier=identifier or None,
                input_snapshot=snapshot,
                validation_status="INVALID" if errors else "VALID",
                validation_errors=errors,
                validation_warnings=warnings,
                processing_status="INVALID" if errors else "QUEUED",
            )
            self.db.add(item)
        batch.total_items = len(raw_records)
        batch.invalid_items = invalid_count
        batch.queued_items = len(raw_records) - invalid_count
        batch.error_summary = {"duplicate_identifiers": duplicate_values, "missing_required_fields": dict(missing_counts), "validation_failures_by_field": dict(failure_counts), "warnings_by_row": warnings_by_row}
        batch.configuration_snapshot = {**(batch.configuration_snapshot or {}), "validation": {"valid_rows": batch.queued_items, "invalid_rows": batch.invalid_items}}
        self.db.commit()
        self.db.refresh(batch)
        return batch

    @staticmethod
    def upload_summary(batch: CatalogBatch) -> dict[str, Any]:
        summary = batch.error_summary or {}
        warning_rows = summary.get("warnings_by_row") or {}
        warnings = [message for row_messages in warning_rows.values() for message in row_messages]
        return {"batch_id": batch.id, "dataset_name": batch.dataset_name, "filename": batch.file_name, "source_type": batch.source_type, "total_rows": batch.total_items, "detected_columns": batch.detected_columns or [], "valid_rows": batch.queued_items, "invalid_rows": batch.invalid_items, "duplicate_identifiers": summary.get("duplicate_identifiers", []), "missing_required_fields": summary.get("missing_required_fields", {}), "validation_failures_by_field": summary.get("validation_failures_by_field", {}), "validation_warnings": warnings[:20], "status": batch.status, "warnings_by_row": warning_rows}

    def _create_source_backed_product(self, batch: CatalogBatch, item: CatalogItem) -> ProductRecord:
        row = item.input_snapshot
        identifier = (item.identifier or "").strip()
        existing = self.db.query(ProductRecord).filter(
            ProductRecord.sku == identifier,
            ProductRecord.sku_source_identifier == batch.file_name,
            ProductRecord.sku_row_number == item.row_number,
        ).first()
        if existing:
            # The row was already materialized from this exact source location. Reuse it
            # without importing unrelated products or creating a duplicate SKU record.
            return existing
        collision = self.db.query(ProductRecord).filter(ProductRecord.sku == identifier).first()
        if collision:
            raise CatalogDomainError(f"Product identifier already exists outside this catalog item: {identifier}", 409)
        id_column = (batch.configuration_snapshot or {}).get("identifier_column")
        description_column = (batch.configuration_snapshot or {}).get("description_column")
        manufacturer_column = (batch.configuration_snapshot or {}).get("manufacturer_column")
        name = _clean(row.get(description_column)) if description_column else None
        manufacturer = _clean(row.get(manufacturer_column)) if manufacturer_column else None
        job = IngestionJob(job_name=f"Catalog batch {batch.id} row {item.row_number}", status="processing", source_type="csv")
        self.db.add(job)
        self.db.flush()
        raw_text = "\n".join(f"{key}: {value}" for key, value in row.items())
        source = RawDocumentSource(job_id=job.id, file_name=batch.file_name, raw_text_content=raw_text)
        self.db.add(source)
        self.db.flush()
        product = ProductRecord(sku=identifier, name=name, description=name, manufacturer=manufacturer, status="draft", sku_evidence_chunk_id=f"catalog-{batch.id}-{item.row_number}", sku_source_type="csv", sku_source_identifier=batch.file_name, sku_row_number=item.row_number)
        self.db.add(product)
        self.db.flush()
        for column, raw_value in row.items():
            text_value = None if raw_value is None else str(raw_value)
            if not _clean(text_value):
                continue
            attribute = ProductAttribute(product_id=product.id, attribute_name=str(column), raw_value=text_value, normalized_value=text_value, confidence_score=0.99, source_type="csv", source_identifier=batch.file_name, row_number=item.row_number, evidence_chunk_id=f"catalog-{batch.id}-{item.row_number}-{_normalized_name(column).replace(' ', '-')}")
            self.db.add(attribute)
            self.db.flush()
            self.db.add(EvidenceChunk(job_id=job.id, source_id=source.id, attribute_id=attribute.id, stable_chunk_id=attribute.evidence_chunk_id, snippet_text=f"{column}: {text_value}", source_type="csv", source_identifier=batch.file_name, row_number=item.row_number))
        job.status = "completed"
        self.db.flush()
        return product

    def process_item(self, batch: CatalogBatch, item: CatalogItem, *, mode: str = "SOURCE_ONLY", use_llm: bool = False) -> None:
        item.attempt_count += 1
        item.processing_status = "PROCESSING"
        item.started_at = self._now()
        item.error_message = None
        self.db.flush()
        try:
            product = self._create_source_backed_product(batch, item)
            run = EnrichmentPipeline(self.db).analyze(product.id, use_llm=use_llm, mode=mode)
            commerce = CommerceOutputService(self.db).generate(product.id, run.id)
            item.product_id = product.id
            item.enrichment_run_id = run.id
            item.commerce_output_id = commerce.id
            item.result_status = run.product_status or commerce.status
            item.processing_status = "COMPLETED"
            item.completed_at = self._now()
        except Exception as exc:
            self.db.rollback()
            # Re-load the item after rollback because SQLAlchemy expires transactional state.
            item = self.db.query(CatalogItem).filter(CatalogItem.id == item.id).one()
            item.processing_status = "FAILED"
            item.error_message = str(exc)
            item.completed_at = self._now()
        self.db.commit()

    def process_batch(self, batch_id: int, *, mode: str = "SOURCE_ONLY", use_llm: bool = False, item_ids: Optional[list[int]] = None) -> CatalogBatch:
        batch = self.db.query(CatalogBatch).filter(CatalogBatch.id == batch_id).first()
        if not batch:
            raise CatalogDomainError("Catalog batch not found.", 404)
        if batch.status == "CANCELLED" and not item_ids:
            raise CatalogDomainError("Cancelled batches must be restarted explicitly through retry.", 409)
        batch.status = "PROCESSING"
        batch.started_at = batch.started_at or self._now()
        batch.cancellation_requested = False
        batch.configuration_snapshot = {**(batch.configuration_snapshot or {}), "processing": {"mode": mode, "use_llm": use_llm}}
        self.db.commit()
        query = self.db.query(CatalogItem).filter(CatalogItem.batch_id == batch_id, CatalogItem.validation_status == "VALID", CatalogItem.processing_status.in_(["QUEUED", "FAILED"]))
        if item_ids:
            query = query.filter(CatalogItem.id.in_(item_ids))
        for item in query.order_by(CatalogItem.row_number.asc()).all():
            batch = self.db.query(CatalogBatch).filter(CatalogBatch.id == batch_id).one()
            if batch.cancellation_requested:
                batch.status = "CANCELLED"
                self.db.commit()
                break
            self.process_item(batch, item, mode=mode, use_llm=use_llm)
            self.recalculate(batch_id)
        batch = self.recalculate(batch_id)
        if batch.status != "CANCELLED":
            batch.status = "FAILED" if batch.failed_items and batch.processed_items >= batch.queued_items else "COMPLETED" if batch.processed_items >= batch.queued_items else "PROCESSING"
            batch.completed_at = self._now() if batch.status in {"FAILED", "COMPLETED"} else None
            self.db.commit()
            self.db.refresh(batch)
        return batch

    def recalculate(self, batch_id: int) -> CatalogBatch:
        batch = self.db.query(CatalogBatch).filter(CatalogBatch.id == batch_id).one()
        items = self.db.query(CatalogItem).filter(CatalogItem.batch_id == batch_id).all()
        batch.processed_items = sum(item.processing_status in {"COMPLETED", "FAILED"} for item in items)
        batch.successful_items = sum(item.processing_status == "COMPLETED" for item in items)
        batch.failed_items = sum(item.processing_status == "FAILED" for item in items)
        batch.review_items = sum(item.processing_status == "COMPLETED" and item.result_status != "READY" for item in items)
        batch.queued_items = sum(item.processing_status == "QUEUED" for item in items if item.validation_status == "VALID")
        batch.invalid_items = sum(item.validation_status == "INVALID" for item in items)
        self.db.flush()
        return batch

    def start(self, batch_id: int, *, mode: str, use_llm: bool) -> CatalogBatch:
        batch = self.db.query(CatalogBatch).filter(CatalogBatch.id == batch_id).first()
        if not batch:
            raise CatalogDomainError("Catalog batch not found.", 404)
        if batch.status == "PROCESSING":
            return batch
        batch.status = "PROCESSING"
        batch.started_at = batch.started_at or self._now()
        batch.configuration_snapshot = {**(batch.configuration_snapshot or {}), "processing": {"mode": mode, "use_llm": use_llm}}
        self.db.commit()
        return batch

    def cancel(self, batch_id: int) -> CatalogBatch:
        batch = self.db.query(CatalogBatch).filter(CatalogBatch.id == batch_id).first()
        if not batch:
            raise CatalogDomainError("Catalog batch not found.", 404)
        batch.cancellation_requested = True
        if batch.status == "QUEUED":
            batch.status = "CANCELLED"
        elif batch.status == "PROCESSING":
            # The bounded worker observes this flag after its current item and persists CANCELLED.
            batch.status = "PAUSED"
        self.db.commit()
        self.db.refresh(batch)
        return batch

    def retry(self, batch_id: int, item_ids: Optional[list[int]] = None) -> CatalogBatch:
        batch = self.db.query(CatalogBatch).filter(CatalogBatch.id == batch_id).first()
        if not batch:
            raise CatalogDomainError("Catalog batch not found.", 404)
        query = self.db.query(CatalogItem).filter(CatalogItem.batch_id == batch_id, CatalogItem.processing_status == "FAILED")
        if item_ids:
            query = query.filter(CatalogItem.id.in_(item_ids))
        for item in query.all():
            item.processing_status = "QUEUED"
            item.error_message = None
        batch.status = "QUEUED"
        batch.cancellation_requested = False
        self.recalculate(batch_id)
        self.db.commit()
        return batch

    @staticmethod
    def status_payload(batch: CatalogBatch) -> dict[str, Any]:
        progress = round((batch.processed_items / batch.total_items) * 100, 1) if batch.total_items else 0.0
        return {"batch_id": batch.id, "dataset_name": batch.dataset_name, "filename": batch.file_name, "source_type": batch.source_type, "status": batch.status, "total_items": batch.total_items, "queued_items": batch.queued_items, "processed_items": batch.processed_items, "successful_items": batch.successful_items, "review_items": batch.review_items, "failed_items": batch.failed_items, "invalid_items": batch.invalid_items, "progress_percentage": progress, "started_at": batch.started_at, "completed_at": batch.completed_at, "error_summary": batch.error_summary or {}, "configuration_snapshot": batch.configuration_snapshot or {}}

    def _item_payload(self, item: CatalogItem) -> dict[str, Any]:
        product = item.product
        run = item.enrichment_run
        evidence_available = bool(run and run.evidence_count)
        conflicts = self.db.query(DataConflict).filter(DataConflict.product_id == item.product_id).count() if item.product_id else 0
        return {"id": item.id, "batch_id": item.batch_id, "row_number": item.row_number, "identifier": item.identifier, "input_snapshot": item.input_snapshot or {}, "validation_status": item.validation_status, "validation_errors": item.validation_errors or [], "validation_warnings": item.validation_warnings or [], "processing_status": item.processing_status, "error_message": item.error_message, "product_id": item.product_id, "enrichment_run_id": item.enrichment_run_id, "commerce_output_id": item.commerce_output_id, "result_status": item.result_status, "attempt_count": item.attempt_count, "evidence_available": evidence_available, "conflict_count": conflicts, "review_required": item.result_status not in {None, "READY"}, "confidence": run.overall_confidence if run else None, "product_name": product.name if product else None, "manufacturer": product.manufacturer if product else None, "brand": None}

    def results(self, batch_id: int, page: int = 1, page_size: int = 50, status: Optional[str] = None, search: Optional[str] = None) -> dict[str, Any]:
        query = self.db.query(CatalogItem).filter(CatalogItem.batch_id == batch_id)
        if status and status != "all":
            if status == "failed":
                query = query.filter(CatalogItem.processing_status == "FAILED")
            elif status == "review_required":
                query = query.filter(CatalogItem.processing_status == "COMPLETED", CatalogItem.result_status != "READY")
            elif status == "ready":
                query = query.filter(CatalogItem.result_status == "READY")
        rows = query.order_by(CatalogItem.row_number.asc()).all()
        payload = [self._item_payload(item) for item in rows]
        if search:
            term = search.casefold()
            payload = [item for item in payload if term in json.dumps(item, default=str).casefold()]
        total = len(payload)
        start = max(page - 1, 0) * page_size
        return {"batch_id": batch_id, "total": total, "page": page, "page_size": page_size, "items": payload[start:start + page_size]}

    def aggregation(self, batch_id: int) -> dict[str, Any]:
        batch = self.db.query(CatalogBatch).filter(CatalogBatch.id == batch_id).first()
        if not batch:
            raise CatalogDomainError("Catalog batch not found.", 404)
        items = self.db.query(CatalogItem).filter(CatalogItem.batch_id == batch_id).all()
        completed = [item for item in items if item.processing_status == "COMPLETED"]
        runs = [item.enrichment_run for item in completed if item.enrichment_run]
        products = [item.product for item in completed if item.product]
        ready = sum(item.result_status == "READY" for item in completed)
        insufficient = sum(item.result_status == "INSUFFICIENT_DATA" for item in completed)
        conflicts = sum(self.db.query(DataConflict).filter(DataConflict.product_id == item.product_id).count() > 0 for item in completed if item.product_id)
        evidence = sum(bool(run.evidence_count) for run in runs)
        durations = [(run.completed_at - run.started_at).total_seconds() for run in runs if run.started_at and run.completed_at]
        with_reference = 0
        compliant_reference = 0
        quality_scores: list[float] = []
        for item in completed:
            output = item.commerce_output
            validation = output.validation_summary if output else {}
            if output and validation.get("reference_data_unavailable_fields", 0) == 0:
                with_reference += 1
                if validation.get("invalid_reference_fields", 0) == 0:
                    compliant_reference += 1
        metrics = {"processing_success_rate": round(batch.successful_items * 100 / batch.total_items, 1) if batch.total_items else None, "completeness": round((ready + (len(completed) - insufficient - ready)) * 100 / len(completed), 1) if completed else None, "evidence_coverage": round(evidence * 100 / len(completed), 1) if completed else None, "reference_data_compliance": round(compliant_reference * 100 / with_reference, 1) if with_reference else None, "conflict_rate": round(conflicts * 100 / len(completed), 1) if completed else None, "human_review_rate": round(batch.review_items * 100 / batch.total_items, 1) if batch.total_items else None, "rule_based_quality_score": round(sum(quality_scores) / len(quality_scores), 1) if quality_scores else None, "ground_truth_accuracy": "UNAVAILABLE"}
        progress = round(batch.processed_items * 100 / batch.total_items, 1) if batch.total_items else 0.0
        return {"batch_id": batch.id, "status": batch.status, "total_products": batch.total_items, "processed": batch.processed_items, "ready": ready, "review_required": batch.review_items, "insufficient_data": insufficient, "failed": batch.failed_items, "conflicts": conflicts, "progress_percentage": progress, "average_processing_time_seconds": round(sum(durations) / len(durations), 2) if durations else None, "metrics": metrics, "ground_truth_message": "Official ground truth dataset not available."}

    def review_queue(self, batch_id: int) -> dict[str, Any]:
        items = self.db.query(CatalogItem).filter(CatalogItem.batch_id == batch_id, CatalogItem.processing_status == "COMPLETED", CatalogItem.result_status != "READY").order_by(CatalogItem.row_number.asc()).all()
        results: list[dict[str, Any]] = []
        for item in items:
            conflicts = self.db.query(DataConflict).filter(DataConflict.product_id == item.product_id).all() if item.product_id else []
            run = item.enrichment_run
            reasons = list(run.missing_attributes or []) if run else []
            reasons.extend(conflict.attribute_name for conflict in conflicts)
            severity = "CRITICAL" if any(conflict.severity == "CRITICAL" for conflict in conflicts) else "HIGH" if conflicts else "MEDIUM"
            results.append({"item_id": item.id, "product_id": item.product_id, "row_number": item.row_number, "identifier": item.identifier, "product_name": item.product.name if item.product else None, "issue": "; ".join(reasons) or (item.result_status or "Review required"), "severity": severity, "status": item.result_status or "REVIEW_REQUIRED", "reason": "; ".join(reasons) or "The source-backed product did not reach READY status.", "evidence_available": bool(run and run.evidence_count)})
        return {"batch_id": batch_id, "total": len(results), "items": results}

    def export_rows(self, batch_id: int, filter_name: str = "all") -> list[dict[str, Any]]:
        data = self.results(batch_id, page=1, page_size=100000, status=filter_name)
        rows: list[dict[str, Any]] = []
        for item in data["items"]:
            output = self.db.query(CommerceOutput).filter(CommerceOutput.id == item["commerce_output_id"]).first() if item.get("commerce_output_id") else None
            record = (output.record_snapshot or {}).get("record", {}) if output else {}
            rows.append({"batch_id": batch_id, "row_number": item["row_number"], "identifier": item["identifier"], "product_id": item["product_id"], "product_name": item["product_name"], "manufacturer": item["manufacturer"], "status": item["result_status"] or item["processing_status"], "confidence": item["confidence"], "evidence_available": item["evidence_available"], "conflict_count": item["conflict_count"], "review_required": item["review_required"], "commerce_output_available": bool(output), "record": json.dumps(record, default=str), "input_snapshot": json.dumps(item["input_snapshot"], default=str)})
        return rows

    def export(self, batch_id: int, fmt: str, filter_name: str = "all") -> tuple[bytes, str, str]:
        rows = self.export_rows(batch_id, filter_name)
        if fmt == "json":
            return json.dumps(rows, indent=2, default=str).encode("utf-8"), "application/json", f"catalog-batch-{batch_id}-{filter_name}.json"
        headers = list(rows[0].keys()) if rows else ["batch_id", "row_number", "identifier", "status"]
        if fmt == "csv":
            stream = io.StringIO()
            writer = csv.DictWriter(stream, fieldnames=headers)
            writer.writeheader(); writer.writerows(rows)
            return stream.getvalue().encode("utf-8"), "text/csv", f"catalog-batch-{batch_id}-{filter_name}.csv"
        workbook = Workbook()
        sheet = workbook.active; sheet.title = "Catalog Results"; sheet.append(headers)
        for row in rows: sheet.append([row.get(header) for header in headers])
        summary = self.aggregation(batch_id)
        metrics_sheet = workbook.create_sheet("Summary"); metrics_sheet.append(["key", "value"])
        for key, value in summary.items(): metrics_sheet.append([key, json.dumps(value, default=str) if isinstance(value, (dict, list)) else value])
        stream = io.BytesIO(); workbook.save(stream)
        return stream.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", f"catalog-batch-{batch_id}-{filter_name}.xlsx"


def process_catalog_batch_in_background(batch_id: int, mode: str = "SOURCE_ONLY", use_llm: bool = False, item_ids: Optional[list[int]] = None) -> None:
    db = SessionLocal()
    try:
        CatalogService(db).process_batch(batch_id, mode=mode, use_llm=use_llm, item_ids=item_ids)
    finally:
        db.close()
