import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models.conflict import DataConflict, EvidenceChunk
from app.models.enrichment import EnrichmentReviewDecision, EnrichmentRun
from app.models.ingestion import IngestionJob, RawDocumentSource
from app.models.product import ProductAttribute, ProductRecord


@pytest.fixture(scope="function")
def test_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = Session()
    try:
        yield db
    finally:
        db.close()
        os.unlink(path)


@pytest.fixture(scope="function")
def client(test_db):
    def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as api_client:
        yield api_client
    app.dependency_overrides.clear()


def seed_product(db, *, sku="MTR-400-01", source_type="pdf", value="400 V", include_sku=True):
    job = IngestionJob(job_name="Motor source", status="completed", source_type=source_type)
    db.add(job)
    db.flush()
    source = RawDocumentSource(job_id=job.id, file_name="motor.pdf", raw_text_content="SKU: MTR-400-01\nVoltage: 400 V")
    db.add(source)
    db.flush()
    product = ProductRecord(
        sku=sku if include_sku else None,
        sku_evidence_chunk_id=f"chunk-{job.id}" if include_sku else None,
        sku_source_type=source_type if include_sku else None,
        sku_source_identifier="motor.pdf" if include_sku else None,
        sku_page_number=2 if include_sku else None,
        name="Verified Drive Motor",
        manufacturer="Example Manufacturing",
        category="Motors",
    )
    db.add(product)
    db.flush()
    attribute = ProductAttribute(
        product_id=product.id,
        attribute_name="Voltage",
        raw_value=value,
        normalized_value=value,
        unit="V",
        confidence_score=0.99,
        source_type=source_type,
        source_identifier="motor.pdf",
        page_number=2,
        evidence_chunk_id=f"chunk-{job.id}",
    )
    db.add(attribute)
    db.flush()
    chunk = EvidenceChunk(
        job_id=job.id,
        source_id=source.id,
        attribute_id=attribute.id,
        stable_chunk_id=f"chunk-{job.id}",
        snippet_text=f"SKU: {sku or 'not supplied'}\nVoltage: {value}",
        source_type=source_type,
        source_identifier="motor.pdf",
        page_number=2,
    )
    db.add(chunk)
    db.commit()
    return product, attribute, chunk


def test_analyze_preserves_source_value_evidence_and_no_fabrication(client, test_db):
    product, attribute, _ = seed_product(test_db)
    original = attribute.raw_value

    response = client.post(f"/api/v1/analyze/{product.id}", json={"use_llm": False})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "completed"
    assert body["product_status"] == "NEEDS_REVIEW"  # PDF authority produces evidence-based but non-trust confidence.
    assert body["attribute_count"] == 1

    details = client.get(f"/api/v1/enrichment/{product.id}")
    assert details.status_code == 200, details.text
    payload = details.json()
    voltage = next(item for item in payload["attributes"] if item["name"] == "Voltage")
    assert voltage["raw_value"] == "400 V"
    assert voltage["evidence"][0]["source_type"] == "pdf"
    assert voltage["evidence"][0]["page_number"] == 2
    assert test_db.query(ProductAttribute).filter_by(id=attribute.id).one().raw_value == original
    assert "discovered_url" not in payload["run"]["product_understanding"]


def test_missing_explicit_identifier_is_insufficient_and_not_invented(client, test_db):
    product, _, _ = seed_product(test_db, sku=None, include_sku=False)
    response = client.post(f"/api/v1/analyze/{product.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["product_status"] == "INSUFFICIENT_DATA"
    assert "sku or product id" in body["missing_attributes"]
    assert test_db.query(ProductRecord).filter_by(id=product.id).one().sku is None


def test_existing_critical_conflict_produces_conflicting_status_and_is_not_resolved(client, test_db):
    product, _, _ = seed_product(test_db)
    conflict = DataConflict(
        product_id=product.id,
        attribute_name="SKU",
        conflict_type="IDENTITY_CONFLICT",
        severity="CRITICAL",
        status="REQUIRES_REVIEW",
        resolution_status="unresolved",
        source_a_name="PDF",
        source_a_value="MTR-400-01",
        source_b_name="CSV",
        source_b_value="MTR-400-02",
    )
    test_db.add(conflict)
    test_db.commit()

    response = client.post(f"/api/v1/analyze/{product.id}")
    assert response.status_code == 200
    assert response.json()["product_status"] == "CONFLICTING_DATA"
    details = client.get(f"/api/v1/enrichment/{product.id}").json()
    assert details["conflicts"][0]["id"] == conflict.id
    assert test_db.query(DataConflict).filter_by(id=conflict.id).one().resolution_status == "unresolved"


def test_batch_processes_products_and_batch_endpoint_is_not_captured_by_dynamic_route(client, test_db):
    first, _, _ = seed_product(test_db, sku="MTR-BATCH-1")
    second, _, _ = seed_product(test_db, sku="MTR-BATCH-2")
    response = client.post("/api/v1/analyze/batch", json={"product_ids": [first.id, second.id]})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_products"] == 2
    assert body["successful_count"] == 2
    assert body["processed_count"] == 2


def test_review_is_non_destructive_and_rejects_cross_product_attribute(client, test_db):
    product, attribute, _ = seed_product(test_db, sku="MTR-REVIEW-1")
    other, other_attribute, _ = seed_product(test_db, sku="MTR-REVIEW-2")
    client.post(f"/api/v1/analyze/{product.id}")
    source_value = attribute.raw_value

    review = client.post(f"/api/v1/enrichment/{product.id}/review", json={"action": "EDIT", "attribute_id": attribute.id, "value": "415 V", "reason": "Reviewer correction proposal"})
    assert review.status_code == 200, review.text
    assert test_db.query(ProductAttribute).filter_by(id=attribute.id).one().raw_value == source_value
    decision = test_db.query(EnrichmentReviewDecision).one()
    assert decision.reviewer_value == "415 V"
    assert decision.evidence_snapshot[0]["page_number"] == 2

    rejected = client.post(f"/api/v1/enrichment/{product.id}/review", json={"action": "EDIT", "attribute_id": other_attribute.id, "value": "415 V"})
    assert rejected.status_code == 422


def test_evidence_attributes_and_json_csv_exports_are_available(client, test_db):
    product, _, _ = seed_product(test_db, sku="MTR-EXPORT")
    client.post(f"/api/v1/analyze/{product.id}")
    assert client.get(f"/api/v1/enrichment/{product.id}/evidence").status_code == 200
    assert client.get(f"/api/v1/enrichment/{product.id}/attributes").status_code == 200
    assert client.get(f"/api/v1/enrichment/{product.id}/conflicts").status_code == 200
    json_export = client.get(f"/api/v1/enrichment/{product.id}/export", params={"format": "json"})
    csv_export = client.get(f"/api/v1/enrichment/{product.id}/export", params={"format": "csv"})
    assert json_export.status_code == 200 and "application/json" in json_export.headers["content-type"]
    assert csv_export.status_code == 200 and "Voltage" in csv_export.text
    assert test_db.query(EnrichmentRun).filter_by(product_id=product.id).count() == 1


def test_enrichment_output_isolated_to_the_selected_product_evidence(client, test_db):
    first, _, first_chunk = seed_product(test_db, sku="MTR-ISOLATED-1", value="400 V")
    second, _, second_chunk = seed_product(test_db, sku="MTR-ISOLATED-2", value="415 V")

    response = client.post(f"/api/v1/analyze/{first.id}")
    assert response.status_code == 200
    payload = client.get(f"/api/v1/enrichment/{first.id}").json()
    voltage = next(item for item in payload["attributes"] if item["name"] == "Voltage")
    evidence_ids = {item["evidence_chunk_id"] for item in voltage["evidence"]}
    assert evidence_ids == {first_chunk.stable_chunk_id}
    assert second_chunk.stable_chunk_id not in evidence_ids
    assert voltage["raw_value"] == "400 V"
    assert "415 V" not in str(payload)
