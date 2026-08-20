"""Persistent, auditable commerce-ready output snapshots."""
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class CommerceOutput(Base):
    """One immutable-ish generated delivery snapshot for an enrichment run."""

    __tablename__ = "commerce_outputs"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("product_records.id"), nullable=False, index=True)
    enrichment_run_id = Column(Integer, ForeignKey("enrichment_runs.id"), nullable=False, index=True)
    output_version = Column(String(50), nullable=False, default="1.0")
    status = Column(String(50), nullable=False, default="REVIEW_REQUIRED", index=True)
    overall_confidence = Column(Float, nullable=True)
    validation_summary = Column(JSON, nullable=True)
    record_snapshot = Column(JSON, nullable=False)
    source_snapshot = Column(JSON, nullable=True)
    conflict_snapshot = Column(JSON, nullable=True)
    review_snapshot = Column(JSON, nullable=True)
    generated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    product = relationship("ProductRecord")
    enrichment_run = relationship("EnrichmentRun")
    fields = relationship("CommerceOutputField", back_populates="output", cascade="all, delete-orphan")


class CommerceOutputField(Base):
    """Field-level delivery value, validation, provenance, and review audit."""

    __tablename__ = "commerce_output_fields"

    id = Column(Integer, primary_key=True, index=True)
    commerce_output_id = Column(Integer, ForeignKey("commerce_outputs.id"), nullable=False, index=True)
    field_key = Column(String(255), nullable=False, index=True)
    display_name = Column(String(255), nullable=False)
    raw_value = Column(Text, nullable=True)
    normalized_value = Column(Text, nullable=True)
    output_value = Column(Text, nullable=True)
    unit = Column(String(100), nullable=True)
    field_status = Column(String(50), nullable=False, default="MISSING")
    validation_status = Column(String(80), nullable=False, default="NOT_EVALUATED")
    validation_explanation = Column(Text, nullable=True)
    reference_dataset = Column(String(255), nullable=True)
    character_limit = Column(Integer, nullable=True)
    character_limit_status = Column(String(50), nullable=False, default="UNAVAILABLE")
    confidence = Column(Float, nullable=True)
    evidence_snapshot = Column(JSON, nullable=True)
    provenance_status = Column(String(50), nullable=False, default="UNAVAILABLE")
    conflict_ids = Column(JSON, nullable=True)
    review_state = Column(String(50), nullable=False, default="NOT_REVIEWED")
    review_snapshot = Column(JSON, nullable=True)

    output = relationship("CommerceOutput", back_populates="fields")


__all__ = ["CommerceOutput", "CommerceOutputField"]
