"""Pydantic contracts for large-scale catalog processing."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class CatalogUploadResponse(BaseModel):
    batch_id: int
    dataset_name: str
    filename: str
    source_type: str
    total_rows: int
    detected_columns: list[str]
    valid_rows: int
    invalid_rows: int
    duplicate_identifiers: list[str] = Field(default_factory=list)
    missing_required_fields: dict[str, int] = Field(default_factory=dict)
    validation_failures_by_field: dict[str, int] = Field(default_factory=dict)
    validation_warnings: list[str] = Field(default_factory=list)
    status: str


class CatalogStartRequest(BaseModel):
    mode: str = "SOURCE_ONLY"
    use_llm: bool = False


class CatalogRetryRequest(BaseModel):
    item_ids: list[int] = Field(default_factory=list)
    start_immediately: bool = True
    mode: str = "SOURCE_ONLY"


class CatalogStatusResponse(BaseModel):
    batch_id: int
    dataset_name: str
    filename: str
    source_type: str
    status: str
    total_items: int
    queued_items: int
    processed_items: int
    successful_items: int
    review_items: int
    failed_items: int
    invalid_items: int
    progress_percentage: float
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_summary: dict[str, Any] = Field(default_factory=dict)
    configuration_snapshot: dict[str, Any] = Field(default_factory=dict)


class CatalogItemResponse(BaseModel):
    id: int
    batch_id: int
    row_number: int
    identifier: Optional[str] = None
    input_snapshot: dict[str, Any]
    validation_status: str
    validation_errors: list[str] = Field(default_factory=list)
    validation_warnings: list[str] = Field(default_factory=list)
    processing_status: str
    error_message: Optional[str] = None
    product_id: Optional[int] = None
    enrichment_run_id: Optional[int] = None
    commerce_output_id: Optional[int] = None
    result_status: Optional[str] = None
    attempt_count: int
    evidence_available: bool = False
    conflict_count: int = 0
    review_required: bool = False
    confidence: Optional[float] = None
    product_name: Optional[str] = None
    manufacturer: Optional[str] = None
    brand: Optional[str] = None


class CatalogResultsResponse(BaseModel):
    batch_id: int
    total: int
    page: int
    page_size: int
    items: list[CatalogItemResponse]


class CatalogReviewQueueItem(BaseModel):
    item_id: int
    product_id: Optional[int] = None
    row_number: int
    identifier: Optional[str] = None
    product_name: Optional[str] = None
    issue: str
    severity: str
    status: str
    reason: str
    evidence_available: bool = False


class CatalogReviewQueueResponse(BaseModel):
    batch_id: int
    total: int
    items: list[CatalogReviewQueueItem]


class CatalogMetrics(BaseModel):
    processing_success_rate: Optional[float] = None
    completeness: Optional[float] = None
    evidence_coverage: Optional[float] = None
    reference_data_compliance: Optional[float] = None
    conflict_rate: Optional[float] = None
    human_review_rate: Optional[float] = None
    rule_based_quality_score: Optional[float] = None
    ground_truth_accuracy: str = "UNAVAILABLE"


class CatalogAggregationResponse(BaseModel):
    batch_id: int
    status: str
    total_products: int
    processed: int
    ready: int
    review_required: int
    insufficient_data: int
    failed: int
    conflicts: int
    progress_percentage: float
    average_processing_time_seconds: Optional[float] = None
    metrics: CatalogMetrics
    ground_truth_message: str = "Official ground truth dataset not available."


class CatalogUploadValidationResponse(CatalogUploadResponse):
    warnings_by_row: dict[str, list[str]] = Field(default_factory=dict)
