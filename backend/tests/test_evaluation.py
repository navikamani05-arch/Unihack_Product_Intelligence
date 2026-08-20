import csv
import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models.product import ProductAttribute, ProductRecord
from app.services.evaluation_service import EvaluationDomainError, EvaluationService


INPUT_COLUMNS = [
    "Mfg_Part_Num",
    "Part_Desc",
    "E1_Brand",
    "Unilog_Brand",
    "DIB_Brand",
    "Part_Manuf",
]


@pytest.fixture
def test_db():
    descriptor, db_path = tempfile.mkstemp(suffix=".db")
    os.close(descriptor)
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    Base.metadata.create_all(bind=engine)
    try:
        yield session
    finally:
        session.close()
        os.unlink(db_path)


@pytest.fixture
def client(test_db):
    def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def input_dataset(tmp_path, monkeypatch):
    path = tmp_path / "Unihack_SampleDataset-Input.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=INPUT_COLUMNS)
        writer.writeheader()
        writer.writerows([
            {
                "Mfg_Part_Num": "KNOWN-001",
                "Part_Desc": "Known industrial motor for evaluation coverage",
                "E1_Brand": "-- Unbranded --",
                "Unilog_Brand": "-- No Unilog Brand --",
                "DIB_Brand": "Acme",
                "Part_Manuf": "Acme Corporation (ACME)",
            },
            {
                "Mfg_Part_Num": "MISSING-002",
                "Part_Desc": "No generated product exists for this raw source record",
                "E1_Brand": "-- Unbranded --",
                "Unilog_Brand": "-- No Unilog Brand --",
                "DIB_Brand": "-- No DIB Brand --",
                "Part_Manuf": "Acme Corporation (ACME)",
            },
        ])
    monkeypatch.setattr(settings, "evaluation_input_dataset_path", str(path))
    return path


def add_generated_product(db, sku="KNOWN-001", *, manufacturer="Acme Corporation", name="Acme industrial motor", description="A detailed normalized industrial motor description for safe evaluation."):
    product = ProductRecord(
        sku=sku,
        name=name,
        description=description,
        manufacturer=manufacturer,
        category="Motors",
        sku_evidence_chunk_id="csv-1",
        sku_source_type="csv",
        sku_source_identifier="source.csv",
        sku_row_number=2,
    )
    db.add(product)
    db.flush()
    db.add_all([
        ProductAttribute(
            product_id=product.id,
            attribute_name="Brand",
            raw_value="Acme",
            normalized_value="Acme",
            source_type="csv",
            source_identifier="source.csv",
            row_number=2,
            evidence_chunk_id="csv-1",
        ),
        ProductAttribute(
            product_id=product.id,
            attribute_name="Voltage",
            raw_value="400V",
            normalized_value="400 V",
            unit="V",
            source_type="csv",
            source_identifier="source.csv",
            row_number=2,
            evidence_chunk_id="csv-1",
        ),
    ])
    db.commit()
    return product


def test_rule_quality_uses_raw_input_and_does_not_fabricate_score_without_generated_output(test_db, input_dataset):
    run = EvaluationService.run_rule_quality(test_db)
    summary = EvaluationService.latest_summary(test_db)

    assert run.products_processed == 2
    assert summary.products_processed == 2
    assert summary.products_with_generated_output == 0
    assert summary.rule_based_quality_score is None
    assert summary.ground_truth_accuracy is None
    assert summary.official_ground_truth_available is False
    assert "not ground-truth accuracy" in summary.message.lower()


def test_rule_quality_reports_computed_metrics_for_source_backed_generated_product(test_db, input_dataset):
    add_generated_product(test_db)
    EvaluationService.run_rule_quality(test_db)
    summary = EvaluationService.latest_summary(test_db)

    metrics = {metric.name: metric for metric in summary.metrics}
    assert summary.products_with_generated_output == 1
    assert summary.rule_based_quality_score is not None
    assert metrics["manufacturer"].compliance_percentage == 100.0
    assert metrics["uom"].compliance_percentage == 100.0
    assert metrics["lov"].compliance_percentage is None
    assert metrics["lov"].unavailable_reason
    assert summary.ground_truth_accuracy is None


def test_rule_quality_flags_placeholder_and_character_limit_violations(test_db, input_dataset):
    add_generated_product(
        test_db,
        manufacturer="-- Unbranded --",
        name="A" * 260,
        description="short",
    )
    run = EvaluationService.run_rule_quality(test_db)
    failures = EvaluationService.failures(test_db, run.id)
    checks = {failure.field.check_name for failure in failures.failures if failure.generated_product_id}

    assert "manufacturer" in checks
    assert "character_limit" in checks
    assert "description_format" in checks
    assert "placeholder" in checks


def test_ground_truth_is_explicitly_unavailable_until_official_output_is_registered(test_db, input_dataset):
    availability = EvaluationService.ground_truth_availability(test_db)
    assert availability.official_ground_truth_available is False
    assert availability.message == "Official ground truth dataset not available."
    with pytest.raises(EvaluationDomainError, match="Official ground truth dataset not available"):
        EvaluationService.run_ground_truth(test_db)


def test_official_expected_output_enables_exact_and_normalized_ground_truth_comparison(test_db, input_dataset, tmp_path):
    product = add_generated_product(test_db)
    expected = tmp_path / "official_expected.csv"
    expected.write_text(
        "Mfg_Part_Num,Product Title,Voltage\nKNOWN-001,Acme industrial motor,400 volts\n",
        encoding="utf-8",
    )
    EvaluationService.register_expected_dataset(test_db, expected, expected.name)
    run = EvaluationService.run_ground_truth(test_db)
    summary = EvaluationService.ground_truth_summary(test_db)
    comparison = EvaluationService.ground_truth_comparison(test_db, product.id)

    assert run.ground_truth_available == 1
    assert summary.official_ground_truth_available is True
    assert summary.ground_truth_accuracy == 100.0
    assert {row.result for row in comparison.rows} == {"EXACT_MATCH", "NORMALIZED_MATCH"}


def test_expected_output_requires_identifier_column(test_db, input_dataset, tmp_path):
    expected = tmp_path / "bad_expected.csv"
    expected.write_text("Title,Voltage\nMotor,400 V\n", encoding="utf-8")

    with pytest.raises(EvaluationDomainError, match="identifier column"):
        EvaluationService.register_expected_dataset(test_db, expected, expected.name)


def test_evaluation_api_distinguishes_rule_quality_from_unavailable_ground_truth(client, input_dataset):
    rule_run = client.post("/api/v1/evaluation/run", json={"mode": "rule_quality"})
    ground_truth = client.get("/api/v1/evaluation/summary", params={"mode": "ground_truth"})
    availability = client.get("/api/v1/evaluation/ground-truth/availability")

    assert rule_run.status_code == 200
    assert rule_run.json()["ground_truth_accuracy"] is None
    assert ground_truth.status_code == 200
    assert ground_truth.json()["status"] == "unavailable"
    assert availability.json()["message"] == "Official ground truth dataset not available."


def test_evaluation_product_and_failures_api_return_human_review_candidates(client, test_db, input_dataset):
    response = client.post("/api/v1/evaluation/run", json={"mode": "rule_quality"})
    assert response.status_code == 200
    failures = client.get("/api/v1/evaluation/failures")
    assert failures.status_code == 200
    assert failures.json()["total_failures"] > 0
    product_result_id = failures.json()["failures"][0]["product_result_id"]
    detail = client.get(f"/api/v1/evaluation/products/{product_result_id}")
    assert detail.status_code == 200
    assert detail.json()["status"] == "human_review"


def test_official_delivery_format_profile_reports_observed_schema_without_inventing_meanings(test_db, input_dataset, tmp_path):
    expected = tmp_path / "Unihack_ExpectedOutput-DeliveryFormat.csv"
    expected.write_text(
        "MFR URL,PART_NUMBER,Mfg_Part_Num,Product Name,MANUFACTURER_NAME,BRAND_NAME,ATTRIBUTE_LABEL 1,ATTRIBUTE_VALUE 1,ATTRIBUTE_UOM 1,Unknown Delivery Field\n"
        "https://example.com/A,20887830,PDSH4816AF,Dishwasher,Rheem Manufacturing,FRIGIDAIRE®,Series,Professional Series,,observed\n"
        "https://example.com/B,25286031,WDTS7024RZ,Dishwasher,Whirlpool Corporation,Whirlpool®,Series,Eco Series,,\n",
        encoding="utf-8",
    )
    EvaluationService.register_expected_dataset(test_db, expected, expected.name)
    profile = EvaluationService.ground_truth_schema(test_db)

    assert profile.official_ground_truth_available is True
    assert profile.row_count == 2
    assert profile.column_count == 10
    assert profile.identifier_column == "Mfg_Part_Num"
    by_name = {column.name: column for column in profile.columns}
    assert by_name["Mfg_Part_Num"].comparison_status == "SUPPORTED"
    assert by_name["Product Name"].mapped_field == "name"
    assert by_name["ATTRIBUTE_VALUE 1"].comparison_status == "PARTIALLY_SUPPORTED"
    assert by_name["MFR URL"].comparison_status == "UNSUPPORTED"
    assert by_name["Unknown Delivery Field"].comparison_status == "UNKNOWN"
    assert by_name["MFR URL"].sample_values == ["https://example.com/A", "https://example.com/B"]


def test_official_delivery_format_aggregate_reports_real_product_and_field_outcomes(test_db, input_dataset, tmp_path):
    product = add_generated_product(test_db, sku="KNOWN-001", name="Dishwasher", manufacturer="Acme Corporation")
    test_db.add(ProductAttribute(
        product_id=product.id,
        attribute_name="Series",
        raw_value="Professional Series",
        normalized_value="Professional Series",
        source_type="csv",
        source_identifier="source.csv",
        row_number=2,
        evidence_chunk_id="csv-1",
    ))
    test_db.commit()
    expected = tmp_path / "official_expected.csv"
    expected.write_text(
        "Mfg_Part_Num,Product Name,MANUFACTURER_NAME,ATTRIBUTE_LABEL 1,ATTRIBUTE_VALUE 1,Unknown Field\n"
        "KNOWN-001,Dishwasher,Acme Corporation,Series,Professional Series,official-only\n"
        "MISSING-002,Dishwasher,Acme Corporation,Series,Other,official-only\n",
        encoding="utf-8",
    )
    EvaluationService.register_expected_dataset(test_db, expected, expected.name)
    run = EvaluationService.run_ground_truth(test_db)
    summary = EvaluationService.ground_truth_summary(test_db)
    aggregate = summary.ground_truth

    assert run.products_processed == 2
    assert aggregate is not None
    assert aggregate.total_expected_products == 2
    assert aggregate.products_matched == 1
    assert aggregate.products_missing_from_output == 1
    assert aggregate.unexpected_products == 0
    assert aggregate.exact_matches >= 3
    assert aggregate.missing_values >= 1
    assert "Unknown Field" in aggregate.unknown_columns
    assert aggregate.overall_match_rate is not None
    assert any(item.result in {"MISSING", "INCORRECT"} for item in aggregate.mismatches)


def test_official_schema_and_ground_truth_summary_api_expose_real_metrics(client, test_db, input_dataset, tmp_path):
    add_generated_product(test_db)
    expected = tmp_path / "official_expected.csv"
    expected.write_text("Mfg_Part_Num,Product Name\nKNOWN-001,Acme industrial motor\n", encoding="utf-8")
    response = client.post(
        "/api/v1/evaluation/ground-truth/upload",
        files={"file": (expected.name, expected.read_bytes(), "text/csv")},
    )
    assert response.status_code == 200

    schema = client.get("/api/v1/evaluation/ground-truth/schema")
    assert schema.status_code == 200
    assert schema.json()["row_count"] == 1
    assert schema.json()["identifier_column"] == "Mfg_Part_Num"

    run = client.post("/api/v1/evaluation/run", json={"mode": "ground_truth"})
    assert run.status_code == 200
    summary = client.get("/api/v1/evaluation/summary", params={"mode": "ground_truth"})
    assert summary.status_code == 200
    assert summary.json()["official_ground_truth_available"] is True
    assert summary.json()["ground_truth"]["total_expected_products"] == 1
    assert summary.json()["ground_truth"]["products_matched"] == 1
    assert summary.json()["ground_truth"]["overall_match_rate"] == 100.0
    assert summary.json()["ground_truth_accuracy"] == 100.0


def test_official_file_is_legitimate_ground_truth_only_after_explicit_registration(test_db, input_dataset):
    availability = EvaluationService.ground_truth_availability(test_db)
    assert availability.official_ground_truth_available is False
    assert availability.message == "Official ground truth dataset not available."
    schema = EvaluationService.ground_truth_schema(test_db)
    assert schema.official_ground_truth_available is False
    assert schema.message == "Official ground truth dataset not available."
