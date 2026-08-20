"""Tests for SQLAlchemy ORM models."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models.ingestion import IngestionJob, RawDocumentSource
from app.models.product import ProductRecord, ProductAttribute
from app.models.conflict import DataConflict, EvidenceChunk
from app.models.trust import TrustMetric


@pytest.fixture
def test_db():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    yield db
    db.close()


class TestIngestionJob:
    """Test IngestionJob model."""

    def test_create_ingestion_job(self, test_db):
        """Test creating an ingestion job."""
        job = IngestionJob(
            job_name="Test Ingestion",
            status="pending",
            source_type="pdf",
        )
        test_db.add(job)
        test_db.commit()
        test_db.refresh(job)
        
        assert job.id is not None
        assert job.job_name == "Test Ingestion"
        assert job.status == "pending"
        assert job.source_type == "pdf"


class TestProductRecord:
    """Test ProductRecord model."""

    def test_create_product_record(self, test_db):
        """Test creating a product record."""
        product = ProductRecord(
            sku="SENSOR-001",
            name="Industrial Temperature Sensor",
            category="Sensors",
            manufacturer="Acme Corp",
            status="draft",
        )
        test_db.add(product)
        test_db.commit()
        test_db.refresh(product)
        
        assert product.id is not None
        assert product.sku == "SENSOR-001"
        assert product.name == "Industrial Temperature Sensor"
        assert product.category == "Sensors"
        assert product.status == "draft"

    def test_product_sku_uniqueness(self, test_db):
        """Test that SKU must be unique."""
        product1 = ProductRecord(
            sku="SENSOR-001",
            name="Sensor 1",
            category="Sensors",
        )
        product2 = ProductRecord(
            sku="SENSOR-001",
            name="Sensor 2",
            category="Sensors",
        )
        test_db.add(product1)
        test_db.commit()
        test_db.add(product2)
        
        with pytest.raises(Exception):  # SQLAlchemy will raise IntegrityError
            test_db.commit()


class TestProductAttribute:
    """Test ProductAttribute model."""

    def test_create_product_attribute(self, test_db):
        """Test creating a product attribute."""
        product = ProductRecord(
            sku="SENSOR-001",
            name="Sensor",
            category="Sensors",
        )
        test_db.add(product)
        test_db.commit()
        test_db.refresh(product)
        
        attribute = ProductAttribute(
            product_id=product.id,
            attribute_name="rated_voltage",
            raw_value="230V",
            normalized_value="230",
            unit="V",
            confidence_score=0.95,
        )
        test_db.add(attribute)
        test_db.commit()
        test_db.refresh(attribute)
        
        assert attribute.id is not None
        assert attribute.attribute_name == "rated_voltage"
        assert attribute.confidence_score == 0.95


class TestTrustMetric:
    """Test TrustMetric model."""

    def test_create_trust_metric(self, test_db):
        """Test creating a trust metric."""
        product = ProductRecord(
            sku="SENSOR-001",
            name="Sensor",
            category="Sensors",
        )
        test_db.add(product)
        test_db.commit()
        test_db.refresh(product)
        
        trust = TrustMetric(
            product_id=product.id,
            trust_score=85.5,
            completeness_percentage=90.0,
            conflict_count=1,
            provenance_score=80.0,
            ml_readiness_probability=0.75,
        )
        test_db.add(trust)
        test_db.commit()
        test_db.refresh(trust)
        
        assert trust.id is not None
        assert trust.trust_score == 85.5
        assert trust.ml_readiness_probability == 0.75


class TestDataConflict:
    """Test DataConflict model."""

    def test_create_data_conflict(self, test_db):
        """Test creating a data conflict."""
        product = ProductRecord(
            sku="SENSOR-001",
            name="Sensor",
            category="Sensors",
        )
        test_db.add(product)
        test_db.commit()
        test_db.refresh(product)
        
        conflict = DataConflict(
            product_id=product.id,
            attribute_name="rated_voltage",
            source_a_name="datasheet.pdf",
            source_a_value="230V",
            source_b_name="catalog.csv",
            source_b_value="220V",
            resolution_status="unresolved",
        )
        test_db.add(conflict)
        test_db.commit()
        test_db.refresh(conflict)
        
        assert conflict.id is not None
        assert conflict.resolution_status == "unresolved"
        assert conflict.source_a_value == "230V"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
