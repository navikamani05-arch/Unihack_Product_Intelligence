import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models.commerce_output import CommerceOutput, CommerceOutputField
from app.models.conflict import DataConflict, EvidenceChunk
from app.models.enrichment import EnrichmentReviewDecision
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


def seed_product(db, *, sku="MTR-COMMERCE-1", value="400 V"):
    job = IngestionJob(job_name="Commerce source", status="completed", source_type="pdf")
    db.add(job)
    db.flush()
    source = RawDocumentSource(job_id=job.id, file_name="commerce-motor.pdf", raw_text_content=f"SKU: {sku}\nVoltage: {value}")
    db.add(source)
    db.flush()
    product = ProductRecord(
        sku=sku,
        sku_evidence_chunk_id=f"commerce-chunk-{job.id}",
        sku_source_type="pdf",
        sku_source_identifier="commerce-motor.pdf",
        sku_page_number=3,
        name="Commerce Test Motor",
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
        confidence_score=0.91,
        source_type="pdf",
        source_identifier="commerce-motor.pdf",
        page_number=3,
        evidence_chunk_id=f"commerce-chunk-{job.id}",
    )
    db.add(attribute)
    db.flush()
    db.add(EvidenceChunk(
        job_id=job.id,
        source_id=source.id,
        attribute_id=attribute.id,
        stable_chunk_id=f"commerce-chunk-{job.id}",
        snippet_text=f"SKU: {sku}\nVoltage: {value}",
        source_type="pdf",
        source_identifier="commerce-motor.pdf",
        page_number=3,
    ))
    db.commit()
    return product, attribute


def analyze(client, product_id):
    response = client.post(f"/api/v1/analyze/{product_id}")
    assert response.status_code == 200, response.text


def test_commerce_output_preserves_source_values_and_pdf_provenance(client, test_db):
    product, attribute = seed_product(test_db, value="400 V")
    analyze(client, product.id)

    response = client.post(f"/api/v1/commerce-output/{product.id}/generate")
    assert response.status_code == 200, response.text
    body = response.json()
    voltage = next(field for field in body["fields"] if field["field_key"] == "voltage")
    assert voltage["raw_value"] == "400 V"
    assert voltage["normalized_value"] == "400 V"
    assert voltage["output_value"] == "400 V"
    assert voltage["provenance_status"] == "PRESENT"
    assert voltage["evidence"][0]["source_type"] == "pdf"
    assert voltage["evidence"][0]["page_number"] == 3
    assert body["ground_truth_accuracy"] == "UNAVAILABLE"
    assert body["validation"]["character_limit_unavailable"] > 0
    assert test_db.query(ProductAttribute).filter_by(id=attribute.id).one().raw_value == "400 V"


def test_missing_identifier_is_explicit_and_not_fabricated(client, test_db):
    product, _ = seed_product(test_db, sku=None)
    product.sku = None
    product.sku_source_identifier = None
    product.sku_evidence_chunk_id = None
    test_db.commit()
    analyze(client, product.id)

    response = client.get(f"/api/v1/commerce-output/{product.id}")
    assert response.status_code == 200, response.text
    body = response.json()
    identifier = next(field for field in body["fields"] if field["field_key"] == "sku_or_product_id")
    assert identifier["output_value"] is None
    assert identifier["field_status"] == "MISSING"
    assert identifier["provenance_status"] == "UNAVAILABLE"
    assert body["record"]["sku_or_product_id"] is None


def test_conflict_and_non_destructive_review_state_are_propagated(client, test_db):
    product, attribute = seed_product(test_db)
    conflict = DataConflict(
        product_id=product.id,
        attribute_name="Voltage",
        conflict_type="VALUE_CONFLICT",
        severity="HIGH",
        status="REQUIRES_REVIEW",
        source_a_name="PDF",
        source_a_value="400 V",
        source_b_name="Website",
        source_b_value="415 V",
    )
    test_db.add(conflict)
    test_db.commit()
    analyze(client, product.id)
    review = client.post(f"/api/v1/enrichment/{product.id}/review", json={"action": "EDIT", "attribute_id": attribute.id, "value": "415 V", "reason": "Review proposal"})
    assert review.status_code == 200, review.text

    body = client.get(f"/api/v1/commerce-output/{product.id}").json()
    voltage = next(field for field in body["fields"] if field["field_key"] == "voltage")
    assert voltage["field_status"] == "CONFLICT"
    assert voltage["conflict_ids"] == [conflict.id]
    assert voltage["review_state"] == "EDIT"
    assert voltage["output_value"] == "400 V"
    assert test_db.query(ProductAttribute).filter_by(id=attribute.id).one().raw_value == "400 V"


def test_commerce_exports_json_csv_and_xlsx(client, test_db):
    product, _ = seed_product(test_db)
    analyze(client, product.id)
    for fmt, content_type in [("json", "application/json"), ("csv", "text/csv"), ("xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")]:
        response = client.get(f"/api/v1/commerce-output/{product.id}/export", params={"format": fmt})
        assert response.status_code == 200, response.text
        assert content_type in response.headers["content-type"]
        assert len(response.content) > 20
    assert test_db.query(CommerceOutput).filter_by(product_id=product.id).count() == 1
    assert test_db.query(CommerceOutputField).count() >= 5
