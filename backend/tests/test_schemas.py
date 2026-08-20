"""Tests for Pydantic schemas."""
import pytest
from app.schemas.product_schema import (
    EvidenceSchema,
    AttributeExtractionSchema,
    ProductRecordResponse,
)
from app.schemas.conflict_schema import (
    DataConflictResponse,
    ConflictResolutionRequest,
)
from app.schemas.trust_schema import TrustScoreResponse


class TestEvidenceSchema:
    """Test EvidenceSchema validation."""

    def test_valid_evidence(self):
        """Test creating valid evidence schema."""
        evidence = EvidenceSchema(
            snippet_text="Rated voltage: 230V AC",
            page_number=1,
            source_name="datasheet.pdf",
        )
        assert evidence.snippet_text == "Rated voltage: 230V AC"
        assert evidence.page_number == 1
        assert evidence.source_name == "datasheet.pdf"

    def test_evidence_without_page_number(self):
        """Test evidence without page number."""
        evidence = EvidenceSchema(
            snippet_text="Rated voltage: 230V AC",
            source_name="datasheet.pdf",
        )
        assert evidence.page_number is None


class TestAttributeExtractionSchema:
    """Test AttributeExtractionSchema validation."""

    def test_valid_attribute(self):
        """Test creating valid attribute extraction schema."""
        attribute = AttributeExtractionSchema(
            attribute_name="rated_voltage",
            raw_value="230V",
            normalized_value="230",
            unit="V",
            confidence_score=0.95,
            evidence=[],
        )
        assert attribute.attribute_name == "rated_voltage"
        assert attribute.confidence_score == 0.95
        assert attribute.is_verified is False

    def test_confidence_score_validation(self):
        """Test confidence score must be between 0 and 1."""
        with pytest.raises(ValueError):
            AttributeExtractionSchema(
                attribute_name="rated_voltage",
                raw_value="230V",
                normalized_value="230",
                unit="V",
                confidence_score=1.5,  # Invalid: > 1.0
                evidence=[],
            )

    def test_attribute_with_evidence(self):
        """Test attribute with evidence."""
        evidence = EvidenceSchema(
            snippet_text="Rated voltage: 230V AC",
            page_number=1,
            source_name="datasheet.pdf",
        )
        attribute = AttributeExtractionSchema(
            attribute_name="rated_voltage",
            raw_value="230V",
            normalized_value="230",
            unit="V",
            confidence_score=0.95,
            evidence=[evidence],
        )
        assert len(attribute.evidence) == 1
        assert attribute.evidence[0].snippet_text == "Rated voltage: 230V AC"


class TestConflictResolutionRequest:
    """Test ConflictResolutionRequest validation."""

    def test_valid_resolution_request(self):
        """Test creating valid conflict resolution request."""
        request = ConflictResolutionRequest(
            conflict_id=1,
            chosen_value="230V",
            resolution_notes="Verified against official datasheet",
        )
        assert request.conflict_id == 1
        assert request.chosen_value == "230V"
        assert request.resolution_notes == "Verified against official datasheet"

    def test_resolution_request_without_notes(self):
        """Test resolution request without notes."""
        request = ConflictResolutionRequest(
            conflict_id=1,
            chosen_value="230V",
        )
        assert request.resolution_notes is None


class TestTrustScoreResponse:
    """Test TrustScoreResponse validation."""

    def test_valid_trust_score(self):
        """Test creating valid trust score response."""
        trust_score = TrustScoreResponse(
            product_id=1,
            sku="SENSOR-001",
            trust_score=85.5,
            completeness_percentage=90.0,
            conflict_count=1,
            provenance_score=80.0,
            ml_readiness_probability=0.75,
        )
        assert trust_score.product_id == 1
        assert trust_score.sku == "SENSOR-001"
        assert trust_score.trust_score == 85.5
        assert trust_score.ml_readiness_probability == 0.75


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
