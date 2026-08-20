"""Product-related SQLAlchemy models."""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class ProductRecord(Base):
    """Represents the master product entity normalized across sources."""

    __tablename__ = "product_records"

    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String(100), unique=True, index=True, nullable=True)
    sku_evidence_chunk_id = Column(String(128), nullable=True, index=True)
    sku_source_type = Column(String(50), nullable=True)
    sku_source_identifier = Column(String(500), nullable=True)
    sku_source_url = Column(String(500), nullable=True)
    sku_page_number = Column(Integer, nullable=True)
    sku_row_number = Column(Integer, nullable=True)
    name = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=True)
    manufacturer = Column(String(255), nullable=True)
    status = Column(String(50), default="draft")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    attributes = relationship(
        "ProductAttribute", back_populates="product", cascade="all, delete-orphan"
    )
    conflicts = relationship(
        "DataConflict", back_populates="product", cascade="all, delete-orphan"
    )
    trust_metric = relationship(
        "TrustMetric", back_populates="product", uselist=False, cascade="all, delete-orphan"
    )


class ProductAttribute(Base):
    """Stores an extracted attribute and where its value came from."""

    __tablename__ = "product_attributes"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("product_records.id"))
    attribute_name = Column(String(100), nullable=False)
    raw_value = Column(String(255), nullable=True)
    normalized_value = Column(String(255), nullable=True)
    unit = Column(String(50), nullable=True)
    confidence_score = Column(Float, default=0.0)
    is_verified = Column(Boolean, default=False)

    source_type = Column(String(50), nullable=True)
    source_identifier = Column(String(500), nullable=True)
    source_url = Column(String(500), nullable=True)
    page_number = Column(Integer, nullable=True)
    row_number = Column(Integer, nullable=True)
    evidence_chunk_id = Column(String(128), nullable=True, index=True)

    product = relationship("ProductRecord", back_populates="attributes")
    evidence_chunks = relationship(
        "EvidenceChunk", back_populates="attribute", cascade="all, delete-orphan"
    )
