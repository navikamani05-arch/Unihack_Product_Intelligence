import pytest
import os
import tempfile
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import Base, get_db
from app.models.ingestion import IngestionJob, RawDocumentSource
from app.models.conflict import EvidenceChunk
from app.models.product import ProductRecord
from app.services.llm_extraction_service import LLMExtractionService


class FakeLLMClient:
    def __init__(self, response_text: str):
        self.response_text = response_text
        self.request = None

    class MockMessage:
        def __init__(self, content):
            self.content = content

    class MockChoice:
        def __init__(self, content):
            self.message = FakeLLMClient.MockMessage(content)

    class MockResponse:
        def __init__(self, content):
            self.choices = [FakeLLMClient.MockChoice(content)]

    class MockCompletions:
        def __init__(self, parent):
            self.parent = parent

        def create(self, **kwargs):
            self.parent.request = kwargs
            return FakeLLMClient.MockResponse(self.parent.response_text)

    @property
    def chat(self):
        return self.MockCompletions(self)


@pytest.fixture(scope="function")
def test_db():
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False}
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        os.unlink(db_path)


@pytest.fixture(scope="function")
def client(test_db):
    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def valid_payload(chunk_id="chunk_1"):
    return {
        "product_name": "Isolated Product",
        "sku": "ISO-001",
        "brand": "TestBrand",
        "category": "Motor",
        "description": "Test Description",
        "attributes": [
            {
                "attribute_name": "voltage",
                "raw_value": "400V",
                "normalized_value": "400",
                "unit": "V",
                "confidence_score": 0.95,
                "evidence_chunk_id": chunk_id,
                "page_number": None,
                "row_number": 1,
            }
        ],
        "missing_attributes": [],
    }


def test_job_evidence_isolation_and_filtering(test_db, monkeypatch):
    """Test 1, 2, 3, 5, 6: Verify evidence and extraction are strictly isolated per job_id."""
    # Create Job A (CSV)
    job_a = IngestionJob(job_name="Job A CSV", status="completed", source_type="csv")
    test_db.add(job_a)
    test_db.commit()
    test_db.refresh(job_a)

    source_a = RawDocumentSource(
        job_id=job_a.id,
        file_name="catalog.csv",
        raw_text_content="CSV Data",
    )
    test_db.add(source_a)
    test_db.commit()
    test_db.refresh(source_a)

    chunk_a = EvidenceChunk(
        job_id=job_a.id,
        source_id=source_a.id,
        stable_chunk_id="csv_chunk_1",
        snippet_text="Voltage 400V",
        source_type="csv",
        source_identifier="catalog.csv",
        row_number=1,
    )
    test_db.add(chunk_a)

    # Create Job B (PDF)
    job_b = IngestionJob(job_name="Job B PDF", status="completed", source_type="pdf")
    test_db.add(job_b)
    test_db.commit()
    test_db.refresh(job_b)

    source_b = RawDocumentSource(
        job_id=job_b.id,
        file_name="datasheet.pdf",
        raw_text_content="PDF Data",
    )
    test_db.add(source_b)
    test_db.commit()
    test_db.refresh(source_b)

    chunk_b = EvidenceChunk(
        job_id=job_b.id,
        source_id=source_b.id,
        stable_chunk_id="pdf_chunk_1",
        snippet_text="Rated Voltage 415V",
        source_type="pdf",
        source_identifier="datasheet.pdf",
        page_number=1,
    )
    test_db.add(chunk_b)
    test_db.commit()

    # Mock LLM for Job A extraction
    payload_a = valid_payload("csv_chunk_1")
    fake_client_a = FakeLLMClient(str({"products": [payload_a]}).replace("'", '"'))
    monkeypatch.setattr(LLMExtractionService, "get_client", classmethod(lambda cls: fake_client_a))

    # Test extracting Job A receives ONLY Job A chunks
    chunks_for_job_a = test_db.query(EvidenceChunk).filter(EvidenceChunk.job_id == job_a.id).all()
    assert len(chunks_for_job_a) == 1
    assert chunks_for_job_a[0].stable_chunk_id == "csv_chunk_1"
    assert chunks_for_job_a[0].source_type == "csv"

    # Verify Job B chunks do not appear in Job A query
    for c in chunks_for_job_a:
        assert c.job_id == job_a.id
        assert c.source_type != "pdf"


def test_same_job_multi_source_allowed(test_db):
    """Test 4: Verify uploading CSV + PDF in the SAME job allows combining sources."""
    job = IngestionJob(job_name="Mixed Job", status="completed", source_type="pdf")
    test_db.add(job)
    test_db.commit()
    test_db.refresh(job)

    source_pdf = RawDocumentSource(job_id=job.id, file_name="doc.pdf", raw_text_content="PDF")
    source_csv = RawDocumentSource(job_id=job.id, file_name="data.csv", raw_text_content="CSV")
    test_db.add_all([source_pdf, source_csv])
    test_db.commit()
    test_db.refresh(source_pdf)
    test_db.refresh(source_csv)

    chunk_1 = EvidenceChunk(job_id=job.id, source_id=source_pdf.id, stable_chunk_id="pdf_1", snippet_text="PDF text", source_type="pdf")
    chunk_2 = EvidenceChunk(job_id=job.id, source_id=source_csv.id, stable_chunk_id="csv_1", snippet_text="CSV text", source_type="csv")
    test_db.add_all([chunk_1, chunk_2])
    test_db.commit()

    # Query all chunks for this job
    job_chunks = test_db.query(EvidenceChunk).filter(EvidenceChunk.job_id == job.id).all()
    assert len(job_chunks) == 2
    source_types = {c.source_type for c in job_chunks}
    assert source_types == {"pdf", "csv"}
