import io
import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models.catalog import CatalogBatch, CatalogItem
from app.models.conflict import EvidenceChunk
from app.models.product import ProductAttribute, ProductRecord
from app.services.catalog_service import CatalogService


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


def catalog_csv(rows: str) -> io.BytesIO:
    return io.BytesIO(("Mfg_Part_Num,Part_Desc,Part_Manuf,E1_Brand,Voltage,Power\n" + rows).encode())


def upload(client, content: io.BytesIO, filename="catalog.csv"):
    return client.post("/api/v1/catalog/batches/upload", files={"file": (filename, content, "text/csv")})


def test_catalog_upload_preserves_rows_and_validates_required_fields(client, test_db):
    response = upload(client, catalog_csv("SKU-001,Motor One,Maker A,Brand A,400 V,5.5 kW\n,Motor Missing ID,Maker A,Brand A,230 V,2 kW\nSKU-003,Motor Three,,Brand C,110 V,1 kW\n"))
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["total_rows"] == 3
    assert payload["valid_rows"] == 1
    assert payload["invalid_rows"] == 2
    assert payload["detected_columns"][:3] == ["Mfg_Part_Num", "Part_Desc", "Part_Manuf"]
    assert any("Missing required product identifier" in warning for warning in payload["missing_required_fields"].keys()) is False
    batch = test_db.query(CatalogBatch).one()
    items = test_db.query(CatalogItem).filter_by(batch_id=batch.id).order_by(CatalogItem.row_number).all()
    assert [item.row_number for item in items] == [2, 3, 4]
    assert items[0].input_snapshot["Voltage"] == "400 V"
    assert items[0].identifier == "SKU-001"
    assert items[1].validation_status == "INVALID"
    assert any("Missing required product identifier" in error for error in items[1].validation_errors)
    assert items[2].validation_status == "INVALID"
    assert any("Missing manufacturer" in error for error in items[2].validation_errors)


def test_catalog_rejects_unsupported_extension_and_missing_required_columns(client):
    response = upload(client, io.BytesIO(b"name,description\nOne,Motor\n"), "catalog.txt")
    assert response.status_code == 400
    response = upload(client, io.BytesIO(b"name,description\nOne,Motor\n"))
    assert response.status_code == 400
    assert "identifier" in response.json()["detail"].lower()


def test_catalog_processing_creates_source_backed_products_and_commerce_outputs(client, test_db):
    response = upload(client, catalog_csv("SKU-101,Motor One,Maker A,Brand A,400 V,5.5 kW\nSKU-102,Motor Two,Maker B,Brand B,230 V,2 kW\n"))
    batch_id = response.json()["batch_id"]
    service = CatalogService(test_db)
    batch = service.process_batch(batch_id, mode="SOURCE_ONLY", use_llm=False)
    assert batch.status == "COMPLETED"
    assert batch.processed_items == 2
    assert batch.successful_items == 2
    items = test_db.query(CatalogItem).filter_by(batch_id=batch_id).order_by(CatalogItem.row_number).all()
    assert all(item.processing_status == "COMPLETED" for item in items)
    products = test_db.query(ProductRecord).order_by(ProductRecord.id).all()
    assert {product.sku for product in products} == {"SKU-101", "SKU-102"}
    assert all(item.product_id and item.commerce_output_id for item in items)
    attributes = test_db.query(ProductAttribute).all()
    assert all(attribute.source_type == "csv" and attribute.row_number in {2, 3} for attribute in attributes)
    chunks = test_db.query(EvidenceChunk).all()
    assert len(chunks) >= 4
    assert {chunk.row_number for chunk in chunks} == {2, 3}
    assert {chunk.source_type for chunk in chunks} == {"csv"}


def test_catalog_processing_isolated_between_batches(client, test_db):
    first = upload(client, catalog_csv("SKU-A,First Motor,Maker A,Brand A,400 V,5 kW\n"), "first.csv").json()["batch_id"]
    second = upload(client, catalog_csv("SKU-B,Second Motor,Maker B,Brand B,230 V,2 kW\n"), "second.csv").json()["batch_id"]
    CatalogService(test_db).process_batch(first, use_llm=False)
    CatalogService(test_db).process_batch(second, use_llm=False)
    first_item = test_db.query(CatalogItem).filter_by(batch_id=first).one()
    second_item = test_db.query(CatalogItem).filter_by(batch_id=second).one()
    first_product = test_db.query(ProductRecord).filter_by(id=first_item.product_id).one()
    second_product = test_db.query(ProductRecord).filter_by(id=second_item.product_id).one()
    assert first_product.sku == "SKU-A"
    assert second_product.sku == "SKU-B"
    first_attributes = test_db.query(ProductAttribute).filter_by(product_id=first_product.id).all()
    second_attributes = test_db.query(ProductAttribute).filter_by(product_id=second_product.id).all()
    assert all(attribute.source_identifier == "first.csv" for attribute in first_attributes)
    assert all(attribute.source_identifier == "second.csv" for attribute in second_attributes)
    assert not any(attribute.product_id == first_product.id and attribute.source_identifier == "second.csv" for attribute in second_attributes)


def test_catalog_cancel_and_retry_state_are_persisted(client, test_db):
    response = upload(client, catalog_csv("SKU-C,Cancelable Motor,Maker C,Brand C,400 V,5 kW\n"))
    batch_id = response.json()["batch_id"]
    cancelled = client.post(f"/api/v1/catalog/batches/{batch_id}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"
    # Cancelled batches have no processed failure rows yet; retry is safe and transitions the batch back to queued work.
    retry = CatalogService(test_db).retry(batch_id)
    assert retry.status == "QUEUED"
    assert test_db.query(CatalogItem).filter_by(batch_id=batch_id).one().processing_status == "QUEUED"


def test_catalog_results_summary_review_queue_and_exports(client, test_db):
    response = upload(client, catalog_csv("SKU-X,Export Motor,Maker X,Brand X,400 V,5 kW\n"))
    batch_id = response.json()["batch_id"]
    CatalogService(test_db).process_batch(batch_id, use_llm=False)
    results = client.get(f"/api/v1/catalog/batches/{batch_id}/results?search=SKU-X")
    assert results.status_code == 200
    assert results.json()["total"] == 1
    summary = client.get(f"/api/v1/catalog/batches/{batch_id}/summary")
    assert summary.status_code == 200
    assert summary.json()["ground_truth_message"] == "Official ground truth dataset not available."
    review = client.get(f"/api/v1/catalog/batches/{batch_id}/review-queue")
    assert review.status_code == 200
    assert "items" in review.json()
    for format_name, content_type in [("json", "application/json"), ("csv", "text/csv"), ("xlsx", "spreadsheetml")]:
        export = client.get(f"/api/v1/catalog/batches/{batch_id}/export?format={format_name}")
        assert export.status_code == 200, export.text
        assert content_type in export.headers["content-type"]
        assert len(export.content) > 10


def test_catalog_status_progress_and_reports_are_available(client, test_db):
    response = upload(client, catalog_csv("SKU-S,Status Motor,Maker S,Brand S,400 V,5 kW\n"))
    batch_id = response.json()["batch_id"]
    status = client.get(f"/api/v1/catalog/batches/{batch_id}/status")
    progress = client.get(f"/api/v1/catalog/batches/{batch_id}/progress")
    assert status.status_code == progress.status_code == 200
    assert status.json()["progress_percentage"] == 0
    for report_type in ["catalog-summary", "failed-products", "conflict-report", "human-review-report", "evaluation-report"]:
        report = client.get(f"/api/v1/catalog/batches/{batch_id}/reports/{report_type}")
        assert report.status_code == 200, report.text
