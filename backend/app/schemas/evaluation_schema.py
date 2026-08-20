from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


EvaluationMode = Literal["rule_quality", "ground_truth"]


class EvaluationRunRequest(BaseModel):
    """Select the evaluation mode; ground truth remains unavailable without expected output."""

    mode: EvaluationMode = "rule_quality"


class FieldMetricResponse(BaseModel):
    name: str
    label: str
    passed: int
    evaluated: int
    compliance_percentage: Optional[float] = None
    unavailable_reason: Optional[str] = None


class GroundTruthColumnProfile(BaseModel):
    name: str
    pandas_dtype: str
    nonempty_count: int
    empty_count: int
    unique_count: int
    sample_values: list[str] = Field(default_factory=list)
    max_string_length: int = 0
    role: str = "unknown"
    comparison_status: Literal["SUPPORTED", "PARTIALLY_SUPPORTED", "UNSUPPORTED", "UNKNOWN"] = "UNKNOWN"
    mapped_field: Optional[str] = None
    comparison_mode: Optional[str] = None
    reason: str


class GroundTruthSchemaProfileResponse(BaseModel):
    official_ground_truth_available: bool
    message: str
    file_name: Optional[str] = None
    row_count: int = 0
    column_count: int = 0
    identifier_column: Optional[str] = None
    columns: list[GroundTruthColumnProfile] = Field(default_factory=list)


class GroundTruthFieldMetricResponse(BaseModel):
    field_name: str
    mapped_field: Optional[str] = None
    expected_nonempty: int = 0
    exact_matches: int = 0
    normalized_matches: int = 0
    partial_matches: int = 0
    missing: int = 0
    incorrect: int = 0
    evaluated: int = 0
    exact_match_rate: Optional[float] = None
    match_rate: Optional[float] = None
    missing_value_rate: Optional[float] = None
    comparison_status: Literal["SUPPORTED", "PARTIALLY_SUPPORTED", "UNSUPPORTED", "UNKNOWN"] = "SUPPORTED"
    reason: Optional[str] = None
    source_data_unavailable: int = 0
    pipeline_missing: int = 0


class GroundTruthMismatchResponse(BaseModel):
    product_key: Optional[str] = None
    expected_row_number: Optional[int] = None
    field_name: str
    mapped_field: Optional[str] = None
    expected_value: Optional[str] = None
    generated_value: Optional[str] = None
    result: Literal["PARTIAL_MATCH", "MISSING", "INCORRECT"]
    availability: Literal["available", "source_data_unavailable"] = "available"
    reason: Optional[str] = None


class GroundTruthAggregateResponse(BaseModel):
    total_expected_products: int = 0
    products_matched: int = 0
    products_missing_from_output: int = 0
    unexpected_products: int = 0
    expected_nonempty_fields: int = 0
    comparable_fields: int = 0
    exact_matches: int = 0
    normalized_matches: int = 0
    partial_matches: int = 0
    missing_values: int = 0
    incorrect_values: int = 0
    source_data_unavailable: int = 0
    pipeline_missing: int = 0
    overall_evaluation_rate: Optional[float] = None
    overall_match_rate: Optional[float] = None
    overall_missing_value_rate: Optional[float] = None
    field_metrics: list[GroundTruthFieldMetricResponse] = Field(default_factory=list)
    mismatches: list[GroundTruthMismatchResponse] = Field(default_factory=list)
    unsupported_columns: list[str] = Field(default_factory=list)
    unknown_columns: list[str] = Field(default_factory=list)
    lov_comparison_available: bool = False
    uom_comparison_available: bool = False
    character_limits_available: bool = False


class EvaluationSummaryResponse(BaseModel):
    run_id: Optional[int] = None
    mode: EvaluationMode = "rule_quality"
    status: str
    message: str
    official_ground_truth_available: bool
    products_processed: int = 0
    products_with_generated_output: int = 0
    fields_evaluated: int = 0
    rule_based_quality_score: Optional[float] = None
    ground_truth_accuracy: Optional[float] = None
    missing_attribute_rate: Optional[float] = None
    invalid_lov_values: int = 0
    invalid_uom_values: int = 0
    character_limit_violations: int = 0
    human_review_candidates: int = 0
    metrics: list[FieldMetricResponse] = Field(default_factory=list)
    ground_truth: Optional[GroundTruthAggregateResponse] = None
    generated_at: Optional[datetime] = None


class EvaluationFieldResponse(BaseModel):
    id: int
    field_name: str
    check_name: str
    outcome: str
    expected_value: Optional[str] = None
    generated_value: Optional[str] = None
    normalized_expected_value: Optional[str] = None
    normalized_generated_value: Optional[str] = None
    details: Optional[str] = None
    severity: str

    model_config = {"from_attributes": True}


class EvaluationProductResponse(BaseModel):
    id: int
    run_id: int
    input_row_number: int
    input_product_key: Optional[str] = None
    source_description: Optional[str] = None
    generated_product_id: Optional[int] = None
    status: str
    quality_score: Optional[float] = None
    human_review_reason: Optional[str] = None
    input_snapshot: dict[str, Any] = Field(default_factory=dict)
    generated_snapshot: dict[str, Any] = Field(default_factory=dict)
    fields: list[EvaluationFieldResponse] = Field(default_factory=list)


class EvaluationFailureResponse(BaseModel):
    product_result_id: int
    input_row_number: int
    input_product_key: Optional[str] = None
    generated_product_id: Optional[int] = None
    status: str
    field: EvaluationFieldResponse


class EvaluationFailuresResponse(BaseModel):
    run_id: Optional[int] = None
    total_failures: int = 0
    failures: list[EvaluationFailureResponse] = Field(default_factory=list)


class GroundTruthAvailabilityResponse(BaseModel):
    official_ground_truth_available: bool
    message: str
    supported_file_types: list[str] = Field(default_factory=lambda: [".csv", ".xlsx"])
    expected_dataset_path: Optional[str] = None
    file_name: Optional[str] = None
    row_count: int = 0
    column_count: int = 0
    detected_columns: list[str] = Field(default_factory=list)
    identifier_column: Optional[str] = None


class GroundTruthComparisonRow(BaseModel):
    field_name: str
    mapped_field: Optional[str] = None
    expected_value: Optional[str] = None
    generated_value: Optional[str] = None
    result: Literal["EXACT_MATCH", "NORMALIZED_MATCH", "PARTIAL_MATCH", "MISSING", "INCORRECT"]
    availability: Literal["available", "source_data_unavailable"] = "available"
    comparison_status: Literal["SUPPORTED", "PARTIALLY_SUPPORTED", "UNSUPPORTED", "UNKNOWN"] = "SUPPORTED"
    reason: Optional[str] = None


class GroundTruthComparisonResponse(BaseModel):
    official_ground_truth_available: bool
    message: str
    rows: list[GroundTruthComparisonRow] = Field(default_factory=list)
    product_key: Optional[str] = None
    expected_row_number: Optional[int] = None


__all__ = [
    "EvaluationMode", "EvaluationRunRequest", "FieldMetricResponse", "GroundTruthColumnProfile",
    "GroundTruthSchemaProfileResponse", "GroundTruthFieldMetricResponse", "GroundTruthMismatchResponse",
    "GroundTruthAggregateResponse", "EvaluationSummaryResponse", "EvaluationFieldResponse",
    "EvaluationProductResponse", "EvaluationFailureResponse", "EvaluationFailuresResponse",
    "GroundTruthAvailabilityResponse", "GroundTruthComparisonRow", "GroundTruthComparisonResponse",
]
