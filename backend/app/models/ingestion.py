"""Ingestion-related SQLAlchemy models."""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class IngestionJob(Base):
    """Tracks batch uploads of PDFs, URLs, or CSV files."""
    __tablename__ = "ingestion_jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    job_name = Column(String(255), nullable=False)
    status = Column(String(50), default="pending")  # pending, processing, completed, failed
    source_type = Column(String(50), nullable=False)  # pdf, url, csv
    created_at = Column(DateTime, default=datetime.utcnow)
    
    sources = relationship("RawDocumentSource", back_populates="job", cascade="all, delete-orphan")


class RawDocumentSource(Base):
    """Stores individual files or URLs associated with an ingestion job."""
    __tablename__ = "raw_document_sources"
    
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("ingestion_jobs.id"))
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=True)
    source_url = Column(String(500), nullable=True)
    raw_text_content = Column(Text, nullable=True)
    parsed_at = Column(DateTime, default=datetime.utcnow)
    
    job = relationship("IngestionJob", back_populates="sources")
    evidence = relationship("EvidenceChunk", back_populates="source")
