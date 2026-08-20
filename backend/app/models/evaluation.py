"""Persisted, non-destructive evaluation run records for Phase 4."""
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class EvaluationExpectedDataset(Base):
    """Metadata for an uploaded official expected-output dataset; no values are inferred."""

    __tablename__ = "evaluation_expected_datasets"

    id = Column(Integer, primary_key=True, index=True)
    file_name = Column(String(500), nullable=False)
    file_path = Column(String(1000), nullable=False)
    identifier_column = Column(String(255), nullable=True)
    columns_json = Column(JSON, nullable=False, default=list)
    row_count = Column(Integer, nullable=False, default=0)
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class EvaluationRun(Base):
    """An immutable summary of one rule-quality or ground-truth evaluation run."""

    __tablename__ = "evaluation_runs"

    id = Column(Integer, primary_key=True, index=True)
    mode = Column(String(40), nullable=False, index=True)  # rule_quality | ground_truth
    status = Column(String(40), nullable=False, default="completed")
    dataset_path = Column(String(1000), nullable=True)
    expected_dataset_path = Column(String(1000), nullable=True)
    ground_truth_available = Column(Integer, nullable=False, default=0)
    products_processed = Column(Integer, nullable=False, default=0)
    products_with_generated_output = Column(Integer, nullable=False, default=0)
    fields_evaluated = Column(Integer, nullable=False, default=0)
    overall_score = Column(Float, nullable=True)
    summary_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    products = relationship(
        "EvaluationProductResult", back_populates="run", cascade="all, delete-orphan"
    )


class EvaluationProductResult(Base):
    """One input record's evidence-based evaluation outcome."""

    __tablename__ = "evaluation_product_results"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("evaluation_runs.id"), nullable=False, index=True)
    input_row_number = Column(Integer, nullable=False)
    input_product_key = Column(String(255), nullable=True, index=True)
    source_description = Column(Text, nullable=True)
    generated_product_id = Column(Integer, ForeignKey("product_records.id"), nullable=True, index=True)
    status = Column(String(40), nullable=False, default="human_review")
    quality_score = Column(Float, nullable=True)
    human_review_reason = Column(Text, nullable=True)
    input_snapshot = Column(JSON, nullable=False, default=dict)
    generated_snapshot = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    run = relationship("EvaluationRun", back_populates="products")
    fields = relationship(
        "EvaluationFieldResult", back_populates="product_result", cascade="all, delete-orphan"
    )


class EvaluationFieldResult(Base):
    """A single quality check or future expected-vs-generated field comparison."""

    __tablename__ = "evaluation_field_results"

    id = Column(Integer, primary_key=True, index=True)
    product_result_id = Column(
        Integer, ForeignKey("evaluation_product_results.id"), nullable=False, index=True
    )
    field_name = Column(String(120), nullable=False, index=True)
    check_name = Column(String(120), nullable=False, index=True)
    outcome = Column(String(40), nullable=False, index=True)
    expected_value = Column(Text, nullable=True)
    generated_value = Column(Text, nullable=True)
    normalized_expected_value = Column(Text, nullable=True)
    normalized_generated_value = Column(Text, nullable=True)
    details = Column(Text, nullable=True)
    severity = Column(String(20), nullable=False, default="LOW")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    product_result = relationship("EvaluationProductResult", back_populates="fields")
