"""Pydantic contracts for the additive Phase 6 enrichment API."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class EnrichmentAnalyzeRequest(BaseModel):
    use_llm: bool = Field(default=False, description="Use the already configured extraction provider only when new source evidence exists.")
    mode: Literal["SOURCE_ONLY", "DISCOVERY_ENABLED"] = Field(
        default="SOURCE_ONLY",
        description="SOURCE_ONLY reuses existing evidence. DISCOVERY_ENABLED runs controlled discovery and never fabricates a source when no provider is configured.",
    )


class EnrichmentBatchRequest(BaseModel):
    product_ids: list[int] = Field(min_length=1, max_length=100)
    retry_failed: bool = False
    mode: Literal["SOURCE_ONLY", "DISCOVERY_ENABLED"] = "SOURCE_ONLY"


class EnrichmentReviewRequest(BaseModel):
    action: Literal["APPROVE", "EDIT", "REJECT", "MARK_UNRESOLVED"]
    attribute_id: Optional[int] = None
    value: Optional[str] = Field(default=None, max_length=1000)
    reason: Optional[str] = Field(default=None, max_length=4000)


class EnrichmentEvidenceSchema(BaseModel):
    evidence_chunk_id: Optional[str] = None
    source_type: Optional[str] = None
    source_identifier: Optional[str] = None
    source_url: Optional[str] = None
    page_number: Optional[int] = None
    row_number: Optional[int] = None
    quote: Optional[str] = None
    authority: str = "unknown"


class EnrichmentAttributeSchema(BaseModel):
    attribute_id: int
    name: str
    raw_value: Optional[str] = None
    normalized_value: Optional[str] = None
    unit: Optional[str] = None
    confidence: Optional[float] = None
    validation_status: str
    validation_explanation: Optional[str] = None
    evidence: list[EnrichmentEvidenceSchema] = Field(default_factory=list)


class EnrichmentConflictSchema(BaseModel):
    id: int
    attribute_name: str
    conflict_type: Optional[str] = None
    severity: Optional[str] = None
    status: Optional[str] = None
    suggested_value: Optional[str] = None
    suggestion_reason: Optional[str] = None
    agreement_count: Optional[int] = None
    total_sources: Optional[int] = None
    evidence_snapshot: Optional[Any] = None


class EnrichmentStageSchema(BaseModel):
    stage: str
    status: Literal["completed", "skipped", "warning", "failed"]
    message: str
    timestamp: datetime


class EnrichmentRunSchema(BaseModel):
    id: int
    product_id: int
    status: str
    stage: str
    product_status: Optional[str] = None
    overall_confidence: Optional[float] = None
    category: Optional[str] = None
    category_path: list[str] = Field(default_factory=list)
    category_confidence: Optional[float] = None
    product_understanding: dict[str, Any] = Field(default_factory=dict)
    schema_snapshot: list[dict[str, Any]] = Field(default_factory=list)
    missing_attributes: list[str] = Field(default_factory=list)
    progress_log: list[EnrichmentStageSchema] = Field(default_factory=list)
    source_count: int = 0
    evidence_count: int = 0
    attribute_count: int = 0
    conflict_count: int = 0
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class EnrichmentOutputSchema(BaseModel):
    run: EnrichmentRunSchema
    product: dict[str, Any]
    attributes: list[EnrichmentAttributeSchema] = Field(default_factory=list)
    evidence: list[EnrichmentEvidenceSchema] = Field(default_factory=list)
    conflicts: list[EnrichmentConflictSchema] = Field(default_factory=list)
    review_decisions: list[dict[str, Any]] = Field(default_factory=list)


class EnrichmentBatchSchema(BaseModel):
    id: int
    status: str
    total_products: int
    processed_count: int
    successful_count: int
    failed_count: int
    review_count: int
    requested_product_ids: list[int] = Field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class EnrichmentProductListItem(BaseModel):
    id: int
    sku: Optional[str] = None
    name: Optional[str] = None
    manufacturer: Optional[str] = None
    category: Optional[str] = None
    status: Optional[str] = None

    model_config = {"from_attributes": True}
