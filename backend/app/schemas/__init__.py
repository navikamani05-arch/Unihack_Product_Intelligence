"""Pydantic validation schemas."""
from app.schemas.product_schema import (
    EvidenceSchema,
    AttributeExtractionSchema,
    ProductExtractionResponse,
    ProductRecordResponse,
    ProductAttributeResponse,
)
from app.schemas.conflict_schema import (
    DataConflictResponse,
    ConflictResolutionRequest,
)
from app.schemas.trust_schema import TrustScoreResponse

__all__ = [
    "EvidenceSchema",
    "AttributeExtractionSchema",
    "ProductExtractionResponse",
    "ProductRecordResponse",
    "ProductAttributeResponse",
    "DataConflictResponse",
    "ConflictResolutionRequest",
    "TrustScoreResponse",
]
