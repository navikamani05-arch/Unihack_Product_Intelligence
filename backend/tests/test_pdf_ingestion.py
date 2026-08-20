"""Tests for PDF extraction and ingestion service."""
import pytest
import os
import fitz  # PyMuPDF
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.database import Base, get_db
from app.services.pdf_extractor import PDFExtractor, PDFExtractionError
from app.services.ingestion_service import IngestionService
from app.models.ingestion import IngestionJob, RawDocumentSource
from app.models.conflict import EvidenceChunk


from app.database import engine as app_engine, SessionLocal as AppSessionLocal
@pytest.fixture
def test_db():
    """Create tables on app engine for API testing."""
    Base.metadata.create_all(bind=app_engine)
    db = AppSessionLocal()
    yield db
    db.close()


@pytest.fixture
def client():
    """Create a FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def sample_pdf(tmp_path):
    """Create a sample PDF file for testing."""
    pdf_path = tmp_path / "test_datasheet.pdf"
    doc = fitz.open()
    
    # Page 1
    page1 = doc.new_page()
    page1.insert_text((50, 50), "Industrial Pressure Transmitter Model PT-100\nRated Pressure: 0-100 bar\nVoltage: 24V DC")
    
    # Page 2
    page2 = doc.new_page()
    page2.insert_text((50, 50), "Operating Temperature: -40°C to +85°C\nOutput Signal: 4-20mA")
    
    doc.save(str(pdf_path))
    doc.close()
    return str(pdf_path)


@pytest.fixture
def corrupted_pdf(tmp_path):
    """Create a corrupted PDF file for testing."""
    pdf_path = tmp_path / "corrupted.pdf"
    pdf_path.write_text("This is not a valid PDF file content.")
    return str(pdf_path)


class TestPDFExtractor:
    """Test PDFExtractor service."""

    def test_extract_text_from_valid_pdf(self, sample_pdf):
        """Test extracting text from a valid multi-page PDF."""
        result = PDFExtractor.extract_text_from_pdf(sample_pdf)
        
        assert result["filename"] == "test_datasheet.pdf"
        assert result["total_pages"] == 2
        assert len(result["pages"]) == 2
        
        # Check page 1
        assert result["pages"][0]["page_number"] == 1
        assert "PT-100" in result["pages"][0]["text"]
        assert "0-100 bar" in result["pages"][0]["text"]
        assert "chunk_id" in result["pages"][0]
        
        # Check page 2
        assert result["pages"][1]["page_number"] == 2
        assert "-40°C" in result["pages"][1]["text"]
        assert "4-20mA" in result["pages"][1]["text"]
        assert "chunk_id" in result["pages"][1]

    def test_extract_text_from_nonexistent_pdf(self):
        """Test extracting text from a non-existent file raises PDFExtractionError."""
        with pytest.raises(PDFExtractionError):
            PDFExtractor.extract_text_from_pdf("nonexistent_file.pdf")

    def test_extract_text_from_corrupted_pdf(self, corrupted_pdf):
        """Test extracting text from a corrupted PDF raises PDFExtractionError."""
        with pytest.raises(PDFExtractionError):
            PDFExtractor.extract_text_from_pdf(corrupted_pdf)

    def test_validate_pdf(self, sample_pdf, corrupted_pdf):
        """Test PDF validation method."""
        assert PDFExtractor.validate_pdf(sample_pdf) is True
        assert PDFExtractor.validate_pdf(corrupted_pdf) is False
        assert PDFExtractor.validate_pdf("nonexistent.pdf") is False

    def test_extract_pdf_metadata(self, sample_pdf):
        """Test extracting PDF metadata."""
        metadata = PDFExtractor.extract_pdf_metadata(sample_pdf)
        assert metadata["total_pages"] == 2


class TestIngestionService:
    """Test IngestionService."""

    def test_create_ingestion_job(self, test_db):
        """Test creating an ingestion job."""
        job = IngestionService.create_ingestion_job(
            test_db, "Test PDF Job", "pdf"
        )
        assert job.id is not None
        assert job.job_name == "Test PDF Job"
        assert job.status == "pending"
        assert job.source_type == "pdf"

    def test_process_pdf_file_service(self, test_db, sample_pdf):
        """Test processing PDF file through IngestionService."""
        job = IngestionService.create_ingestion_job(
            test_db, "Test PDF Job", "pdf"
        )
        
        raw_source = IngestionService.process_pdf_file(
            test_db, job.id, sample_pdf, "test_datasheet.pdf"
        )
        
        assert raw_source is not None
        assert raw_source.job_id == job.id
        assert raw_source.file_name == "test_datasheet.pdf"
        assert "PT-100" in raw_source.raw_text_content
        
        # Check evidence chunks created
        chunks = test_db.query(EvidenceChunk).filter(
            EvidenceChunk.source_id == raw_source.id
        ).all()
        
        assert len(chunks) == 2
        assert chunks[0].page_number == 1
        assert chunks[1].page_number == 2
        assert "PT-100" in chunks[0].snippet_text
        assert "-40°C" in chunks[1].snippet_text


class TestIngestionAPI:
    """Test Ingestion API endpoints."""

    def test_upload_pdf_endpoint(self, client, test_db, sample_pdf):
        """Test uploading a valid PDF through API."""
        def override_get_db():
            try:
                yield test_db
            finally:
                pass
                
        app.dependency_overrides[get_db] = override_get_db
        
        with open(sample_pdf, "rb") as f:
            response = client.post(
                "/api/v1/ingest/upload-pdf?job_name=API+Test+Upload",
                files={"file": ("test_datasheet.pdf", f, "application/pdf")},
            )
            
        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "test_datasheet.pdf"
        assert data["status"] == "completed"
        assert data["total_pages"] == 2
        assert data["chunks_created"] == 2
        assert "job_id" in data
        
        # Verify job details endpoint
        job_id = data["job_id"]
        details_response = client.get(f"/api/v1/ingest/jobs/{job_id}")
        assert details_response.status_code == 200
        details = details_response.json()
        assert details["job_name"] == "API Test Upload"
        assert details["source_count"] == 1
        assert details["total_chunks"] == 2

    def test_upload_non_pdf_endpoint(self, client, test_db):
        """Test uploading a non-PDF file returns 400 error."""
        def override_get_db():
            try:
                yield test_db
            finally:
                pass
                
        app.dependency_overrides[get_db] = override_get_db
        
        response = client.post(
            "/api/v1/ingest/upload-pdf",
            files={"file": ("test.txt", b"some text content", "text/plain")},
            data={"job_name": "Text Upload"},
        )
        
        assert response.status_code == 400
        assert "Only PDF files are supported" in response.json()["detail"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
