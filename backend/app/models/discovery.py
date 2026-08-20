"""Persisted, source-auditable Phase 7 discovery records."""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class DiscoveryRun(Base):
    """One bounded source-discovery attempt for one existing product."""

    __tablename__ = "discovery_runs"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("product_records.id"), nullable=False, index=True)
    status = Column(String(50), nullable=False, default="pending", index=True)
    mode = Column(String(50), nullable=False, default="DISCOVERY_ENABLED")
    provider_name = Column(String(100), nullable=True)
    provider_status = Column(String(100), nullable=True)
    max_queries = Column(Integer, nullable=False, default=4)
    max_results_per_query = Column(Integer, nullable=False, default=5)
    max_sources = Column(Integer, nullable=False, default=8)
    max_fetches = Column(Integer, nullable=False, default=5)
    query_count = Column(Integer, nullable=False, default=0)
    discovered_count = Column(Integer, nullable=False, default=0)
    verified_count = Column(Integer, nullable=False, default=0)
    rejected_count = Column(Integer, nullable=False, default=0)
    fetch_failed_count = Column(Integer, nullable=False, default=0)
    evidence_count = Column(Integer, nullable=False, default=0)
    conflict_count = Column(Integer, nullable=False, default=0)
    summary = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    product = relationship("ProductRecord")
    queries = relationship("DiscoveryQuery", back_populates="run", cascade="all, delete-orphan")
    sources = relationship("CandidateSource", back_populates="run", cascade="all, delete-orphan")
    evidence = relationship("DiscoveryEvidence", back_populates="run", cascade="all, delete-orphan")


class DiscoveryQuery(Base):
    """A concise, deterministic discovery query and its user-visible reason."""

    __tablename__ = "discovery_queries"

    id = Column(Integer, primary_key=True, index=True)
    discovery_run_id = Column(Integer, ForeignKey("discovery_runs.id"), nullable=False, index=True)
    query_text = Column(String(1000), nullable=False)
    reason = Column(Text, nullable=False)
    provider_name = Column(String(100), nullable=True)
    status = Column(String(50), nullable=False, default="pending")
    result_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    run = relationship("DiscoveryRun", back_populates="queries")
    sources = relationship("CandidateSource", back_populates="query")


class CandidateSource(Base):
    """A candidate URL returned by a provider or supplied explicitly by the user."""

    __tablename__ = "candidate_sources"

    id = Column(Integer, primary_key=True, index=True)
    discovery_run_id = Column(Integer, ForeignKey("discovery_runs.id"), nullable=False, index=True)
    discovery_query_id = Column(Integer, ForeignKey("discovery_queries.id"), nullable=True, index=True)
    url = Column(String(2048), nullable=False)
    canonical_url = Column(String(2048), nullable=False, index=True)
    url_hash = Column(String(128), nullable=False, index=True)
    title = Column(String(1000), nullable=True)
    domain = Column(String(255), nullable=True, index=True)
    source_type = Column(String(50), nullable=False, default="web")
    authority_tier = Column(String(50), nullable=False, default="TIER_3_UNKNOWN")
    identity_score = Column(Float, nullable=True)
    quality_score = Column(Float, nullable=True)
    rank = Column(Integer, nullable=True)
    status = Column(String(50), nullable=False, default="candidate", index=True)
    rejection_reason = Column(Text, nullable=True)
    user_provided = Column(Boolean, nullable=False, default=False)
    metadata_snapshot = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    run = relationship("DiscoveryRun", back_populates="sources")
    query = relationship("DiscoveryQuery", back_populates="sources")
    fetches = relationship("SourceFetch", back_populates="source", cascade="all, delete-orphan")
    evidence = relationship("DiscoveryEvidence", back_populates="source", cascade="all, delete-orphan")


class SourceFetch(Base):
    """An auditable bounded fetch result; text is retained only after URL validation."""

    __tablename__ = "source_fetches"

    id = Column(Integer, primary_key=True, index=True)
    candidate_source_id = Column(Integer, ForeignKey("candidate_sources.id"), nullable=False, index=True)
    status = Column(String(50), nullable=False, default="pending")
    final_url = Column(String(2048), nullable=True)
    http_status = Column(Integer, nullable=True)
    content_type = Column(String(255), nullable=True)
    byte_count = Column(Integer, nullable=True)
    page_count = Column(Integer, nullable=True)
    extracted_text = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    fetched_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    source = relationship("CandidateSource", back_populates="fetches")
    evidence = relationship("DiscoveryEvidence", back_populates="fetch")


class DiscoveryEvidence(Base):
    """Exact discovery evidence bound to one product, source, fetch, and optional attribute."""

    __tablename__ = "discovery_evidence"

    id = Column(Integer, primary_key=True, index=True)
    discovery_run_id = Column(Integer, ForeignKey("discovery_runs.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("product_records.id"), nullable=False, index=True)
    candidate_source_id = Column(Integer, ForeignKey("candidate_sources.id"), nullable=False, index=True)
    source_fetch_id = Column(Integer, ForeignKey("source_fetches.id"), nullable=False, index=True)
    attribute_name = Column(String(255), nullable=True, index=True)
    raw_value = Column(Text, nullable=True)
    normalized_value = Column(Text, nullable=True)
    quote = Column(Text, nullable=False)
    page_number = Column(Integer, nullable=True)
    extraction_method = Column(String(100), nullable=False, default="exact_text_match")
    evidence_quality = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    run = relationship("DiscoveryRun", back_populates="evidence")
    source = relationship("CandidateSource", back_populates="evidence")
    fetch = relationship("SourceFetch", back_populates="evidence")
    product = relationship("ProductRecord")
