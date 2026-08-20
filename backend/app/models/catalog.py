"""Phase 9 catalog upload, validation, and bounded processing models."""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class CatalogBatch(Base):
    __tablename__ = "catalog_batches"

    id = Column(Integer, primary_key=True, index=True)
    dataset_name = Column(String(255), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    source_type = Column(String(20), nullable=False)
    detected_columns = Column(JSON, nullable=True)
    total_items = Column(Integer, nullable=False, default=0)
    queued_items = Column(Integer, nullable=False, default=0)
    processed_items = Column(Integer, nullable=False, default=0)
    successful_items = Column(Integer, nullable=False, default=0)
    review_items = Column(Integer, nullable=False, default=0)
    failed_items = Column(Integer, nullable=False, default=0)
    invalid_items = Column(Integer, nullable=False, default=0)
    status = Column(String(30), nullable=False, default="QUEUED", index=True)
    error_summary = Column(JSON, nullable=True)
    configuration_snapshot = Column(JSON, nullable=True)
    cancellation_requested = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    items = relationship("CatalogItem", back_populates="batch", cascade="all, delete-orphan")


class CatalogItem(Base):
    __tablename__ = "catalog_items"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("catalog_batches.id"), nullable=False, index=True)
    row_number = Column(Integer, nullable=False, index=True)
    identifier = Column(String(255), nullable=True, index=True)
    input_snapshot = Column(JSON, nullable=False)
    validation_status = Column(String(30), nullable=False, default="VALID", index=True)
    validation_errors = Column(JSON, nullable=True)
    validation_warnings = Column(JSON, nullable=True)
    processing_status = Column(String(30), nullable=False, default="QUEUED", index=True)
    error_message = Column(Text, nullable=True)
    product_id = Column(Integer, ForeignKey("product_records.id"), nullable=True, index=True)
    enrichment_run_id = Column(Integer, ForeignKey("enrichment_runs.id"), nullable=True, index=True)
    commerce_output_id = Column(Integer, ForeignKey("commerce_outputs.id"), nullable=True, index=True)
    result_status = Column(String(50), nullable=True, index=True)
    attempt_count = Column(Integer, nullable=False, default=0)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    batch = relationship("CatalogBatch", back_populates="items")
    product = relationship("ProductRecord")
    enrichment_run = relationship("EnrichmentRun")
    commerce_output = relationship("CommerceOutput")


__all__ = ["CatalogBatch", "CatalogItem"]
