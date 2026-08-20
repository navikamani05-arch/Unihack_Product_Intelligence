"""SQLAlchemy ORM models."""
from app.models.ingestion import IngestionJob, RawDocumentSource
from app.models.product import ProductRecord, ProductAttribute
from app.models.conflict import DataConflict, EvidenceChunk
from app.models.investigation import InvestigationSourceJob, ProductInvestigation
from app.models.trust import TrustMetric
from app.models.reference_data import (
    BrandMaster,
    FractionConversion,
    LOVEntry,
    ManufacturerMaster,
    ProductNormalizationDecision,
    ReferenceDataset,
    UOMEntry,
)
from app.models.evaluation import (
    EvaluationExpectedDataset,
    EvaluationFieldResult,
    EvaluationProductResult,
    EvaluationRun,
)
from app.models.enrichment import EnrichmentBatch, EnrichmentReviewDecision, EnrichmentRun
from app.models.discovery import CandidateSource, DiscoveryEvidence, DiscoveryQuery, DiscoveryRun, SourceFetch
from app.models.commerce_output import CommerceOutput, CommerceOutputField
from app.models.catalog import CatalogBatch, CatalogItem
from app.models.extraction import ExtractionJob

__all__ = [
    "IngestionJob",
    "RawDocumentSource",
    "ProductRecord",
    "ProductAttribute",
    "DataConflict",
    "EvidenceChunk",
    "ProductInvestigation",
    "InvestigationSourceJob",
    "TrustMetric",
    "EvaluationExpectedDataset",
    "EvaluationRun",
    "EvaluationProductResult",
    "EvaluationFieldResult",
    "ReferenceDataset",
    "ManufacturerMaster",
    "BrandMaster",
    "LOVEntry",
    "UOMEntry",
    "FractionConversion",
    "ProductNormalizationDecision",
    "EnrichmentRun",
    "EnrichmentBatch",
    "EnrichmentReviewDecision",
    "DiscoveryRun",
    "DiscoveryQuery",
    "CandidateSource",
    "SourceFetch",
    "DiscoveryEvidence",
    "CommerceOutput",
    "CommerceOutputField",
    "CatalogBatch",
    "CatalogItem",
    "ExtractionJob",
]
