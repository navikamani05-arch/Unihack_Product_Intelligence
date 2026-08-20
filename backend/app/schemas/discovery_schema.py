"""Pydantic contracts for controlled external discovery."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class DiscoveryStartRequest(BaseModel):
    """Starts a bounded discovery run; URLs are fetched only after server-side validation."""

    user_urls: list[str] = Field(default_factory=list, max_length=8)
    mode: Literal["DISCOVERY_ENABLED"] = "DISCOVERY_ENABLED"


class DiscoveryQueryResponse(BaseModel):
    id: int
    query_text: str
    reason: str
    provider_name: Optional[str] = None
    status: str
    result_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class DiscoverySourceResponse(BaseModel):
    id: int
    url: str
    canonical_url: str
    title: Optional[str] = None
    domain: Optional[str] = None
    source_type: str
    authority_tier: str
    identity_score: Optional[float] = None
    quality_score: Optional[float] = None
    rank: Optional[int] = None
    status: str
    rejection_reason: Optional[str] = None
    user_provided: bool
    metadata_snapshot: Optional[dict[str, Any]] = None

    model_config = {"from_attributes": True}


class DiscoveryEvidenceResponse(BaseModel):
    id: int
    source_id: int
    source_url: str
    source_title: Optional[str] = None
    source_type: str
    attribute_name: Optional[str] = None
    raw_value: Optional[str] = None
    normalized_value: Optional[str] = None
    quote: str
    page_number: Optional[int] = None
    extraction_method: str
    evidence_quality: Optional[float] = None


class DiscoveryRunResponse(BaseModel):
    id: int
    product_id: int
    status: str
    mode: str
    provider_name: Optional[str] = None
    provider_status: Optional[str] = None
    query_count: int
    discovered_count: int
    verified_count: int
    rejected_count: int
    fetch_failed_count: int
    evidence_count: int
    conflict_count: int
    summary: Optional[dict[str, Any]] = None
    error_message: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class DiscoveryDetailResponse(BaseModel):
    run: DiscoveryRunResponse
    queries: list[DiscoveryQueryResponse]
    sources: list[DiscoverySourceResponse]
    evidence: list[DiscoveryEvidenceResponse]


class DiscoveryProviderStatusResponse(BaseModel):
    provider_name: str
    configured: bool
    message: str
    max_queries_per_product: int
    max_results_per_query: int
    max_sources_per_product: int
    max_fetches_per_run: int


class CrossSourceConflictResponse(BaseModel):
    attribute_name: str
    values: list[str]
    source_count: int
    explanation: str
