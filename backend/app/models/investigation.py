"""SQLAlchemy models for source-scoped product investigations."""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class ProductInvestigation(Base):
    """A user-defined analysis workspace for one product across explicitly attached jobs."""

    __tablename__ = "product_investigations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, default="draft", index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    source_jobs = relationship(
        "InvestigationSourceJob",
        back_populates="investigation",
        cascade="all, delete-orphan",
        order_by="InvestigationSourceJob.created_at",
    )


class InvestigationSourceJob(Base):
    """Reference from an investigation to one completed ingestion job; evidence is never copied."""

    __tablename__ = "investigation_source_jobs"
    __table_args__ = (
        UniqueConstraint("investigation_id", "job_id", name="uq_investigation_source_job"),
    )

    id = Column(Integer, primary_key=True, index=True)
    investigation_id = Column(
        Integer,
        ForeignKey("product_investigations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id = Column(Integer, ForeignKey("ingestion_jobs.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    investigation = relationship("ProductInvestigation", back_populates="source_jobs")
    job = relationship("IngestionJob")
