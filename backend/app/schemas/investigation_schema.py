"""Pydantic schemas for source-scoped product investigations and matching."""
from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class InvestigationCreateRequest(BaseModel):
    """Create a named workspace for a product investigation."""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=4000)


class InvestigationDocumentSourceResponse(BaseModel):
    """A persisted source belonging to an attached ingestion job."""

    id: int
    filename: str
    source_url: Optional[str] = None


class InvestigationSourceJobResponse(BaseModel):
    """An explicit investigation-to-job attachment and its existing source metadata."""

    id: int
    job_id: int
    job_name: str
    status: str
    source_type: str
    source_count: int
    evidence_chunk_count: int
    sources: List[InvestigationDocumentSourceResponse] = Field(default_factory=list)
    attached_at: datetime


class InvestigationResponse(BaseModel):
    """Investigation detail, including only explicitly attached jobs."""

    id: int
    name: str
    description: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime
    source_jobs: List[InvestigationSourceJobResponse] = Field(default_factory=list)


class AvailableIngestionJobResponse(BaseModel):
    """A completed ingestion job eligible for attachment."""

    id: int
    job_name: str
    status: str
    source_type: str
    created_at: datetime
    source_count: int
    evidence_chunk_count: int


class IdentityFieldResponse(BaseModel):
    """One source-backed product identity value and its provenance."""

    field: str
    value: str
    source_type: Optional[str] = None
    source_identifier: Optional[str] = None
    source_url: Optional[str] = None
    page_number: Optional[int] = None
    row_number: Optional[int] = None
    evidence_chunk_id: Optional[str] = None


class SourceIdentityResponse(BaseModel):
    """Identity data inferred from one attached job without crossing job boundaries."""

    job_id: int
    source_type: str
    product_ids: List[int] = Field(default_factory=list)
    identity_fields: List[IdentityFieldResponse] = Field(default_factory=list)


class SourceAttributeValueResponse(BaseModel):
    """An extracted product attribute and its preserved source provenance."""

    job_id: int
    source_type: str
    attribute_name: str
    value: str
    unit: Optional[str] = None
    confidence_score: Optional[float] = None
    source_identifier: Optional[str] = None
    source_url: Optional[str] = None
    page_number: Optional[int] = None
    row_number: Optional[int] = None
    evidence_chunk_id: Optional[str] = None
    evidence_snippet: Optional[str] = None
    normalized_value: Optional[str] = None
    source_authority: Optional[str] = None


class AttributeConflictSummaryResponse(BaseModel):
    """Source-scoped agreement result for one dynamically extracted attribute."""

    attribute_name: str
    status: str
    severity: Optional[str] = None
    agreement_count: int = 0
    total_sources: int = 0
    agreement_percentage: float = 0.0
    missing_job_ids: List[int] = Field(default_factory=list)
    explanation: Optional[str] = None
    suggested_value: Optional[str] = None
    suggestion_reason: Optional[str] = None


class AttributeConflictResponse(AttributeConflictSummaryResponse):
    """A detected disagreement and all source-backed values needed for human review."""

    values: List[SourceAttributeValueResponse] = Field(default_factory=list)
    requires_review: bool = True
    conflict_id: Optional[int] = None
    resolution_status: str = "unresolved"
    resolution_action: Optional[str] = None
    resolution_reason: Optional[str] = None


class ConflictResolutionRequest(BaseModel):
    """A human decision that records review state without modifying source evidence."""

    action: str = Field(
        ..., pattern="^(ACCEPT_SOURCE_VALUE|ACCEPT_OTHER_VALUE|MARK_AS_UNRESOLVED|MARK_AS_HUMAN_REVIEW)$"
    )
    chosen_value: Optional[str] = None
    reasoning: Optional[str] = Field(default=None, max_length=4000)


class ConflictDetailResponse(AttributeConflictResponse):
    """Persisted conflict detail, including its original source-backed snapshot."""

    source_authority_summary: List[dict] = Field(default_factory=list)
    created_at: Optional[str] = None
    resolved_at: Optional[str] = None


class InvestigationConflictsResponse(BaseModel):
    """All detected conflicts plus non-conflicting summaries for an investigation."""

    investigation_id: int
    total_sources: int = 0
    conflict_count: int = 0
    conflicts: List[AttributeConflictResponse] = Field(default_factory=list)
    attribute_summaries: List[AttributeConflictSummaryResponse] = Field(default_factory=list)


class AttributeComparisonResponse(BaseModel):
    """Values displayed side by side together with the Phase 3B conflict assessment."""

    attribute_name: str
    values: List[SourceAttributeValueResponse] = Field(default_factory=list)
    different_values_detected: bool = False
    conflict_status: str = "NO_CONFLICT"
    conflict_severity: Optional[str] = None
    agreement_count: int = 0
    total_sources: int = 0


class ProductMatchResponse(BaseModel):
    """Explainable deterministic match assessment for a pair of attached source jobs."""

    source_job_ids: List[int]
    match_score: int = Field(..., ge=0, le=100)
    match_status: str
    reasons: List[str] = Field(default_factory=list)


class InvestigationComparisonResponse(BaseModel):
    """Unified non-conflict comparison for an investigation's explicitly attached sources."""

    investigation_id: int
    investigation_name: str
    status: str
    source_identities: List[SourceIdentityResponse] = Field(default_factory=list)
    matches: List[ProductMatchResponse] = Field(default_factory=list)
    attributes: List[AttributeComparisonResponse] = Field(default_factory=list)
