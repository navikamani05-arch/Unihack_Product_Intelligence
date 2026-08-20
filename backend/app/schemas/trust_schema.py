"""Pydantic schemas for trust scoring and metrics."""
from pydantic import BaseModel, Field


class TrustScoreResponse(BaseModel):
    """Response model for product trust score and readiness metrics."""
    product_id: int
    sku: str
    trust_score: float = Field(..., description="Composite trust score (0-100).")
    completeness_percentage: float = Field(..., description="Percentage of required attributes present.")
    conflict_count: int = Field(..., description="Active unresolved conflicts.")
    provenance_score: float = Field(..., description="Score based on traceable evidence backing.")
    ml_readiness_probability: float = Field(..., description="ML predicted probability of commerce readiness.")

    model_config = {"from_attributes": True}
