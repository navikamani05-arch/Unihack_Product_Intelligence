"""Regression tests for Phase 2C CSV extraction."""
import json
import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import settings
from app.main import app
from app.database import Base, get_db
from app.services.llm_extraction_service import LLMExtractionService
from app.models.ingestion import IngestionJob, RawDocumentSource
from app.models.conflict import EvidenceChunk
from app.models.product import ProductRecord, ProductAttribute

@pytest.fixture
def test_db():
    """Create a temporary SQLite database for testing."""
    db_path = "/home/ubuntu/ai-product-intelligence/backend/test_regression.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    app.dependency_overrides[get_db] = override_get_db
    db = SessionLocal()
    yield db
    db.close()
    app.dependency_overrides.clear()
    if os.path.exists(db_path):
        os.remove(db_path)

@pytest.fixture
def client():
    return TestClient(app)

class FakeLLMClient:
    def __init__(self, response_content):
        self.response_content = response_content
        self.request = None

    class Choices:
        def __init__(self, content):
            self.message = type('obj', (object,), {'content': content})

    def create(self, **kwargs):
        self.request = kwargs
        return type('obj', (object,), {'choices': [self.Choices(self.response_content)]})

    @property
    def chat(self):
        return type('obj', (object,), {'completions': self})

def test_csv_multi_product_extraction(client, test_db, monkeypatch):
    # This fixture returns all ten products from one mocked provider response.
    # Pin the batch size so the test focuses on CSV row/provenance behavior.
    monkeypatch.setattr(settings, "llm_batch_size", 50)
    # 1. Setup mock CSV job with 10 rows
    job = IngestionJob(job_name="CSV Regression Test", source_type="csv", status="completed")
    test_db.add(job)
    test_db.flush()
    
    source = RawDocumentSource(job_id=job.id, file_name="product_catalog.csv")
    test_db.add(source)
    test_db.flush()
    
    # Create 10 chunks representing 10 products
    for i in range(1, 11):
        chunk = EvidenceChunk(
            job_id=job.id,
            source_id=source.id,
            source_type="csv",
            source_identifier="product_catalog.csv",
            row_number=i,
            snippet_text=f"Product Name: Product {i}\nSKU: SKU-{i}\nVoltage: 400V\nPower: 5.5 kW\nMaterial: Cast Iron\nPrice: 25000",
            stable_chunk_id=f"csv_row_{i}"
        )
        test_db.add(chunk)
    test_db.commit()
    
    # 2. Mock LLM to return 10 products
    products = []
    for i in range(1, 11):
        products.append({
            "product_name": f"Product {i}",
            "sku": f"SKU-{i}",
            "brand": "Siemens",
            "category": "Motor",
            "description": f"Description {i}",
            "attributes": [
                {"attribute_name": "voltage", "raw_value": "400V", "normalized_value": "400", "unit": "V", "confidence_score": 0.95, "evidence_chunk_id": f"csv_row_{i}", "row_number": i, "page_number": None},
                {"attribute_name": "power", "raw_value": "5.5 kW", "normalized_value": "5.5", "unit": "kW", "confidence_score": 0.95, "evidence_chunk_id": f"csv_row_{i}", "row_number": i, "page_number": None},
                {"attribute_name": "material", "raw_value": "Cast Iron", "normalized_value": "Cast Iron", "unit": None, "confidence_score": 0.95, "evidence_chunk_id": f"csv_row_{i}", "row_number": i, "page_number": None},
                {"attribute_name": "price", "raw_value": "25000", "normalized_value": "25000", "unit": None, "confidence_score": 0.95, "evidence_chunk_id": f"csv_row_{i}", "row_number": i, "page_number": None}
            ],
            "missing_attributes": []
        })
    
    fake_response = json.dumps({"products": products})
    fake_client = FakeLLMClient(fake_response)
    monkeypatch.setattr(LLMExtractionService, "get_client", classmethod(lambda cls: fake_client))
    
    # 3. Call extraction API
    response = client.post(f"/api/v1/extract/{job.id}?wait=true")
    assert response.status_code == 200
    data = response.json()
    
    # 4. Verify results
    assert len(data["product_ids"]) == 10
    assert len(data["extracted_products"]) == 10
    
    # Check Row 1 values
    p1 = data["extracted_products"][0]
    assert p1["product_name"] == "Product 1"
    
    attrs = {a["attribute_name"]: a for a in p1["attributes"]}
    assert attrs["voltage"]["raw_value"] == "400V"
    assert attrs["power"]["raw_value"] == "5.5 kW"
    assert attrs["material"]["raw_value"] == "Cast Iron"
    assert attrs["price"]["raw_value"] == "25000"
    
    # Verify database persistence
    db_products = test_db.query(ProductRecord).all()
    assert len(db_products) == 10
    
    db_p1 = test_db.query(ProductRecord).filter(ProductRecord.sku == "SKU-1").first()
    assert db_p1 is not None
    assert len(db_p1.attributes) == 4
    
    # Check provenance in DB
    v_attr = test_db.query(ProductAttribute).filter(
        ProductAttribute.product_id == db_p1.id, 
        ProductAttribute.attribute_name == "voltage"
    ).first()
    assert v_attr.row_number == 1
    assert v_attr.source_identifier == "product_catalog.csv"
