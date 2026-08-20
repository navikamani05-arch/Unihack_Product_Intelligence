import io
import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
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


def test_dashboard_empty_state_is_honest(client):
    response = client.get("/api/v1/dashboard/overview")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["latest_batch"] is None
    assert payload["demo_product_id"] is None
    ground_truth = payload["availability"]["ground_truth"]
    assert ground_truth["status"] == "UNAVAILABLE"
    assert ground_truth["message"] == "Official ground truth dataset not available."
    assert all(metric["key"] != "avg_trust_score" for metric in payload["metrics"])


def test_dashboard_aggregates_real_catalog_and_product_detail(client, test_db):
    upload = client.post(
        "/api/v1/catalog/batches/upload",
        files={"file": ("dashboard.csv", catalog_csv("DASH-001,Dashboard Motor,Maker A,Brand A,400 V,5.5 kW\n"), "text/csv")},
    )
    assert upload.status_code == 200, upload.text
    batch_id = upload.json()["batch_id"]
    CatalogService(test_db).process_batch(batch_id, mode="SOURCE_ONLY", use_llm=False)

    overview_response = client.get("/api/v1/dashboard/overview")
    assert overview_response.status_code == 200, overview_response.text
    overview = overview_response.json()
    assert overview["latest_batch"]["id"] == batch_id
    assert overview["latest_batch"]["total_items"] == 1
    metrics = {metric["key"]: metric for metric in overview["metrics"]}
    assert metrics["products_processed"]["value"] == 1
    assert metrics["evidence_coverage"]["value"] is not None
    assert metrics["ground_truth_accuracy"]["status"] == "UNAVAILABLE"
    assert overview["pipeline"][-1]["key"] == "commerce_output"
    product_id = overview["demo_product_id"]
    assert product_id is not None

    products_response = client.get("/api/v1/dashboard/products", params={"search": "DASH-001"})
    assert products_response.status_code == 200, products_response.text
    products = products_response.json()
    assert products["total"] == 1
    assert products["items"][0]["sku"] == "DASH-001"
    assert products["items"][0]["source_types"] == ["csv"]

    detail_response = client.get(f"/api/v1/dashboard/products/{product_id}")
    assert detail_response.status_code == 200, detail_response.text
    detail = detail_response.json()
    assert detail["product"]["sku"] == "DASH-001"
    assert detail["raw_input"]["input_snapshot"]["Voltage"] == "400 V"
    assert detail["evidence"]
    assert all(item["source_type"] == "csv" for item in detail["evidence"])
    assert detail["commerce_output"] is not None
    assert detail["availability"]["ground_truth_accuracy"] == "UNAVAILABLE"


def test_dashboard_product_not_found_is_scoped(client):
    response = client.get("/api/v1/dashboard/products/999999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()

