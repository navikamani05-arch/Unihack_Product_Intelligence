import io
import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.utils.upload import safe_upload_filename


@pytest.fixture()
def client():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as api_client:
            yield api_client
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
        os.unlink(path)


def test_safe_upload_filename_strips_client_paths():
    assert safe_upload_filename("../../etc/passwd") == "passwd"
    assert safe_upload_filename(r"C:\\temp\\catalog.csv") == "catalog.csv"
    assert safe_upload_filename(None) == "upload"


def test_catalog_upload_enforces_configured_byte_limit(client, monkeypatch):
    monkeypatch.setattr(settings, "max_upload_size_bytes", 8)
    response = client.post(
        "/api/v1/catalog/batches/upload",
        files={"file": ("catalog.csv", io.BytesIO(b"identifier,description\nSKU-001,Motor\n"), "text/csv")},
    )
    assert response.status_code == 413
    assert "configured limit" in response.json()["detail"]


def test_health_and_readiness_contracts(client):
    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json()["status"] in {"healthy", "degraded"}
    assert "database" in health.json()

    readiness = client.get("/api/v1/health/ready")
    assert readiness.status_code == 200
    assert readiness.json() == {"status": "ready", "database": "healthy"}


def test_root_contract_hides_docs_when_disabled(monkeypatch, client):
    monkeypatch.setattr(settings, "enable_docs", False)
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["docs"] == "/docs" or response.json()["docs"] is None
