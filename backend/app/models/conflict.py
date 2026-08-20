"""Conflict and evidence tracking SQLAlchemy models."""
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class EvidenceChunk(Base):
    """Stores source text snippets linked to extracted attributes."""

    __tablename__ = "evidence_chunks"

    id = Column(Integer, primary_key=True, index=True)
    # Stable external identifier used in LLM output and provenance responses.
    stable_chunk_id = Column(String(128), unique=True, index=True, nullable=True)
    job_id = Column(Integer, ForeignKey("ingestion_jobs.id"), nullable=True, index=True)
    attribute_id = Column(Integer, ForeignKey("product_attributes.id"), nullable=True)
    source_id = Column(Integer, ForeignKey("raw_document_sources.id"), nullable=False)
    snippet_text = Column(Text, nullable=False)
    page_number = Column(Integer, nullable=True)
    row_number = Column(Integer, nullable=True)
    source_type = Column(String(50), nullable=True)
    source_identifier = Column(String(500), nullable=True)
    source_url = Column(String(500), nullable=True)
    bounding_box = Column(JSON, nullable=True)

    attribute = relationship("ProductAttribute", back_populates="evidence_chunks")
    source = relationship("RawDocumentSource", back_populates="evidence")
    job = relationship("IngestionJob")


class DataConflict(Base):
    """Records attribute discrepancies between multiple sources for the same product."""

    __tablename__ = "data_conflicts"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("product_records.id"))
    # Phase 3B additions: a conflict is scoped to one investigation and retains only a compact
    # summary. Source evidence remains in the existing EvidenceChunk/ProductAttribute records.
    investigation_id = Column(Integer, ForeignKey("product_investigations.id"), nullable=True, index=True)
    attribute_name = Column(String(100), nullable=False)
    conflict_type = Column(String(50), nullable=True, index=True)
    severity = Column(String(20), nullable=True, index=True)
    status = Column(String(50), nullable=True, index=True)
    agreement_count = Column(Integer, nullable=True)
    total_sources = Column(Integer, nullable=True)
    agreement_percentage = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    # Immutable-at-detection evidence snapshot supports detail, filters, and human review
    # even after a subsequent conflict-report refresh.
    evidence_snapshot = Column(JSON, nullable=True)
    suggested_value = Column(String(255), nullable=True)
    suggestion_reason = Column(Text, nullable=True)
    source_authority_summary = Column(JSON, nullable=True)
    resolution_action = Column(String(50), nullable=True)
    resolution_reason = Column(Text, nullable=True)
    source_a_name = Column(String(255), nullable=False)
    source_a_value = Column(String(255), nullable=False)
    source_b_name = Column(String(255), nullable=False)
    source_b_value = Column(String(255), nullable=False)
    resolution_status = Column(String(50), default="unresolved")
    resolved_value = Column(String(255), nullable=True)

    product = relationship("ProductRecord", back_populates="conflicts")
