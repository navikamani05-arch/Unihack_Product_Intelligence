"""Persistent background extraction-task model."""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text

from app.database import Base


class ExtractionJob(Base):
    """Tracks one background extraction run for an ingestion job."""

    __tablename__ = "extraction_jobs"

    id = Column(Integer, primary_key=True, index=True)
    ingestion_job_id = Column(Integer, ForeignKey("ingestion_jobs.id"), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="QUEUED", index=True)
    current_batch = Column(Integer, nullable=False, default=0)
    total_batches = Column(Integer, nullable=False, default=0)
    processed_evidence_count = Column(Integer, nullable=False, default=0)
    total_evidence_count = Column(Integer, nullable=False, default=0)
    extracted_product_count = Column(Integer, nullable=False, default=0)
    error_message = Column(Text, nullable=True)
    cancellation_requested = Column(Boolean, nullable=False, default=False)
    result_snapshot = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


__all__ = ["ExtractionJob"]

