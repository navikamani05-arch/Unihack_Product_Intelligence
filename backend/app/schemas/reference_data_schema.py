"""Pydantic contracts for explainable Phase 5 reference-data operations."""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ReferenceDatasetResponse(BaseModel):
    id: Optional[int] = None
    dataset_type: str
    name: str
    file_name: Optional[str] = None
    version: Optional[str] = None
    row_count: Optional[int] = None
    status: str
    is_active: bool = True
    checksum: Optional[str] = None
    imported_at: Optional[datetime] = None
    sheet_names: Optional[List[str]] = None
    import_statistics: Optional[Dict[str, Any]] = None


class ReferenceDatasetListResponse(BaseModel):
    datasets: List[ReferenceDatasetResponse]


class ResolutionRequest(BaseModel):
    value: Optional[str] = None
    manufacturer_value: Optional[str] = None
    brand_value: Optional[str] = None


class ResolutionCandidate(BaseModel):
    display_value: str
    code: Optional[str] = None
    manufacturer_code: Optional[str] = None
    score: Optional[float] = None


class ResolutionResponse(BaseModel):
    input: Optional[str] = None
    canonical_name: Optional[str] = None
    manufacturer_code: Optional[str] = None
    brand_code: Optional[str] = None
    match_type: str
    status: str
    confidence: Optional[float] = None
    candidates: List[ResolutionCandidate] = Field(default_factory=list)
    reference_dataset: Optional[str] = None
    explanation: str


class AttributeResolutionRequest(BaseModel):
    classpath: Optional[str] = None
    leaf_node: Optional[str] = None
    attribute: str
    candidate_value: Optional[str] = None


class AttributeResolutionResponse(BaseModel):
    allowed: bool
    status: str
    canonical_attribute_label: Optional[str] = None
    canonical_value: Optional[str] = None
    normalized_value: Optional[str] = None
    filtering_flag: Optional[str] = None
    guideline: Optional[str] = None
    remarks: Optional[str] = None
    confidence: Optional[float] = None
    match_type: str
    reference_dataset: Optional[str] = None
    explanation: str


class UOMNormalizationRequest(BaseModel):
    value: Optional[str] = None
    uom: Optional[str] = None


class UOMNormalizationResponse(BaseModel):
    original_value: Optional[str] = None
    normalized_value: Optional[str] = None
    uom: Optional[str] = None
    uom_source: str
    normalization_rule: Optional[str] = None
    status: str
    reference_dataset: Optional[str] = None
    explanation: str


class FractionNormalizationRequest(BaseModel):
    value: Optional[str] = None


class FractionNormalizationResponse(BaseModel):
    original_value: Optional[str] = None
    normalized_value: Optional[str] = None
    status: str
    normalization_rule: Optional[str] = None
    reference_dataset: Optional[str] = None
    explanation: str


class ImportResponse(ReferenceDatasetResponse):
    duplicate_rows: int = 0
    empty_rows_removed: int = 0
    headers_detected: List[str] = Field(default_factory=list)
