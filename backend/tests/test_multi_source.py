"""Tests for Website and CSV extraction and multi-source ingestion service."""
import pytest
import io
import pandas as pd
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.database import Base
from app.services.website_extractor import WebsiteExtractor, WebsiteExtractionError
from app.services.csv_extractor import CSVExtractor, CSVExtractionError
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


class TestWebsiteExtractor:
    """Test WebsiteExtractor service."""

    def test_validate_url(self):
        """Test URL validation."""
        assert WebsiteExtractor.validate_url("https://example.com/product") is True
        assert WebsiteExtractor.validate_url("http://example.com") is True
        assert WebsiteExtractor.validate_url("ftp://example.com") is False
        assert WebsiteExtractor.validate_url("invalid-url") is False

    def test_extract_content_from_html(self):
        """Test extracting content from HTML."""
        html = """
        <html>
            <head><title>Test Product Page</title></head>
            <body>
                <script>console.log('ads');</script>
                <h1>Industrial Pressure Transmitter</h1>
                <p>This is a high quality pressure transmitter designed for industrial applications with 24V DC power supply.</p>
                <ul>
                    <li>Voltage: 24V DC</li>
                    <li>Pressure Range: 0-100 bar</li>
                </ul>
            </body>
        </html>
        """
        result = WebsiteExtractor.extract_content_from_html(html, "https://example.com/product")
        
        assert result["url"] == "https://example.com/product"
        assert result["title"] == "Test Product Page"
        assert "Industrial Pressure Transmitter" in result["text"]
        assert "24V DC" in result["text"]
        assert len(result["chunks"]) > 0
        assert result["error"] is None

    def test_extract_content_empty_html(self):
        """Test extracting content from empty or script-only HTML."""
        html = "<html><head><title>Empty</title></head><body><script>alert(1);</script></body></html>"
        # Should raise or return chunks
        try:
            WebsiteExtractor.extract_content_from_html(html, "https://example.com/empty")
        except WebsiteExtractionError:
            pass


class TestCSVExtractor:
    """Test CSVExtractor service."""

    def test_validate_csv(self):
        """Test CSV validation."""
        valid_csv = b"SKU,Name,Price\nSKU001,Product A,100\n"
        invalid_csv = b""
        
        assert CSVExtractor.validate_csv(valid_csv) is True

    def test_extract_csv_data_standard(self):
        """Test extracting data from standard CSV with product columns."""
        csv_content = b"SKU,Product Name,Brand,Price,Voltage\nPT-100,Pressure Transmitter,Omega,250.0,24V\nPT-200,Digital Gauge,Fluke,150.0,12V\n"
        result = CSVExtractor.extract_csv_data(csv_content, "products.csv")
        
        assert result["filename"] == "products.csv"
        assert result["total_rows"] == 2
        assert "SKU" in result["columns"]
        assert "Product Name" in result["columns"]
        assert len(result["rows"]) == 2
        
        # Check row 1
        assert result["rows"][0]["row_number"] == 1
        assert result["rows"][0]["values"]["SKU"] == "PT-100"
        assert result["rows"][0]["values"]["Brand"] == "Omega"
        
        # Check row 2
        assert result["rows"][1]["row_number"] == 2
        assert result["rows"][1]["values"]["SKU"] == "PT-200"

    def test_extract_csv_data_different_columns(self):
        """Test extracting data from CSV with non-standard columns."""
        csv_content = b"PartCode,ItemTitle,Manufacturer,Cost\nXYZ-1,Widget A,Acme,45.50\n"
        result = CSVExtractor.extract_csv_data(csv_content, "custom.csv")
        
        assert result["total_rows"] == 1
        assert "PartCode" in result["columns"]
        
        # Test column detection
        detected = CSVExtractor.detect_product_columns(result["columns"])
        assert detected["sku"] == "PartCode"
        assert detected["name"] == "ItemTitle"
        assert detected["brand"] == "Manufacturer"

    def test_extract_empty_csv(self):
        """Test extracting empty CSV raises CSVExtractionError."""
        with pytest.raises(CSVExtractionError):
            CSVExtractor.extract_csv_data(b"", "empty.csv")

    def test_row_to_text(self):
        """Test converting CSV row to text."""
        row_dict = {"SKU": "PT-100", "Name": "Transmitter", "Price": 250}
        columns = ["SKU", "Name", "Price"]
        text = CSVExtractor.row_to_text(row_dict, columns)
        
        assert "SKU: PT-100" in text
        assert "Name: Transmitter" in text
        assert "Price: 250" in text


class TestMultiSourceIngestionService:
    """Test IngestionService with Website and CSV."""

    def test_process_csv_file_service(self, test_db, tmp_path):
        """Test processing CSV file through IngestionService."""
        csv_path = tmp_path / "test_catalog.csv"
        csv_path.write_text("SKU,Name,Price\nSKU-1,Widget 1,99.99\nSKU-2,Widget 2,149.99\n")
        
        job = IngestionService.create_ingestion_job(test_db, "CSV Job", "csv")
        
        raw_source = IngestionService.process_csv_file(
            test_db, job.id, str(csv_path), "test_catalog.csv"
        )
        
        assert raw_source is not None
        assert raw_source.job_id == job.id
        assert raw_source.file_name == "test_catalog.csv"
        
        # Check evidence chunks created for each row
        chunks = test_db.query(EvidenceChunk).filter(
            EvidenceChunk.source_id == raw_source.id
        ).all()
        
        assert len(chunks) == 2
        assert chunks[0].page_number == 1
        assert "SKU-1" in chunks[0].snippet_text
        assert chunks[1].page_number == 2
        assert "SKU-2" in chunks[1].snippet_text


class TestMultiSourceAPI:
    """Test Multi-Source API endpoints."""

    def test_upload_csv_endpoint(self, client, test_db, tmp_path):
        """Test uploading CSV through API."""
        def override_get_db():
            try:
                yield test_db
            finally:
                pass
                
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db
        
        csv_path = tmp_path / "api_catalog.csv"
        csv_path.write_text("SKU,Name,Price\nAPI-1,Sensor A,299.99\n")

        with open(csv_path, "rb") as f:
            response = client.post(
                "/api/v1/ingest/upload-csv?job_name=API+CSV+Upload",
                files={"file": ("api_catalog.csv", f, "text/csv")},
            )
            
        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "api_catalog.csv"
        assert data["status"] == "completed"
        assert data["chunks_created"] == 1
        assert "job_id" in data

    def test_upload_invalid_csv_endpoint(self, client, test_db):
        """Test uploading non-CSV file returns 400 error."""
        def override_get_db():
            try:
                yield test_db
            finally:
                pass
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db

        response = client.post(
            "/api/v1/ingest/upload-csv",
            files={"file": ("test.pdf", b"not a csv", "application/pdf")},
        )
        
        assert response.status_code == 400
        assert "Only CSV files are supported" in response.json()["detail"]

    def test_upload_invalid_url_endpoint(self, client, test_db):
        """Test uploading invalid URL returns 400 error."""
        def override_get_db():
            try:
                yield test_db
            finally:
                pass
        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db

        response = client.post(
            "/api/v1/ingest/upload-website?url=invalid-url",
        )
        
        assert response.status_code == 400
        assert "URL must start with http://" in response.json()["detail"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
