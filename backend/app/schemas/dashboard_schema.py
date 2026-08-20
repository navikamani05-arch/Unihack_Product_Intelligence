from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class DashboardMetric(BaseModel):
    key: str
    label: str
    value: float | int | str | None = None
    status: str = "AVAILABLE"
    explanation: Optional[str] = None


class DashboardPipelineStage(BaseModel):
    key: str
    label: str
    count: int = 0
    status: str = "AVAILABLE"
    explanation: Optional[str] = None


class DashboardOverviewResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    title: str
    subtitle: str
    latest_batch: Optional[dict[str, Any]] = None
    metrics: list[DashboardMetric] = Field(default_factory=list)
    pipeline: list[DashboardPipelineStage] = Field(default_factory=list)
    availability: dict[str, Any] = Field(default_factory=dict)
    demo_product_id: Optional[int] = None
    generated_at: str


class DashboardProductListItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    sku: Optional[str] = None
    name: Optional[str] = None
    manufacturer: Optional[str] = None
    category: Optional[str] = None
    status: Optional[str] = None
    enrichment_status: Optional[str] = None
    commerce_status: Optional[str] = None
    confidence: Optional[float] = None
    conflict_count: int = 0
    review_count: int = 0
    evidence_count: int = 0
    source_types: list[str] = Field(default_factory=list)


class DashboardProductListResponse(BaseModel):
    items: list[DashboardProductListItem] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 25


class DashboardProductDetailResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    product: dict[str, Any]
    raw_input: dict[str, Any] = Field(default_factory=dict)
    before_after: dict[str, Any] = Field(default_factory=dict)
    pipeline: list[dict[str, Any]] = Field(default_factory=list)
    attributes: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    conflicts: list[dict[str, Any]] = Field(default_factory=list)
    reviews: list[dict[str, Any]] = Field(default_factory=list)
    enrichment: Optional[dict[str, Any]] = None
    discovery: Optional[dict[str, Any]] = None
    commerce_output: Optional[dict[str, Any]] = None
    explanation: list[dict[str, Any]] = Field(default_factory=list)
    availability: dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "DashboardMetric",
    "DashboardPipelineStage",
    "DashboardOverviewResponse",
    "DashboardProductListItem",
    "DashboardProductListResponse",
    "DashboardProductDetailResponse",
]

