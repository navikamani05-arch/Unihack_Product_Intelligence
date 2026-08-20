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
from app.models.reference_data import ProductNormalizationDecision, ReferenceDataset
from app.services.reference_data_service import ReferenceDataService


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
def reference_dir(tmp_path, monkeypatch):
    directory = tmp_path / "reference_data"
    monkeypatch.setattr(settings, "reference_data_directory", str(directory))
    return directory


def write_csv(path: Path, headers: list[str], rows: list[dict]):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def import_csv(db, tmp_path, dataset_type, headers, rows, name=None):
    path = tmp_path / (name or f"{dataset_type}.csv")
    write_csv(path, headers, rows)
    return ReferenceDataService(db).import_dataset(path, dataset_type=dataset_type, version="official-test")


def manufacturer_rows():
    return [
        {"Manufacturer Name": "Acme Corporation", "Manufacturer Code": "ACME", "Alternate Names": "ACME|Acme Corp", "Brand Name": "Acme Industrial", "Brand Code": "ACI", "Brand Alternate Names": "Acme"},
        {"Manufacturer Name": "Beta Works", "Manufacturer Code": "BETA", "Alternate Names": "Beta", "Brand Name": "Beta Industrial", "Brand Code": "BI", "Brand Alternate Names": "BetaLine"},
    ]


MANUFACTURER_HEADERS = ["Manufacturer Name", "Manufacturer Code", "Alternate Names", "Brand Name", "Brand Code", "Brand Alternate Names"]


def test_registry_declares_missing_official_datasets_without_fabricating_values(test_db):
    registry = ReferenceDataService(test_db).registry()
    assert {item["dataset_type"] for item in registry} >= {"manufacturer_brand", "lov", "uom", "fraction"}
    assert all(item["status"] == "not_available" for item in registry)
    response = ReferenceDataService(test_db).resolve_manufacturer("ACME")
    assert response["status"] == "REFERENCE_DATA_UNAVAILABLE"
    assert response["canonical_name"] is None


def test_official_manufacturer_and_brand_import_supports_exact_alias_fuzzy_and_mismatch_cases(test_db, tmp_path):
    result = import_csv(test_db, tmp_path, "manufacturer_brand", MANUFACTURER_HEADERS, manufacturer_rows())
    service = ReferenceDataService(test_db)

    exact = service.resolve_manufacturer("ACME")
    alias = service.resolve_manufacturer("Acme Corp")
    fuzzy = service.resolve_manufacturer("Acme Corporatoin")
    brand = service.resolve_brand("Acme", "Acme Corporation")
    mismatch = service.resolve_brand("Acme", "Beta Works")

    assert result["row_count"] == 2
    assert exact["status"] == "APPROVED" and exact["match_type"] == "exact"
    assert alias["canonical_name"] == "Acme Corporation" and alias["match_type"] == "alias"
    assert fuzzy["status"] in {"CANDIDATE", "AMBIGUOUS"}
    assert brand["status"] == "APPROVED" and brand["canonical_name"] == "Acme Industrial"
    assert mismatch["status"] == "BRAND_MANUFACTURER_MISMATCH"


def test_lov_is_validated_only_within_the_given_classpath_and_attribute(test_db, tmp_path):
    headers = ["Class Path", "Leaf Node", "Attribute Label", "Attribute Values", "Filtering Flag", "Guidelines", "Remarks"]
    import_csv(test_db, tmp_path, "lov", headers, [{
        "Class Path": "Plumbing > Faucets", "Leaf Node": "Kitchen Faucets", "Attribute Label": "Finish", "Attribute Values": "Chrome|Brushed Nickel", "Filtering Flag": "Y", "Guidelines": "Official finish values", "Remarks": "No aliases",
    }])
    service = ReferenceDataService(test_db)

    approved = service.resolve_attribute("Plumbing > Faucets", "Kitchen Faucets", "Finish", "Chrome")
    invalid = service.resolve_attribute("Plumbing > Faucets", "Kitchen Faucets", "Finish", "Matte Black")
    wrong_scope = service.resolve_attribute("Plumbing > Fittings", "Kitchen Faucets", "Finish", "Chrome")

    assert approved["status"] == "APPROVED" and approved["allowed"] is True
    assert invalid["status"] == "NOT_IN_APPROVED_LOV" and invalid["allowed"] is False
    assert wrong_scope["status"] == "NOT_IN_APPROVED_LOV"


def test_official_uom_alias_and_fraction_normalization_preserve_original_display_value(test_db, tmp_path):
    import_csv(test_db, tmp_path, "uom", ["UOM", "Display UOM", "Synonyms"], [
        {"UOM": "inch", "Display UOM": "in", "Synonyms": "inches|inch"},
        {"UOM": "volt", "Display UOM": "V", "Synonyms": "volts|v"},
    ])
    import_csv(test_db, tmp_path, "fraction", ["Decimal", "Fraction"], [
        {"Decimal": "0.25", "Fraction": "1/4"},
        {"Decimal": "0.5", "Fraction": "1/2"},
    ])
    service = ReferenceDataService(test_db)

    uom = service.normalize_uom("24 inches")
    fraction = service.normalize_fraction("50.25 in")

    assert uom["status"] == "APPROVED"
    assert uom["original_value"] == "24 inches"
    assert uom["normalized_value"] == "24 in"
    assert fraction["status"] == "APPROVED"
    assert fraction["original_value"] == "50.25 in"
    assert fraction["normalized_value"] == "50 1/4 in"


def test_extraction_validation_records_decisions_but_keeps_source_provenance_and_original_attributes(test_db, tmp_path):
    import_csv(test_db, tmp_path, "manufacturer_brand", MANUFACTURER_HEADERS, manufacturer_rows())
    product = ProductRecord(
        sku="ACME-001", name="Acme product", manufacturer="ACME", sku_evidence_chunk_id="csv-row-2",
        sku_source_type="csv", sku_source_identifier="source.csv", sku_row_number=2,
    )
    test_db.add(product)
    test_db.flush()
    attribute = ProductAttribute(
        product_id=product.id, attribute_name="Brand", raw_value="Acme", normalized_value="Acme",
        source_type="csv", source_identifier="source.csv", row_number=2, evidence_chunk_id="csv-row-2",
    )
    test_db.add(attribute)
    test_db.commit()

    ReferenceDataService(test_db).validate_extracted_product(product)
    test_db.commit()
    test_db.refresh(attribute)
    recorded = test_db.query(ProductNormalizationDecision).filter_by(product_id=product.id).all()

    assert recorded
    assert attribute.raw_value == "Acme" and attribute.source_identifier == "source.csv"
    assert any(decision.decision_type == "manufacturer_resolution" and decision.status == "APPROVED" for decision in recorded)
    assert any((decision.provenance_snapshot or {}).get("source_type") == "csv" and (decision.provenance_snapshot or {}).get("row_number") == 2 for decision in recorded)


def test_reference_data_api_supports_status_import_and_explainable_resolution(client, reference_dir, tmp_path):
    status_response = client.get("/api/v1/reference-data/status")
    assert status_response.status_code == 200
    assert any(item["status"] == "not_available" for item in status_response.json()["datasets"])

    source = tmp_path / "manufacturers.csv"
    write_csv(source, MANUFACTURER_HEADERS, manufacturer_rows())
    with source.open("rb") as handle:
        import_response = client.post("/api/v1/reference-data/import", data={"dataset_type": "manufacturer_brand", "version": "2026.1"}, files={"file": (source.name, handle, "text/csv")})
    resolve_response = client.post("/api/v1/resolve/manufacturer", json={"value": "ACME"})
    brand_response = client.get("/api/v1/brands/search", params={"q": "Acme", "manufacturer": "Acme Corporation"})

    assert import_response.status_code == 201
    assert import_response.json()["status"] == "available"
    assert resolve_response.status_code == 200 and resolve_response.json()["canonical_name"] == "Acme Corporation"
    assert brand_response.status_code == 200 and brand_response.json()["status"] == "APPROVED"


def test_duplicate_dataset_import_is_replaced_by_versioned_active_record_without_cross_type_contamination(test_db, tmp_path):
    first = import_csv(test_db, tmp_path, "uom", ["UOM", "Display UOM", "Synonyms"], [{"UOM": "volt", "Display UOM": "V", "Synonyms": "volts"}], "uom_v1.csv")
    second = import_csv(test_db, tmp_path, "uom", ["UOM", "Display UOM", "Synonyms"], [{"UOM": "ampere", "Display UOM": "A", "Synonyms": "amps"}], "uom_v2.csv")
    active = test_db.query(ReferenceDataset).filter_by(dataset_type="uom", is_active=True).all()

    assert first["id"] != second["id"]
    assert len(active) == 1 and active[0].id == second["id"]
    assert ReferenceDataService(test_db).normalize_uom("4 amps")["status"] == "APPROVED"
    assert ReferenceDataService(test_db).normalize_uom("400 volts")["status"] == "NOT_IN_OFFICIAL_UOM"


def test_category_specific_lov_datasets_are_resolved_across_all_active_official_sources(test_db, tmp_path):
    headers = ["Class Path", "Leaf Node", "Attribute Label", "Attribute Values"]
    import_csv(test_db, tmp_path, "faucets_lov", headers, [{
        "Class Path": "Plumbing > Faucets", "Leaf Node": "Kitchen Faucets",
        "Attribute Label": "Finish", "Attribute Values": "Chrome",
    }], "official_faucets_lov.csv")
    import_csv(test_db, tmp_path, "fittings_lov", headers, [{
        "Class Path": "Plumbing > Fittings", "Leaf Node": "Pipe Fittings",
        "Attribute Label": "Finish", "Attribute Values": "Galvanized",
    }], "official_fittings_lov.csv")
    service = ReferenceDataService(test_db)

    faucet = service.resolve_attribute("Plumbing > Faucets", "Kitchen Faucets", "Finish", "Chrome")
    fitting = service.resolve_attribute("Plumbing > Fittings", "Pipe Fittings", "Finish", "Galvanized")

    assert faucet["status"] == "APPROVED" and faucet["reference_dataset"] == "Faucets LOV"
    assert fitting["status"] == "APPROVED" and fitting["reference_dataset"] == "Fittings LOV"


def test_lov_lookup_api_searches_all_active_category_specific_datasets(client, test_db, tmp_path):
    headers = ["Class Path", "Leaf Node", "Attribute Label", "Attribute Values"]
    import_csv(test_db, tmp_path, "faucets_lov", headers, [{
        "Class Path": "Plumbing > Faucets", "Leaf Node": "Kitchen Faucets",
        "Attribute Label": "Finish", "Attribute Values": "Chrome",
    }], "official_faucets_lookup.csv")
    import_csv(test_db, tmp_path, "fittings_lov", headers, [{
        "Class Path": "Plumbing > Fittings", "Leaf Node": "Pipe Fittings",
        "Attribute Label": "Finish", "Attribute Values": "Galvanized",
    }], "official_fittings_lookup.csv")

    response = client.get("/api/v1/lov/Plumbing%20%3E%20Fittings", params={"attribute": "Finish"})

    assert response.status_code == 200
    assert response.json()["status"] == "AVAILABLE"
    assert response.json()["entries"][0]["attribute_values"] == "Galvanized"
    assert response.json()["entries"][0]["reference_dataset"] == "Fittings LOV"
