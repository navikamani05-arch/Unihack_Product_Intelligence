import json
import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models.conflict import EvidenceChunk
from app.models.ingestion import IngestionJob, RawDocumentSource
from app.services.extraction_job_service import ExtractionJobService
from app.services.llm_extraction_service import LLMExtractionError, LLMExtractionService


class FakeChatClient:
    def __init__(self, payload, delay=0.0):
        self.payload = payload
        self.delay = delay

    def __call__(self, **kwargs):
        if self.delay:
            time.sleep(self.delay)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(self.payload)))]
        )


def _seed_job(db):
    job = IngestionJob(job_name="Background extraction", status="completed", source_type="csv")
    db.add(job)
    db.flush()
    source = RawDocumentSource(job_id=job.id, file_name="background.csv")
    db.add(source)
    db.flush()
    db.add(
        EvidenceChunk(
            job_id=job.id,
            source_id=source.id,
            stable_chunk_id="csv_row_1",
            snippet_text="SKU: BG-1\nProduct Name: Background Motor\nVoltage: 400 V",
            source_type="csv",
            source_identifier="background.csv",
            row_number=1,
        )
    )
    db.commit()
    return job


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'background.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = factory()
    monkeypatch.setattr("app.services.extraction_job_service.SessionLocal", factory)
    yield session, factory
    session.close()


def _override_db(db):
    def dependency():
        yield db

    return dependency


def _payload():
    return {
        "products": [
            {
                "product_name": "Background Motor",
                "sku": "BG-1",
                "brand": "Acme",
                "category": "Motor",
                "description": "A background-test motor.",
                "attributes": [
                    {
                        "attribute_name": "voltage",
                        "raw_value": "400 V",
                        "normalized_value": "400",
                        "unit": "V",
                        "confidence_score": 0.95,
                        "evidence_chunk_id": "csv_row_1",
                        "row_number": 1,
                    }
                ],
                "missing_attributes": [],
            }
        ]
    }


def _wait_for_status(factory, task_id, terminal=None, timeout=2.0):
    terminal = terminal or {"COMPLETED", "FAILED", "CANCELLED"}
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        db = factory()
        try:
            task = db.query(__import__("app.models.extraction", fromlist=["ExtractionJob"]).ExtractionJob).filter_by(id=task_id).one()
            if task.status in terminal:
                return task.status, task.error_message
        finally:
            db.close()
        time.sleep(0.02)
    raise AssertionError(f"Task {task_id} did not reach {terminal} within {timeout}s")


def test_extraction_returns_task_immediately_and_status_completes(monkeypatch, isolated_db):
    db, factory = isolated_db
    job = _seed_job(db)

    def fake_extract(cls, chunks, source_metadata, progress_callback=None, cancellation_check=None):
        if progress_callback:
            progress_callback(1, 1, len(chunks), 0)
        time.sleep(0.15)
        return _payload()

    monkeypatch.setattr(LLMExtractionService, "extract_from_chunks", classmethod(fake_extract))
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        client = TestClient(app)
        started = time.monotonic()
        response = client.post(f"/api/v1/extract/{job.id}")
        elapsed = time.monotonic() - started
        assert response.status_code == 200
        body = response.json()
        assert body["status"] in {"QUEUED", "PROCESSING", "COMPLETED"}
        assert body["task_id"]
        assert elapsed < 0.12

        status, error = _wait_for_status(factory, body["task_id"])
        assert status == "COMPLETED", error
        status_response = client.get(f"/api/v1/extract/tasks/{body['task_id']}/status")
        assert status_response.status_code == 200
        status_body = status_response.json()
        assert status_body["status"] == "COMPLETED"
        assert status_body["extracted_product_count"] == 1
        assert status_body["result"]["extracted_products"][0]["sku"] == "BG-1"
    finally:
        app.dependency_overrides.clear()


def test_health_remains_responsive_during_background_extraction(monkeypatch, isolated_db):
    db, factory = isolated_db
    job = _seed_job(db)

    def slow_extract(cls, chunks, source_metadata, progress_callback=None, cancellation_check=None):
        time.sleep(0.35)
        return {"products": []}

    monkeypatch.setattr(LLMExtractionService, "extract_from_chunks", classmethod(slow_extract))
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        client = TestClient(app)
        response = client.post(f"/api/v1/extract/{job.id}")
        assert response.status_code == 200
        started = time.monotonic()
        health = client.get("/api/v1/health")
        elapsed = time.monotonic() - started
        assert health.status_code == 200
        assert health.json()["status"] in {"healthy", "degraded"}
        assert elapsed < 0.25
        status, error = _wait_for_status(factory, response.json()["task_id"])
        assert status == "COMPLETED", error
    finally:
        app.dependency_overrides.clear()


def test_provider_failure_is_persisted_as_failed_task(monkeypatch, isolated_db):
    db, factory = isolated_db
    job = _seed_job(db)

    def failing_extract(cls, chunks, source_metadata, progress_callback=None, cancellation_check=None):
        raise LLMExtractionError("provider returned invalid JSON")

    monkeypatch.setattr(LLMExtractionService, "extract_from_chunks", classmethod(failing_extract))
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        client = TestClient(app)
        response = client.post(f"/api/v1/extract/{job.id}")
        assert response.status_code == 200
        status, error = _wait_for_status(factory, response.json()["task_id"])
        assert status == "FAILED"
        assert error == "provider returned invalid JSON"
        status_body = client.get(f"/api/v1/extract/{job.id}/status").json()
        assert status_body["status"] == "FAILED"
        assert "invalid JSON" in status_body["error"]
    finally:
        app.dependency_overrides.clear()


def test_queued_extraction_can_be_cancelled_before_worker_starts(isolated_db):
    db, _ = isolated_db
    job = _seed_job(db)
    task = ExtractionJobService(db).create_task(job.id, 1)
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        client = TestClient(app)
        response = client.post(f"/api/v1/extract/{job.id}/cancel")
        assert response.status_code == 200
        body = response.json()
        assert body["task_id"] == task.id
        assert body["status"] == "CANCELLED"
        assert body["cancellation_requested"] is True
    finally:
        app.dependency_overrides.clear()
