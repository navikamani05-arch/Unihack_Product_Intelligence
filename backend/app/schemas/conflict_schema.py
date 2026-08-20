"""Pydantic schemas for conflict detection and resolution."""
from pydantic import BaseModel, Field
from typing import Optional


class DataConflictResponse(BaseModel):
    """Response model for a detected data conflict."""
    id: int
    product_id: int
    attribute_name: str
    source_a_name: str
    source_a_value: str
    source_b_name: str
    source_b_value: str
    resolution_status: str  # unresolved, resolved_a, resolved_b, merged
    resolved_value: Optional[str]

    model_config = {"from_attributes": True}


class ConflictResolutionRequest(BaseModel):
    """Request model for resolving a data conflict."""
    conflict_id: int = Field(..., description="ID of the conflict record.")
    chosen_value: str = Field(..., description="The resolved value selected by human or agent.")
    resolution_notes: Optional[str] = Field(None, description="Justification for the resolution.")
