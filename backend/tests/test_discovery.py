import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models.discovery import CandidateSource, DiscoveryEvidence, DiscoveryRun
from app.models.enrichment import EnrichmentRun
from app.models.ingestion import IngestionJob, RawDocumentSource
from app.models.product import ProductAttribute, ProductRecord
from app.services import discovery_service


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


def seed_product(db, *, sku="MTR-400-01", name="Verified Drive Motor", manufacturer="Example Manufacturing", voltage="400 V"):
    job = IngestionJob(job_name=f"Source for {sku}", status="completed", source_type="csv")
    db.add(job)
    db.flush()
    source = RawDocumentSource(job_id=job.id, file_name=f"{sku}.csv", raw_text_content=f"SKU: {sku}\nVoltage: {voltage}")
    db.add(source)
    db.flush()
    product = ProductRecord(
        sku=sku,
        sku_evidence_chunk_id=f"chunk-{job.id}",
        sku_source_type="csv",
        sku_source_identifier=source.file_name,
        sku_row_number=1,
        name=name,
        manufacturer=manufacturer,
        category="Motors",
    )
    db.add(product)
    db.flush()
    db.add(
        ProductAttribute(
            product_id=product.id,
            attribute_name="Voltage",
            raw_value=voltage,
            normalized_value=voltage,
            unit="V",
            confidence_score=0.98,
            source_type="csv",
            source_identifier=source.file_name,
            row_number=1,
            evidence_chunk_id=f"chunk-{job.id}",
        )
    )
    db.commit()
    return product


class FakeResponse:
    def __init__(self, html: str, *, status_code: int = 200, content_type: str = "text/html"):
        self.content = html.encode("utf-8")
        self.status_code = status_code
        self.headers = {"content-type": content_type, "content-length": str(len(self.content))}
        self.is_redirect = False

    def iter_content(self, chunk_size=65536):
        yield self.content


def install_fake_fetch(monkeypatch, texts_by_marker: dict[str, str]):
    monkeypatch.setattr(discovery_service, "_public_http_url", lambda value: (True, ""))

    def fake_get(url, **_kwargs):
        text = next((value for marker, value in texts_by_marker.items() if marker in url), "")
        return FakeResponse(f"<html><title>Remote product page</title><body>{text}</body></html>")

    monkeypatch.setattr(discovery_service.requests, "get", fake_get)


def test_no_provider_state_is_explicit_and_creates_no_sources(client, test_db, monkeypatch):
    product = seed_product(test_db)
    monkeypatch.setattr(discovery_service.settings, "discovery_provider", "none")
    monkeypatch.setattr(discovery_service.settings, "discovery_provider_api_key", None)

    status = client.get("/api/v1/discovery/provider-status")
    assert status.status_code == 200
    assert status.json()["configured"] is False
    assert status.json()["provider_name"] == "none"

    response = client.post(f"/api/v1/discovery/product/{product.id}", json={"user_urls": []})
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "provider_not_configured"
    assert response.json()["discovered_count"] == 0
    assert test_db.query(CandidateSource).count() == 0


def test_user_provided_url_is_recorded_processed_and_returned_by_detail(client, test_db, monkeypatch):
    product = seed_product(test_db)
    install_fake_fetch(monkeypatch, {"official": "Example Manufacturing Verified Drive Motor MTR-400-01. Voltage: 400 V."})

    start = client.post(f"/api/v1/discovery/product/{product.id}", json={"user_urls": ["https://examplemanufacturing.com/official"]})
    assert start.status_code == 200, start.text
    assert start.json()["status"] == "completed"
    assert start.json()["verified_count"] == 1

    detail = client.get(f"/api/v1/discovery/product/{product.id}")
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert set(body) == {"run", "queries", "sources", "evidence"}
    assert body["queries"] == []
    assert len(body["sources"]) == 1
    assert body["sources"][0]["user_provided"] is True
    assert body["sources"][0]["status"] == "verified"
    assert body["evidence"]
    assert all(item["source_url"] == "https://examplemanufacturing.com/official" for item in body["evidence"])


def test_private_or_localhost_url_is_rejected_before_fetch(client, test_db):
    product = seed_product(test_db)
    response = client.post(f"/api/v1/discovery/product/{product.id}", json={"user_urls": ["http://127.0.0.1/internal"]})
    assert response.status_code == 200, response.text
    source = test_db.query(CandidateSource).one()
    assert source.status == "rejected"
    assert "Private or reserved" in source.rejection_reason
    assert test_db.query(DiscoveryEvidence).count() == 0


def test_identity_verification_rejects_unrelated_sources_and_accepts_no_evidence(client, test_db, monkeypatch):
    product = seed_product(test_db)
    install_fake_fetch(monkeypatch, {"unrelated": "Generic appliance documentation. Voltage: 415 V. No product identifier is provided."})

    response = client.post(f"/api/v1/discovery/product/{product.id}", json={"user_urls": ["https://catalog.example/unrelated"]})
    assert response.status_code == 200, response.text
    source = test_db.query(CandidateSource).one()
    assert source.status == "rejected"
    assert "SKU / Product ID was not found" in source.rejection_reason
    assert test_db.query(DiscoveryEvidence).count() == 0


def test_verified_sources_are_ranked_by_quality_and_only_verified_sources_yield_evidence(client, test_db, monkeypatch):
    product = seed_product(test_db)
    install_fake_fetch(
        monkeypatch,
        {
            "official": "Example Manufacturing Verified Drive Motor MTR-400-01. Voltage: 400 V.",
            "reseller": "Example Manufacturing Verified Drive Motor MTR-400-01. Voltage: 400 V.",
            "unrelated": "A different product MTR-400-99. Voltage: 415 V.",
        },
    )

    response = client.post(
        f"/api/v1/discovery/product/{product.id}",
        json={"user_urls": ["https://examplemanufacturing.com/official", "https://reseller.example/reseller", "https://catalog.example/unrelated"]},
    )
    assert response.status_code == 200, response.text
    sources = test_db.query(CandidateSource).order_by(CandidateSource.id).all()
    verified = [source for source in sources if source.status == "verified"]
    assert len(verified) == 2
    assert verified[0].rank == 1
    assert verified[0].domain == "examplemanufacturing.com"
    assert verified[0].quality_score > verified[1].quality_score
    assert all(row.candidate_source_id in {source.id for source in verified} for row in test_db.query(DiscoveryEvidence).all())


def test_cross_source_conflicts_are_detected_without_selecting_a_value(client, test_db, monkeypatch):
    product = seed_product(test_db)
    install_fake_fetch(
        monkeypatch,
        {
            "source-a": "Example Manufacturing Verified Drive Motor MTR-400-01. Voltage: 400 V.",
            "source-b": "Example Manufacturing Verified Drive Motor MTR-400-01. Voltage: 415 V.",
        },
    )

    response = client.post(
        f"/api/v1/discovery/product/{product.id}",
        json={"user_urls": ["https://examplemanufacturing.com/source-a", "https://reseller.example/source-b"]},
    )
    assert response.status_code == 200, response.text
    assert response.json()["conflict_count"] == 1, response.json()["summary"]
    conflicts = client.get(f"/api/v1/discovery/product/{product.id}/cross-source-conflicts")
    assert conflicts.status_code == 200, conflicts.text
    voltage_conflict = next(item for item in conflicts.json() if item["attribute_name"] == "Voltage")
    assert set(voltage_conflict["values"]) == {"400 v", "415 v"}
    assert voltage_conflict["source_count"] == 2
    assert test_db.query(ProductAttribute).filter_by(product_id=product.id, attribute_name="Voltage").one().raw_value == "400 V"


def test_discovery_evidence_is_strictly_scoped_to_the_requested_product(client, test_db, monkeypatch):
    first = seed_product(test_db, sku="MTR-A-01", name="Alpha Drive Motor", voltage="400 V")
    second = seed_product(test_db, sku="MTR-B-02", name="Beta Drive Motor", voltage="415 V")
    install_fake_fetch(
        monkeypatch,
        {
            "alpha": "Example Manufacturing Alpha Drive Motor MTR-A-01. Voltage: 400 V.",
            "beta": "Example Manufacturing Beta Drive Motor MTR-B-02. Voltage: 415 V.",
        },
    )

    assert client.post(f"/api/v1/discovery/product/{first.id}", json={"user_urls": ["https://examplemanufacturing.com/alpha"]}).status_code == 200
    assert client.post(f"/api/v1/discovery/product/{second.id}", json={"user_urls": ["https://examplemanufacturing.com/beta"]}).status_code == 200

    first_evidence = client.get(f"/api/v1/discovery/product/{first.id}/evidence")
    second_evidence = client.get(f"/api/v1/discovery/product/{second.id}/evidence")
    assert first_evidence.status_code == 200
    assert second_evidence.status_code == 200
    assert first_evidence.json() and second_evidence.json()
    assert all("MTR-B-02" not in item["quote"] for item in first_evidence.json())
    assert all("MTR-A-01" not in item["quote"] for item in second_evidence.json())
    assert {row.product_id for row in test_db.query(DiscoveryEvidence).all()} == {first.id, second.id}


def test_discovery_enabled_enrichment_runs_discovery_stage_without_provider(client, test_db, monkeypatch):
    product = seed_product(test_db)
    monkeypatch.setattr(discovery_service.settings, "discovery_provider", "none")
    monkeypatch.setattr(discovery_service.settings, "discovery_provider_api_key", None)

    response = client.post(f"/api/v1/analyze/{product.id}", json={"use_llm": False, "mode": "DISCOVERY_ENABLED"})
    assert response.status_code == 200, response.text
    run = test_db.query(EnrichmentRun).order_by(EnrichmentRun.id.desc()).first()
    assert run.product_understanding["discovery_status"] == "provider_not_configured"
    assert run.product_understanding["discovery_run_id"]
    assert any(entry["stage"] == "source_discovery" and entry["status"] == "warning" for entry in run.progress_log)
    discovery_run = test_db.get(DiscoveryRun, run.product_understanding["discovery_run_id"])
    assert discovery_run.status == "provider_not_configured"
