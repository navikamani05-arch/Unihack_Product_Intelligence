import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models.conflict import DataConflict, EvidenceChunk
from app.models.ingestion import IngestionJob, RawDocumentSource
from app.models.product import ProductAttribute, ProductRecord


@pytest.fixture(scope="function")
def test_db():
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        os.unlink(db_path)


@pytest.fixture(scope="function")
def client(test_db):
    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def add_job_with_product(
    db,
    *,
    job_name: str,
    source_type: str,
    filename: str,
    product_name: str,
    brand: str,
    category: str,
    power: str,
    voltage: str,
    sku: str | None = None,
    source_url: str | None = None,
    page_number: int | None = None,
    row_number: int | None = None,
    completed: bool = True,
    type_series: str | None = "SIMOTICS GP",
):
    """Persist a complete source-scoped job with extracted attributes and explicit identity evidence."""
    job = IngestionJob(
        job_name=job_name,
        status="completed" if completed else "processing",
        source_type=source_type,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    source = RawDocumentSource(
        job_id=job.id,
        file_name=filename,
        source_url=source_url,
        raw_text_content="Source-backed product data",
    )
    db.add(source)
    db.commit()
    db.refresh(source)

    lines = [
        f"Product Name: {product_name}",
        f"Brand: {brand}",
        f"Category: {category}",
        f"Power: {power}",
        f"Voltage: {voltage}",
    ]
    if type_series:
        lines.append(f"Type Series: {type_series}")
    if sku:
        lines.append(f"SKU: {sku}")

    chunk = EvidenceChunk(
        job_id=job.id,
        source_id=source.id,
        stable_chunk_id=f"{source_type}-{job.id}-identity",
        snippet_text="\n".join(lines),
        source_type=source_type,
        source_identifier=filename,
        source_url=source_url,
        page_number=page_number,
        row_number=row_number,
    )
    db.add(chunk)
    db.commit()
    db.refresh(chunk)

    # ProductRecord.sku is globally unique in the existing architecture. Reuse it when
    # two sources explicitly identify the same SKU; source-specific evidence remains on chunks.
    product = db.query(ProductRecord).filter(ProductRecord.sku == sku).first() if sku else None
    if product is None:
        product = ProductRecord(
            sku=sku,
            sku_evidence_chunk_id=chunk.stable_chunk_id if sku else None,
            sku_source_type=source_type if sku else None,
            sku_source_identifier=filename if sku else None,
            sku_source_url=source_url if sku else None,
            sku_page_number=page_number if sku else None,
            sku_row_number=row_number if sku else None,
            name=product_name,
            manufacturer=brand,
            category=category,
            status="draft",
        )
        db.add(product)
        db.commit()
        db.refresh(product)

    attributes = []
    for attribute_name, value in (("power", power), ("voltage", voltage)):
        attribute = ProductAttribute(
            product_id=product.id,
            attribute_name=attribute_name,
            raw_value=value,
            normalized_value=value,
            confidence_score=0.99,
            source_type=source_type,
            source_identifier=filename,
            source_url=source_url,
            page_number=page_number,
            row_number=row_number,
            evidence_chunk_id=chunk.stable_chunk_id,
        )
        db.add(attribute)
        db.flush()
        attributes.append(attribute)
    # Existing extraction assigns the latest linked attribute to a chunk; matching uses both
    # source provenance fields and the source-scoped chunk relationship.
    chunk.attribute_id = attributes[-1].id
    db.commit()
    return job, source, chunk, product


def create_investigation(client, name="SIMOTICS GP Motor Investigation"):
    response = client.post(
        "/api/v1/investigations",
        json={"name": name, "description": "Cross-source product investigation"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def attach(client, investigation_id, job_id):
    response = client.post(f"/api/v1/investigations/{investigation_id}/sources/{job_id}")
    assert response.status_code == 200, response.text
    return response.json()


def test_create_list_retrieve_and_delete_investigation_without_deleting_jobs(client, test_db):
    job, _, _, _ = add_job_with_product(
        test_db,
        job_name="Motor PDF",
        source_type="pdf",
        filename="motor.pdf",
        product_name="SIMOTICS GP Motor",
        brand="Siemens",
        category="Motor",
        power="5.5 kW",
        voltage="400 V",
        sku="SIM-001",
        page_number=2,
    )

    created = create_investigation(client)
    assert created["status"] == "draft"
    assert created["source_jobs"] == []

    attached = attach(client, created["id"], job.id)
    assert attached["status"] == "active"
    assert attached["source_jobs"][0]["job_id"] == job.id
    assert attached["source_jobs"][0]["sources"][0]["filename"] == "motor.pdf"

    listed = client.get("/api/v1/investigations")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [created["id"]]

    detail = client.get(f"/api/v1/investigations/{created['id']}")
    assert detail.status_code == 200
    assert detail.json()["source_jobs"][0]["evidence_chunk_count"] == 1

    deleted = client.delete(f"/api/v1/investigations/{created['id']}")
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/investigations/{created['id']}").status_code == 404
    # Deleting an investigation never removes the underlying ingestion job, source, or evidence.
    assert test_db.query(IngestionJob).filter(IngestionJob.id == job.id).first() is not None
    assert test_db.query(EvidenceChunk).filter(EvidenceChunk.job_id == job.id).count() == 1


def test_attach_only_completed_valid_jobs_and_list_available_jobs(client, test_db):
    completed, _, _, _ = add_job_with_product(
        test_db,
        job_name="Completed website source",
        source_type="website",
        filename="siemens-product-page",
        product_name="SIMOTICS GP Motor",
        brand="Siemens",
        category="Motor",
        power="5.5 kW",
        voltage="400 V",
        source_url="https://example.test/siemens-motor",
    )
    processing, _, _, _ = add_job_with_product(
        test_db,
        job_name="Processing CSV source",
        source_type="csv",
        filename="catalog.csv",
        product_name="SIMOTICS GP Motor",
        brand="Siemens",
        category="Motor",
        power="5.5 kW",
        voltage="400 V",
        row_number=2,
        completed=False,
    )
    created = create_investigation(client)

    available = client.get("/api/v1/investigations/available-jobs")
    assert available.status_code == 200
    assert [job["id"] for job in available.json()] == [completed.id]

    assert client.post(f"/api/v1/investigations/{created['id']}/sources/99999").status_code == 404
    pending_response = client.post(f"/api/v1/investigations/{created['id']}/sources/{processing.id}")
    assert pending_response.status_code == 400
    assert "completed" in pending_response.json()["detail"]

    attach(client, created["id"], completed.id)
    duplicate_response = client.post(f"/api/v1/investigations/{created['id']}/sources/{completed.id}")
    assert duplicate_response.status_code == 400
    assert "already attached" in duplicate_response.json()["detail"]


def test_attached_sources_are_isolated_and_identity_fields_keep_provenance(client, test_db):
    pdf_job, _, _, _ = add_job_with_product(
        test_db,
        job_name="Siemens Motor PDF",
        source_type="pdf",
        filename="Siemens_Motor.pdf",
        product_name="SIMOTICS GP Motor",
        brand="Siemens",
        category="Motor",
        power="5.5 kW",
        voltage="400 V",
        sku="SIM-001",
        page_number=2,
    )
    csv_job, _, _, _ = add_job_with_product(
        test_db,
        job_name="Supplier CSV",
        source_type="csv",
        filename="supplier_catalog.csv",
        product_name="SIMOTICS GP Motor",
        brand="Siemens",
        category="Motor",
        power="5.5 kW",
        voltage="415 V",
        sku="SIM-001-CSV",
        row_number=2,
    )
    unrelated_job, _, _, _ = add_job_with_product(
        test_db,
        job_name="Unrelated Pump Website",
        source_type="website",
        filename="unrelated-pump",
        product_name="Aqua Pump",
        brand="OtherBrand",
        category="Pump",
        power="2.2 kW",
        voltage="230 V",
        sku="PUMP-001",
        source_url="https://example.test/unrelated-pump",
    )

    created = create_investigation(client)
    attach(client, created["id"], pdf_job.id)
    attach(client, created["id"], csv_job.id)

    comparison = client.get(f"/api/v1/investigations/{created['id']}/comparison")
    assert comparison.status_code == 200, comparison.text
    payload = comparison.json()
    assert {identity["job_id"] for identity in payload["source_identities"]} == {pdf_job.id, csv_job.id}
    assert unrelated_job.id not in {identity["job_id"] for identity in payload["source_identities"]}
    assert all(unrelated_job.id not in match["source_job_ids"] for match in payload["matches"])

    pdf_identity = next(item for item in payload["source_identities"] if item["job_id"] == pdf_job.id)
    fields = {field["field"]: field for field in pdf_identity["identity_fields"]}
    assert fields["product_name"]["value"] == "SIMOTICS GP Motor"
    assert fields["brand"]["value"] == "Siemens"
    assert fields["sku"]["value"] == "SIM-001"
    assert fields["sku"]["source_identifier"] == "Siemens_Motor.pdf"
    assert fields["sku"]["page_number"] == 2
    assert fields["catalog_number"]["value"] == "Not found in provided sources"

    attribute_rows = {row["attribute_name"]: row for row in payload["attributes"]}
    voltage_values = {value["job_id"]: value for value in attribute_rows["voltage"]["values"]}
    assert voltage_values[pdf_job.id]["page_number"] == 2
    assert voltage_values[csv_job.id]["row_number"] == 2
    assert attribute_rows["voltage"]["different_values_detected"] is True


def test_explainable_matching_reports_high_possible_low_and_different_product(client, test_db):
    # High-confidence: explicit SKU, brand, category, type series, and important attributes align.
    pdf, _, _, _ = add_job_with_product(
        test_db,
        job_name="Motor PDF",
        source_type="pdf",
        filename="motor.pdf",
        product_name="SIMOTICS GP Motor",
        brand="Siemens",
        category="Motor",
        power="5.5 kW",
        voltage="400 V",
        sku="SIM-001",
        page_number=2,
    )
    website, _, _, _ = add_job_with_product(
        test_db,
        job_name="Motor Website",
        source_type="website",
        filename="siemens-motor-page",
        product_name="SIMOTICS GP Motor",
        brand="Siemens",
        category="Motor",
        power="5.5 kW",
        voltage="400 V",
        sku="SIM-001",
        source_url="https://example.test/siemens-motor",
    )
    high = create_investigation(client, "High Match")
    attach(client, high["id"], pdf.id)
    attach(client, high["id"], website.id)
    high_match = client.get(f"/api/v1/investigations/{high['id']}/comparison").json()["matches"][0]
    assert high_match["match_status"] == "HIGH_CONFIDENCE_MATCH"
    assert high_match["match_score"] >= 80
    assert any("Brand matches" in reason for reason in high_match["reasons"])
    assert any("SKU matches" in reason for reason in high_match["reasons"])

    # Possible match: compatible brand, category, series, and technical data but no explicit shared identifier.
    possible_left, _, _, _ = add_job_with_product(
        test_db,
        job_name="Possible Left",
        source_type="pdf",
        filename="possible-left.pdf",
        product_name="SIMOTICS GP Motor",
        brand="Siemens",
        category="Motor",
        power="5.5 kW",
        voltage="400 V",
        page_number=1,
    )
    possible_right, _, _, _ = add_job_with_product(
        test_db,
        job_name="Possible Right",
        source_type="csv",
        filename="possible-right.csv",
        product_name="SIMOTICS GP Drive",
        brand="Siemens",
        category="Motor",
        power="5.5 kW",
        voltage="415 V",
        row_number=3,
    )
    possible = create_investigation(client, "Possible Match")
    attach(client, possible["id"], possible_left.id)
    attach(client, possible["id"], possible_right.id)
    possible_match = client.get(f"/api/v1/investigations/{possible['id']}/comparison").json()["matches"][0]
    assert possible_match["match_status"] == "POSSIBLE_MATCH"
    assert 55 <= possible_match["match_score"] < 80

    # Product names alone cannot create a possible match; this must remain low confidence.
    low_left, _, _, _ = add_job_with_product(
        test_db,
        job_name="Low Left",
        source_type="pdf",
        filename="low-left.pdf",
        product_name="Industrial Motor", brand="Brand A", category="Motor",
        power="5.5 kW", voltage="400 V", page_number=1, type_series=None,
    )
    low_right, _, _, _ = add_job_with_product(
        test_db,
        job_name="Low Right",
        source_type="website",
        filename="low-right-page",
        product_name="Industrial Motor", brand="Brand B", category="Pump",
        power="2.2 kW", voltage="230 V", source_url="https://example.test/low", type_series=None,
    )
    low = create_investigation(client, "Low Match")
    attach(client, low["id"], low_left.id)
    attach(client, low["id"], low_right.id)
    low_match = client.get(f"/api/v1/investigations/{low['id']}/comparison").json()["matches"][0]
    assert low_match["match_status"] == "LOW_CONFIDENCE_MATCH"
    assert low_match["match_score"] <= 35

    # Explicitly contradictory identifiers drive a likely-different result regardless of similar attributes.
    different_left, _, _, _ = add_job_with_product(
        test_db,
        job_name="Different Left",
        source_type="pdf",
        filename="different-left.pdf",
        product_name="SIMOTICS GP Motor", brand="Siemens", category="Motor",
        power="5.5 kW", voltage="400 V", sku="SIM-001", page_number=1,
    )
    different_right, _, _, _ = add_job_with_product(
        test_db,
        job_name="Different Right",
        source_type="website",
        filename="different-right-page",
        product_name="SIMOTICS GP Motor", brand="Siemens", category="Motor",
        power="5.5 kW", voltage="400 V", sku="SIM-999", source_url="https://example.test/different",
    )
    different = create_investigation(client, "Different Product")
    attach(client, different["id"], different_left.id)
    attach(client, different["id"], different_right.id)
    different_match = client.get(f"/api/v1/investigations/{different['id']}/comparison").json()["matches"][0]
    assert different_match["match_status"] == "LIKELY_DIFFERENT_PRODUCT"
    assert different_match["match_score"] <= 20
    assert any("values differ" in reason for reason in different_match["reasons"])


def set_source_attribute(db, job, attribute_name, value, *, unit=None, confidence=0.99):
    """Update only one source-scoped extracted attribute for a targeted conflict case."""
    attribute = (
        db.query(ProductAttribute)
        .filter(
            ProductAttribute.evidence_chunk_id == f"{job.source_type}-{job.id}-identity",
            ProductAttribute.attribute_name == attribute_name,
        )
        .one()
    )
    attribute.raw_value = value
    attribute.normalized_value = value
    attribute.unit = unit
    attribute.confidence_score = confidence
    db.commit()


def conflict_report(client, investigation_id):
    response = client.get(f"/api/v1/investigations/{investigation_id}/conflicts")
    assert response.status_code == 200, response.text
    return response.json()


def test_conflict_normalizes_voltage_spelling_and_whitespace_equivalence(client, test_db):
    left, _, _, _ = add_job_with_product(
        test_db, job_name="PDF 400 V", source_type="pdf", filename="motor.pdf",
        product_name="Motor", brand="Acme", category="Motor", power="5.5 kW", voltage="400 V", page_number=2,
    )
    right, _, _, _ = add_job_with_product(
        test_db, job_name="CSV 400 volts", source_type="csv", filename="catalog.csv",
        product_name="Motor", brand="Acme", category="Motor", power="5.5 kilowatts", voltage=" 400 volts ", row_number=4,
    )
    investigation = create_investigation(client, "Equivalent formats")
    attach(client, investigation["id"], left.id)
    attach(client, investigation["id"], right.id)

    report = conflict_report(client, investigation["id"])
    summaries = {item["attribute_name"]: item for item in report["attribute_summaries"]}
    assert summaries["voltage"]["status"] == "NO_CONFLICT"
    assert summaries["power"]["status"] == "NO_CONFLICT"
    assert not any(item["attribute_name"] in {"voltage", "power"} for item in report["conflicts"])


def test_conflict_detects_value_disagreement_with_two_of_three_agreement(client, test_db):
    left, _, _, _ = add_job_with_product(
        test_db, job_name="PDF", source_type="pdf", filename="motor.pdf",
        product_name="Motor", brand="Acme", category="Motor", power="5.5 kW", voltage="400 V", page_number=2,
    )
    middle, _, _, _ = add_job_with_product(
        test_db, job_name="CSV", source_type="csv", filename="catalog.csv",
        product_name="Motor", brand="Acme", category="Motor", power="5.5 kW", voltage="400V", row_number=3,
    )
    right, _, _, _ = add_job_with_product(
        test_db, job_name="Website", source_type="website", filename="product-page",
        product_name="Motor", brand="Acme", category="Motor", power="5.5 kW", voltage="415 V", source_url="https://example.test/motor",
    )
    investigation = create_investigation(client, "Voltage disagreement")
    for job in (left, middle, right):
        attach(client, investigation["id"], job.id)

    report = conflict_report(client, investigation["id"])
    voltage = next(item for item in report["conflicts"] if item["attribute_name"] == "voltage")
    assert voltage["status"] == "VALUE_CONFLICT"
    assert voltage["severity"] == "HIGH"
    assert voltage["agreement_count"] == 2
    assert voltage["total_sources"] == 3
    assert voltage["agreement_percentage"] == 66.7
    assert {value["source_type"] for value in voltage["values"]} == {"pdf", "csv", "website"}


def test_conflict_detects_unit_disagreement_without_overwriting_values(client, test_db):
    left, _, _, _ = add_job_with_product(
        test_db, job_name="PDF", source_type="pdf", filename="motor.pdf",
        product_name="Motor", brand="Acme", category="Motor", power="5.5 kW", voltage="400 V", page_number=1,
    )
    right, _, _, _ = add_job_with_product(
        test_db, job_name="Website", source_type="website", filename="motor-page",
        product_name="Motor", brand="Acme", category="Motor", power="5.5 kW", voltage="400 A", source_url="https://example.test/motor",
    )
    investigation = create_investigation(client, "Unit disagreement")
    attach(client, investigation["id"], left.id)
    attach(client, investigation["id"], right.id)

    report = conflict_report(client, investigation["id"])
    voltage = next(item for item in report["conflicts"] if item["attribute_name"] == "voltage")
    assert voltage["status"] == "UNIT_CONFLICT"
    assert voltage["severity"] == "HIGH"
    assert [value["value"] for value in voltage["values"]] == ["400 V", "400 A"]
    persisted = test_db.query(DataConflict).filter(DataConflict.investigation_id == investigation["id"]).one()
    assert persisted.conflict_type == "UNIT_CONFLICT"
    assert persisted.resolution_status == "unresolved"


def test_conflict_detects_missing_attribute_and_preserves_existing_confidence(client, test_db):
    left, _, _, _ = add_job_with_product(
        test_db, job_name="PDF", source_type="pdf", filename="motor.pdf",
        product_name="Motor", brand="Acme", category="Motor", power="5.5 kW", voltage="400 V", page_number=9,
    )
    right, _, _, _ = add_job_with_product(
        test_db, job_name="CSV", source_type="csv", filename="catalog.csv",
        product_name="Motor", brand="Acme", category="Motor", power="5.5 kW", voltage="400 V", row_number=7,
    )
    set_source_attribute(test_db, left, "power", "5.5 kW", confidence=0.72)
    # Delete only the attached CSV source's power assertion; its voltage evidence remains.
    test_db.query(ProductAttribute).filter(
        ProductAttribute.evidence_chunk_id == f"{right.source_type}-{right.id}-identity",
        ProductAttribute.attribute_name == "power",
    ).delete()
    test_db.commit()
    investigation = create_investigation(client, "Missing power")
    attach(client, investigation["id"], left.id)
    attach(client, investigation["id"], right.id)

    report = conflict_report(client, investigation["id"])
    power = next(item for item in report["conflicts"] if item["attribute_name"] == "power")
    assert power["status"] == "MISSING_IN_SOURCE"
    assert power["severity"] == "LOW"
    assert power["missing_job_ids"] == [right.id]
    assert power["values"][0]["confidence_score"] == 0.72


def test_conflict_detects_explicit_identity_disagreement_with_pdf_csv_website_provenance(client, test_db):
    pdf, _, _, _ = add_job_with_product(
        test_db, job_name="PDF", source_type="pdf", filename="motor.pdf",
        product_name="Motor", brand="Acme", category="Motor", power="5.5 kW", voltage="400 V", sku="SKU-100", page_number=5,
    )
    csv, _, _, _ = add_job_with_product(
        test_db, job_name="CSV", source_type="csv", filename="catalog.csv",
        product_name="Motor", brand="Acme", category="Motor", power="5.5 kW", voltage="400 V", sku="SKU-200", row_number=8,
    )
    website, _, _, _ = add_job_with_product(
        test_db, job_name="Website", source_type="website", filename="motor-page",
        product_name="Motor", brand="Acme", category="Motor", power="5.5 kW", voltage="400 V", sku="SKU-100", source_url="https://example.test/motor",
    )
    investigation = create_investigation(client, "SKU conflict")
    for job in (pdf, csv, website):
        attach(client, investigation["id"], job.id)

    report = conflict_report(client, investigation["id"])
    sku = next(item for item in report["conflicts"] if item["attribute_name"] == "sku")
    assert sku["status"] == "IDENTITY_CONFLICT"
    assert sku["severity"] == "CRITICAL"
    by_type = {value["source_type"]: value for value in sku["values"]}
    assert by_type["pdf"]["page_number"] == 5
    assert by_type["csv"]["row_number"] == 8
    assert by_type["website"]["source_url"] == "https://example.test/motor"


def test_conflicts_are_isolated_per_investigation_and_comparison_exposes_status(client, test_db):
    attached_left, _, _, _ = add_job_with_product(
        test_db, job_name="Attached PDF", source_type="pdf", filename="attached.pdf",
        product_name="Motor", brand="Acme", category="Motor", power="5.5 kW", voltage="400 V", page_number=1,
    )
    attached_right, _, _, _ = add_job_with_product(
        test_db, job_name="Attached CSV", source_type="csv", filename="attached.csv",
        product_name="Motor", brand="Acme", category="Motor", power="5.5 kW", voltage="415 V", row_number=2,
    )
    unrelated, _, _, _ = add_job_with_product(
        test_db, job_name="Unrelated Website", source_type="website", filename="unrelated-page",
        product_name="Pump", brand="Other", category="Pump", power="2.2 kW", voltage="230 V", source_url="https://example.test/unrelated",
    )
    investigation = create_investigation(client, "Scoped conflict")
    attach(client, investigation["id"], attached_left.id)
    attach(client, investigation["id"], attached_right.id)

    report = conflict_report(client, investigation["id"])
    voltage = next(item for item in report["conflicts"] if item["attribute_name"] == "voltage")
    assert {value["job_id"] for value in voltage["values"]} == {attached_left.id, attached_right.id}
    assert unrelated.id not in {value["job_id"] for conflict in report["conflicts"] for value in conflict["values"]}

    comparison = client.get(f"/api/v1/investigations/{investigation['id']}/comparison")
    assert comparison.status_code == 200
    voltage_row = next(item for item in comparison.json()["attributes"] if item["attribute_name"] == "voltage")
    assert voltage_row["conflict_status"] == "VALUE_CONFLICT"
    assert voltage_row["agreement_count"] == 1
    assert voltage_row["total_sources"] == 2


def test_conflict_endpoint_returns_empty_report_for_one_source_without_global_evidence(client, test_db):
    only_job, _, _, _ = add_job_with_product(
        test_db, job_name="Only CSV", source_type="csv", filename="single.csv",
        product_name="Motor", brand="Acme", category="Motor", power="5.5 kW", voltage="400 V", row_number=2,
    )
    unrelated, _, _, _ = add_job_with_product(
        test_db, job_name="Unrelated PDF", source_type="pdf", filename="unrelated.pdf",
        product_name="Pump", brand="Other", category="Pump", power="2.2 kW", voltage="230 V", page_number=2,
    )
    investigation = create_investigation(client, "Single source")
    attach(client, investigation["id"], only_job.id)

    report = conflict_report(client, investigation["id"])
    assert report["total_sources"] == 1
    assert report["conflict_count"] == 0
    assert all(unrelated.id not in {value["job_id"] for value in conflict["values"]} for conflict in report["conflicts"])


def test_conflict_endpoint_replaces_only_its_own_investigation_summaries(client, test_db):
    first_left, _, _, _ = add_job_with_product(
        test_db, job_name="First PDF", source_type="pdf", filename="first.pdf",
        product_name="Motor", brand="Acme", category="Motor", power="5.5 kW", voltage="400 V", page_number=1,
    )
    first_right, _, _, _ = add_job_with_product(
        test_db, job_name="First CSV", source_type="csv", filename="first.csv",
        product_name="Motor", brand="Acme", category="Motor", power="5.5 kW", voltage="415 V", row_number=2,
    )
    second_left, _, _, _ = add_job_with_product(
        test_db, job_name="Second PDF", source_type="pdf", filename="second.pdf",
        product_name="Motor", brand="Acme", category="Motor", power="5.5 kW", voltage="400 V", page_number=3,
    )
    second_right, _, _, _ = add_job_with_product(
        test_db, job_name="Second CSV", source_type="csv", filename="second.csv",
        product_name="Motor", brand="Acme", category="Motor", power="5.5 kW", voltage="440 V", row_number=3,
    )
    first = create_investigation(client, "First investigation")
    second = create_investigation(client, "Second investigation")
    for job in (first_left, first_right):
        attach(client, first["id"], job.id)
    for job in (second_left, second_right):
        attach(client, second["id"], job.id)

    conflict_report(client, first["id"])
    conflict_report(client, second["id"])
    assert test_db.query(DataConflict).filter(DataConflict.investigation_id == first["id"]).count() == 1
    assert test_db.query(DataConflict).filter(DataConflict.investigation_id == second["id"]).count() == 1
    # Re-running the first report refreshes only first-investigation summaries.
    conflict_report(client, first["id"])
    assert test_db.query(DataConflict).filter(DataConflict.investigation_id == first["id"]).count() == 1
    assert test_db.query(DataConflict).filter(DataConflict.investigation_id == second["id"]).count() == 1


def add_source_attribute(db, job, attribute_name, value, *, unit=None, confidence=0.88):
    """Add one source-scoped attribute without changing the fixture's original evidence."""
    attribute = ProductAttribute(
        product_id=(
            db.query(ProductRecord)
            .join(ProductAttribute, ProductAttribute.product_id == ProductRecord.id)
            .filter(ProductAttribute.evidence_chunk_id == f"{job.source_type}-{job.id}-identity")
            .first()
            .id
        ),
        attribute_name=attribute_name,
        raw_value=value,
        normalized_value=value,
        unit=unit,
        confidence_score=confidence,
        source_type=job.source_type,
        source_identifier=(
            db.query(RawDocumentSource).filter(RawDocumentSource.job_id == job.id).one().file_name
        ),
        source_url=(
            db.query(RawDocumentSource).filter(RawDocumentSource.job_id == job.id).one().source_url
        ),
        evidence_chunk_id=f"{job.source_type}-{job.id}-identity",
    )
    db.add(attribute)
    db.commit()
    return attribute


def test_conflict_policy_assigns_critical_high_medium_and_low_severity(client, test_db):
    left, _, _, _ = add_job_with_product(
        test_db, job_name="PDF", source_type="pdf", filename="motor.pdf",
        product_name="Motor", brand="Acme", category="Motor", power="5.5 kW", voltage="400 V", sku="A-100", page_number=1,
    )
    right, _, _, _ = add_job_with_product(
        test_db, job_name="CSV", source_type="csv", filename="motor.csv",
        product_name="Motor", brand="Acme", category="Motor", power="7.5 kW", voltage="415 V", sku="B-100", row_number=2,
    )
    add_source_attribute(test_db, left, "series", "GP")
    add_source_attribute(test_db, right, "series", "XP")
    investigation = create_investigation(client, "Severity policy")
    attach(client, investigation["id"], left.id)
    attach(client, investigation["id"], right.id)

    conflicts = {item["attribute_name"]: item for item in conflict_report(client, investigation["id"])["conflicts"]}
    assert conflicts["sku"]["severity"] == "CRITICAL"
    assert conflicts["voltage"]["severity"] == "HIGH"
    assert conflicts["series"]["severity"] == "MEDIUM"


def test_source_authority_suggestion_prefers_pdf_documentation_when_values_tie(client, test_db):
    pdf, _, _, _ = add_job_with_product(
        test_db, job_name="Manufacturer PDF", source_type="pdf", filename="manufacturer.pdf",
        product_name="Motor", brand="Acme", category="Motor", power="5.5 kW", voltage="400 V", page_number=4,
    )
    website, _, _, _ = add_job_with_product(
        test_db, job_name="Website", source_type="website", filename="page",
        product_name="Motor", brand="Acme", category="Motor", power="5.5 kW", voltage="415 V", source_url="https://example.test/product",
    )
    investigation = create_investigation(client, "Authority suggestion")
    attach(client, investigation["id"], pdf.id)
    attach(client, investigation["id"], website.id)

    voltage = next(item for item in conflict_report(client, investigation["id"])["conflicts"] if item["attribute_name"] == "voltage")
    assert voltage["suggested_value"] == "400 V"
    assert "manufacturer_documentation" in voltage["suggestion_reason"]
    by_source = {value["source_type"]: value for value in voltage["values"]}
    assert by_source["pdf"]["source_authority"] == "manufacturer_documentation"
    assert by_source["website"]["source_authority"] == "manufacturer_website"
    assert by_source["pdf"]["normalized_value"] == "400 v"


def test_conflict_detail_and_accepting_suggestion_preserve_product_attribute_evidence(client, test_db):
    left, _, _, _ = add_job_with_product(
        test_db, job_name="PDF", source_type="pdf", filename="motor.pdf",
        product_name="Motor", brand="Acme", category="Motor", power="5.5 kW", voltage="400 V", page_number=5,
    )
    right, _, _, _ = add_job_with_product(
        test_db, job_name="CSV", source_type="csv", filename="motor.csv",
        product_name="Motor", brand="Acme", category="Motor", power="5.5 kW", voltage="415 V", row_number=9,
    )
    investigation = create_investigation(client, "Resolution safety")
    attach(client, investigation["id"], left.id)
    attach(client, investigation["id"], right.id)

    voltage = next(item for item in conflict_report(client, investigation["id"])["conflicts"] if item["attribute_name"] == "voltage")
    conflict_id = voltage["conflict_id"]
    detail = client.get(f"/api/v1/investigations/{investigation['id']}/conflicts/{conflict_id}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["values"][0]["page_number"] == 5
    assert detail.json()["values"][1]["row_number"] == 9

    before = [
        item.raw_value for item in test_db.query(ProductAttribute).filter(ProductAttribute.attribute_name == "voltage").order_by(ProductAttribute.id)
    ]
    resolved = client.post(
        f"/api/v1/investigations/{investigation['id']}/conflicts/{conflict_id}/resolve",
        json={"action": "ACCEPT_SOURCE_VALUE", "reasoning": "Manufacturer PDF reviewed by analyst."},
    )
    assert resolved.status_code == 200, resolved.text
    payload = resolved.json()
    assert payload["resolution_status"] == "resolved_source_value"
    assert payload["resolution_action"] == "ACCEPT_SOURCE_VALUE"
    assert payload["resolution_reason"] == "Manufacturer PDF reviewed by analyst."
    after = [
        item.raw_value for item in test_db.query(ProductAttribute).filter(ProductAttribute.attribute_name == "voltage").order_by(ProductAttribute.id)
    ]
    assert after == before == ["400 V", "415 V"]

    persisted = test_db.query(DataConflict).filter(DataConflict.id == conflict_id).one()
    assert persisted.resolved_value == "400 V"
    assert persisted.evidence_snapshot[0]["page_number"] == 5
    assert persisted.evidence_snapshot[1]["row_number"] == 9


def test_conflict_resolution_supports_human_review_unresolved_and_rejects_unbacked_value(client, test_db):
    left, _, _, _ = add_job_with_product(
        test_db, job_name="PDF", source_type="pdf", filename="motor.pdf",
        product_name="Motor", brand="Acme", category="Motor", power="5.5 kW", voltage="400 V", page_number=1,
    )
    right, _, _, _ = add_job_with_product(
        test_db, job_name="Website", source_type="website", filename="page",
        product_name="Motor", brand="Acme", category="Motor", power="5.5 kW", voltage="415 V", source_url="https://example.test/motor",
    )
    investigation = create_investigation(client, "Review workflow")
    attach(client, investigation["id"], left.id)
    attach(client, investigation["id"], right.id)
    conflict_id = next(item for item in conflict_report(client, investigation["id"])["conflicts"] if item["attribute_name"] == "voltage")["conflict_id"]

    reviewed = client.post(
        f"/api/v1/investigations/{investigation['id']}/conflicts/{conflict_id}/resolve",
        json={"action": "MARK_AS_HUMAN_REVIEW", "reasoning": "Awaiting product owner confirmation."},
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["resolution_status"] == "human_review"
    assert reviewed.json()["requires_review"] is True

    rejected = client.post(
        f"/api/v1/investigations/{investigation['id']}/conflicts/{conflict_id}/resolve",
        json={"action": "ACCEPT_OTHER_VALUE", "chosen_value": "999 V"},
    )
    assert rejected.status_code == 422

    unresolved = client.post(
        f"/api/v1/investigations/{investigation['id']}/conflicts/{conflict_id}/resolve",
        json={"action": "MARK_AS_UNRESOLVED", "reasoning": "Reopened after additional evidence."},
    )
    assert unresolved.status_code == 200
    assert unresolved.json()["resolution_status"] == "unresolved"
    assert unresolved.json()["resolution_reason"] == "Reopened after additional evidence."


def test_conflict_detail_and_resolution_are_isolated_to_the_owning_investigation(client, test_db):
    first_left, _, _, _ = add_job_with_product(
        test_db, job_name="First PDF", source_type="pdf", filename="first.pdf",
        product_name="Motor", brand="Acme", category="Motor", power="5.5 kW", voltage="400 V", page_number=1,
    )
    first_right, _, _, _ = add_job_with_product(
        test_db, job_name="First CSV", source_type="csv", filename="first.csv",
        product_name="Motor", brand="Acme", category="Motor", power="5.5 kW", voltage="415 V", row_number=2,
    )
    second = create_investigation(client, "Unrelated investigation")
    first = create_investigation(client, "Owning investigation")
    attach(client, first["id"], first_left.id)
    attach(client, first["id"], first_right.id)
    conflict_id = next(item for item in conflict_report(client, first["id"])["conflicts"] if item["attribute_name"] == "voltage")["conflict_id"]

    assert client.get(f"/api/v1/investigations/{second['id']}/conflicts/{conflict_id}").status_code == 404
    assert client.post(
        f"/api/v1/investigations/{second['id']}/conflicts/{conflict_id}/resolve",
        json={"action": "MARK_AS_HUMAN_REVIEW"},
    ).status_code == 404


def test_conflict_report_exposes_persisted_resolution_status_for_frontend_filters(client, test_db):
    left, _, _, _ = add_job_with_product(
        test_db, job_name="PDF", source_type="pdf", filename="motor.pdf",
        product_name="Motor", brand="Acme", category="Motor", power="5.5 kW", voltage="400 V", page_number=1,
    )
    right, _, _, _ = add_job_with_product(
        test_db, job_name="CSV", source_type="csv", filename="motor.csv",
        product_name="Motor", brand="Acme", category="Motor", power="5.5 kW", voltage="415 V", row_number=2,
    )
    investigation = create_investigation(client, "Resolution filter contract")
    attach(client, investigation["id"], left.id)
    attach(client, investigation["id"], right.id)
    first_report = conflict_report(client, investigation["id"])
    voltage = next(item for item in first_report["conflicts"] if item["attribute_name"] == "voltage")
    assert voltage["resolution_status"] == "unresolved"
    assert voltage["conflict_id"]

    client.post(
        f"/api/v1/investigations/{investigation['id']}/conflicts/{voltage['conflict_id']}/resolve",
        json={"action": "MARK_AS_HUMAN_REVIEW", "reasoning": "Evidence assigned to manual review."},
    ).raise_for_status()
    refreshed = conflict_report(client, investigation["id"])
    refreshed_voltage = next(item for item in refreshed["conflicts"] if item["attribute_name"] == "voltage")
    assert refreshed_voltage["resolution_status"] == "human_review"
    assert refreshed_voltage["resolution_action"] == "MARK_AS_HUMAN_REVIEW"
    assert refreshed_voltage["resolution_reason"] == "Evidence assigned to manual review."
