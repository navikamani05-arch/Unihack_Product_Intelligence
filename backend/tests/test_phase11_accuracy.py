from types import SimpleNamespace

import pandas as pd

from app.services.enrichment.output_builder import build_output
from app.services.official_ground_truth_service import aggregate
from app.services.text_normalization import normalize_product_name


def test_product_name_normalization_removes_identifier_and_merchandising_suffixes_only():
    assert normalize_product_name("PDSH4816AF Dishwasher SS - Display Only", "PDSH4816AF") == "Dishwasher"
    assert normalize_product_name("  SKU-1   Industrial Motor  ", "SKU-1") == "Industrial Motor"
    assert normalize_product_name("Industrial Motor", "OTHER") == "Industrial Motor"


def test_source_unavailable_is_separate_from_missing_generated_value():
    product = SimpleNamespace(
        sku="SKU-1",
        name="SKU-1 Industrial Motor",
        description="SKU-1 Industrial Motor",
        manufacturer="Maker A",
        attributes=[],
    )
    frame = pd.DataFrame([
        {
            "Mfg_Part_Num": "SKU-1",
            "Product Name": "Industrial Motor",
            "ATTRIBUTE_LABEL 1": "Voltage",
            "ATTRIBUTE_VALUE 1": "400 V",
        }
    ])

    result = aggregate(frame, [product], "Mfg_Part_Num")

    assert result["overall_match_rate"] == 50.0
    assert result["overall_evaluation_rate"] == 100.0
    assert result["exact_matches"] == 1
    assert result["source_data_unavailable"] == 1
    assert result["pipeline_missing"] == 0
    mismatch = next(item for item in result["mismatches"] if item["field_name"] == "ATTRIBUTE_VALUE 1")
    assert mismatch["result"] == "MISSING"
    assert mismatch["availability"] == "source_data_unavailable"


def test_build_output_promotes_non_placeholder_brand_alias_without_losing_raw_attributes():
    product = SimpleNamespace(id=1, sku="SKU-1", name="SKU-1 Motor", manufacturer="Maker A", category="Motors")
    run = SimpleNamespace(
        id=1,
        category="Motors",
        category_path=[],
        category_confidence=0.9,
        product_understanding={},
        missing_attributes=[],
        overall_confidence=0.95,
        product_status="READY",
    )
    enriched = [
        {
            "attribute_id": 4,
            "name": "E1_Brand",
            "raw_value": "Acme",
            "normalized_value": "Acme",
            "unit": None,
            "confidence": 0.99,
            "evidence": [{"source_type": "csv", "source_identifier": "catalog.csv", "row_number": 2}],
        }
    ]

    output = build_output(product, run, enriched, [], [])

    assert output["brand"] == "Acme"
    assert output["product_name"] == "Motor"
    assert output["attributes"]["E1_Brand"]["raw_value"] == "Acme"
