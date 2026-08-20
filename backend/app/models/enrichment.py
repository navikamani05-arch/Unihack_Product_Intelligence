"""Additive ORM models for the Phase 6 enrichment pipeline."""
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class EnrichmentRun(Base):
    """Stores one source-backed enrichment analysis of an existing product."""

    __tablename__ = "enrichment_runs"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("product_records.id"), nullable=False, index=True)
    batch_id = Column(Integer, ForeignKey("enrichment_batches.id"), nullable=True, index=True)
    status = Column(String(50), nullable=False, default="queued", index=True)
    stage = Column(String(80), nullable=False, default="queued", index=True)
    overall_confidence = Column(Float, nullable=True)
    product_status = Column(String(50), nullable=True, index=True)
    category = Column(String(255), nullable=True)
    category_path = Column(JSON, nullable=True)
    category_confidence = Column(Float, nullable=True)
    product_understanding = Column(JSON, nullable=True)
    schema_snapshot = Column(JSON, nullable=True)
    output_snapshot = Column(JSON, nullable=True)
    missing_attributes = Column(JSON, nullable=True)
    progress_log = Column(JSON, nullable=True)
    source_count = Column(Integer, nullable=False, default=0)
    evidence_count = Column(Integer, nullable=False, default=0)
    attribute_count = Column(Integer, nullable=False, default=0)
    conflict_count = Column(Integer, nullable=False, default=0)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    product = relationship("ProductRecord")
    batch = relationship("EnrichmentBatch", back_populates="runs")


class EnrichmentBatch(Base):
    """Tracks bounded, resumable batches without requiring concurrent processing."""

    __tablename__ = "enrichment_batches"

    id = Column(Integer, primary_key=True, index=True)
    status = Column(String(50), nullable=False, default="queued", index=True)
    total_products = Column(Integer, nullable=False, default=0)
    processed_count = Column(Integer, nullable=False, default=0)
    successful_count = Column(Integer, nullable=False, default=0)
    failed_count = Column(Integer, nullable=False, default=0)
    review_count = Column(Integer, nullable=False, default=0)
    requested_product_ids = Column(JSON, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    runs = relationship("EnrichmentRun", back_populates="batch")


class EnrichmentReviewDecision(Base):
    """Records a human decision without changing source evidence or extracted values."""

    __tablename__ = "enrichment_review_decisions"

    id = Column(Integer, primary_key=True, index=True)
    enrichment_run_id = Column(Integer, ForeignKey("enrichment_runs.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("product_records.id"), nullable=False, index=True)
    attribute_id = Column(Integer, ForeignKey("product_attributes.id"), nullable=True, index=True)
    decision = Column(String(50), nullable=False, index=True)
    reviewer_value = Column(String(1000), nullable=True)
    reason = Column(Text, nullable=True)
    evidence_snapshot = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    run = relationship("EnrichmentRun")
    product = relationship("ProductRecord")
    attribute = relationship("ProductAttribute")


__all__ = ["EnrichmentRun", "EnrichmentBatch", "EnrichmentReviewDecision"]
