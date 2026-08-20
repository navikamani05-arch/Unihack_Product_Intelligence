"""Pydantic schemas for product records, extraction, and evidence provenance."""
from datetime import datetime
from typing import List, Optional

from pydantic import AliasChoices, BaseModel, Field, ConfigDict


class EvidenceSchema(BaseModel):
    """Evidence snippet linking an extracted value to its source."""

    snippet_text: str = Field(..., description="Exact quoted text serving as evidence.")
    page_number: Optional[int] = Field(None, ge=1)
    row_number: Optional[int] = Field(None, ge=1)
    source_name: str = Field(..., description="Filename, URL, or CSV source name.")
    source_type: Optional[str] = None
    source_identifier: Optional[str] = None
    source_url: Optional[str] = None
    evidence_chunk_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class AttributeExtractionSchema(BaseModel):
    """One extracted attribute with normalized value and provenance."""

    attribute_name: str = Field(..., min_length=1)
    raw_value: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("raw_value", "original_value"),
        serialization_alias="raw_value",
    )
    normalized_value: Optional[str] = None
    unit: Optional[str] = None
    confidence_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    is_verified: bool = False
    evidence: List[EvidenceSchema] = Field(default_factory=list)

    # Flattened provenance fields are accepted for LLM structured output and API use.
    evidence_chunk_id: Optional[str] = None
    source_type: Optional[str] = None
    source_identifier: Optional[str] = None
    source_url: Optional[str] = None
    page_number: Optional[int] = Field(None, ge=1)
    row_number: Optional[int] = Field(None, ge=1)

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ProductAttributeResponse(BaseModel):
    """Response model for a stored product attribute and its provenance."""

    id: int
    product_id: int
    attribute_name: str
    raw_value: Optional[str] = None
    normalized_value: Optional[str] = None
    unit: Optional[str] = None
    confidence_score: float
    is_verified: bool
    source_type: Optional[str] = None
    source_identifier: Optional[str] = None
    source_url: Optional[str] = None
    page_number: Optional[int] = None
    row_number: Optional[int] = None
    evidence_chunk_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ProductRecordResponse(BaseModel):
    """Response model for a complete product record."""

    id: int
    sku: Optional[str] = None
    name: Optional[str] = None
    product_name: Optional[str] = None
    category: Optional[str] = None
    manufacturer: Optional[str] = None
    brand: Optional[str] = None
    description: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime
    attributes: List[ProductAttributeResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class ProductExtractionResponse(BaseModel):
    """Validated structured response returned by the LLM extraction service."""

    product_name: Optional[str] = None
    sku: Optional[str] = None
    sku_evidence_chunk_id: Optional[str] = None
    sku_source_type: Optional[str] = None
    sku_source_identifier: Optional[str] = None
    sku_source_url: Optional[str] = None
    sku_page_number: Optional[int] = Field(default=None, ge=1)
    sku_row_number: Optional[int] = Field(default=None, ge=1)
    brand: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    attributes: List[AttributeExtractionSchema] = Field(default_factory=list)
    missing_attributes: List[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class MultiProductExtractionResponse(BaseModel):
    """Response containing multiple products, typically for catalogs or batch processing."""
    products: List[ProductExtractionResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class ExtractionAPIResponse(BaseModel):
    """Response envelope for an extraction request or completed extraction."""

    job_id: int
    task_id: Optional[int] = None
    product_id: Optional[int] = None
    product_ids: List[int] = Field(default_factory=list)
    extracted_data: Optional[ProductExtractionResponse] = None
    extracted_products: List[ProductExtractionResponse] = Field(default_factory=list)
    status: str
    extraction_status_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ExtractionStatusResponse(BaseModel):
    """Persisted status and progress for a background extraction task."""

    job_id: int
    task_id: int
    status: str
    current_batch: int = 0
    total_batches: int = 0
    processed_evidence_count: int = 0
    total_evidence_count: int = 0
    extracted_product_count: int = 0
    error: Optional[str] = None
    cancellation_requested: bool = False
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[ExtractionAPIResponse] = None

    model_config = ConfigDict(from_attributes=True)


# Backward-compatible aliases for callers using the architecture terminology.
ProductAttributeExtraction = AttributeExtractionSchema
ProductExtractionResult = ProductExtractionResponse
Evidence = EvidenceSchema
