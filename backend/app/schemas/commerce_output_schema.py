"""Pydantic contracts for the Commerce-Ready Output & Delivery layer."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class CommerceOutputGenerateRequest(BaseModel):
    enrichment_run_id: Optional[int] = Field(default=None, description="Use a specific existing enrichment run; latest is used when omitted.")


class CommerceOutputFieldSchema(BaseModel):
    id: int
    field_key: str
    display_name: str
    raw_value: Optional[str] = None
    normalized_value: Optional[str] = None
    output_value: Optional[str] = None
    unit: Optional[str] = None
    field_status: str
    validation_status: str
    validation_explanation: Optional[str] = None
    reference_dataset: Optional[str] = None
    character_limit: Optional[int] = None
    character_limit_status: str
    confidence: Optional[float] = None
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    provenance_status: str = "UNAVAILABLE"
    conflict_ids: list[int] = Field(default_factory=list)
    review_state: str = "NOT_REVIEWED"
    review: Optional[dict[str, Any]] = None

    model_config = {"from_attributes": True}


class CommerceValidationSummarySchema(BaseModel):
    overall_status: str
    fields_total: int
    fields_populated: int
    fields_missing: int
    fields_with_conflicts: int
    fields_requiring_review: int
    fields_without_provenance: int = 0
    reference_data_available: bool
    reference_data_unavailable_fields: int
    invalid_reference_fields: int
    character_limit_checked: int
    character_limit_unavailable: int
    character_limit_violations: int
    notes: list[str] = Field(default_factory=list)


class CommerceOutputSchema(BaseModel):
    id: int
    product_id: int
    enrichment_run_id: int
    output_version: str
    status: str
    overall_confidence: Optional[float] = None
    generated_at: datetime
    product: dict[str, Any]
    record: dict[str, Any]
    fields: list[CommerceOutputFieldSchema] = Field(default_factory=list)
    validation: CommerceValidationSummarySchema
    sources: list[dict[str, Any]] = Field(default_factory=list)
    conflicts: list[dict[str, Any]] = Field(default_factory=list)
    reviews: list[dict[str, Any]] = Field(default_factory=list)
    ground_truth_accuracy: Literal["UNAVAILABLE"] = "UNAVAILABLE"


class CommerceOutputListItem(BaseModel):
    id: int
    product_id: int
    enrichment_run_id: int
    status: str
    overall_confidence: Optional[float] = None
    generated_at: datetime

    model_config = {"from_attributes": True}
