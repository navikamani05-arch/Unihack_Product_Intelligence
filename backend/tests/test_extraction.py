"""Unit and API tests for Phase 2C AI product intelligence extraction."""
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models.conflict import EvidenceChunk
from app.models.ingestion import IngestionJob, RawDocumentSource
from app.schemas.product_schema import AttributeExtractionSchema, ProductExtractionResponse
from app.services.llm_extraction_service import LLMExtractionError, LLMExtractionService


class FakeLLMClient:
    def __init__(self, content: str):
        self.content = content
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self.create)
        )

    def create(self, **kwargs):
        self.request = kwargs
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))]
        )


@pytest.fixture
def valid_chunks():
    return [
        {
            "evidence_chunk_id": "pdf_abc123",
            "text": "Industrial motor MTR-100 manufactured by Acme. Rated voltage 230 V AC.",
            "source_type": "pdf",
            "source_identifier": "motor.pdf",
            "source_url": None,
            "page_number": 2,
            "row_number": None,
        }
    ]


def valid_payload(chunk_id="pdf_abc123"):
    return {
        "product_name": "Industrial Motor",
        "sku": "MTR-100",
        "brand": "Acme",
        "category": "Motor",
        "description": "Industrial motor.",
        "attributes": [
            {
                "attribute_name": "rated_voltage",
                "raw_value": "230 V AC",
                "normalized_value": "230",
                "unit": "V",
                "confidence_score": 0.96,
                "evidence_chunk_id": chunk_id,
                "page_number": None,
                "row_number": None,
            }
        ],
        "missing_attributes": ["rpm"],
    }


def test_valid_structured_extraction(monkeypatch, valid_chunks):
    fake_client = FakeLLMClient(json.dumps({"products": [valid_payload()]}))
    monkeypatch.setattr(LLMExtractionService, "get_client", classmethod(lambda cls: fake_client))

    result = LLMExtractionService.extract_from_chunks(valid_chunks, {"source_type": "pdf"})
    product = result["products"][0]

    assert product["product_name"] == "Industrial Motor"
    assert product["category"] == "Motor"
    assert product["attributes"][0]["attribute_name"] == "rated_voltage"
    assert product["attributes"][0]["page_number"] == 2
    assert fake_client.request["response_format"]["type"] == "json_object"


def test_malformed_llm_response_is_rejected(monkeypatch, valid_chunks):
    fake_client = FakeLLMClient("not valid json")
    monkeypatch.setattr(LLMExtractionService, "get_client", classmethod(lambda cls: fake_client))

    with pytest.raises(LLMExtractionError, match="malformed JSON"):
        LLMExtractionService.extract_from_chunks(valid_chunks, {"source_type": "pdf"})


def test_missing_attributes_are_preserved_without_hallucination(monkeypatch, valid_chunks):
    payload = valid_payload()
    payload["attributes"] = []
    payload["missing_attributes"] = ["rpm", "phase"]
    fake_client = FakeLLMClient(json.dumps({"products": [payload]}))
    monkeypatch.setattr(LLMExtractionService, "get_client", classmethod(lambda cls: fake_client))

    result = LLMExtractionService.extract_from_chunks(valid_chunks, {"source_type": "pdf"})
    product = result["products"][0]

    assert product["attributes"] == []
    assert product["missing_attributes"] == ["rpm", "phase", "sku"]
    assert product["sku"] is None


def test_provenance_is_filled_from_authoritative_chunk(monkeypatch):
    chunks = [
        {
            "evidence_chunk_id": "web_123",
            "text": "Voltage 24 V DC",
            "source_type": "website",
            "source_identifier": "https://example.test/product",
            "source_url": "https://example.test/product",
            "page_number": None,
            "row_number": None,
        }
    ]
    payload = valid_payload("web_123")
    payload["attributes"][0]["raw_value"] = "24 V DC"
    payload["attributes"][0]["normalized_value"] = "24"
    payload["attributes"][0]["page_number"] = 99
    payload["attributes"][0]["row_number"] = 88
    fake_client = FakeLLMClient(json.dumps({"products": [payload]}))
    monkeypatch.setattr(LLMExtractionService, "get_client", classmethod(lambda cls: fake_client))

    result = LLMExtractionService.extract_from_chunks(chunks, {"source_type": "website"})
    product = result["products"][0]
    attribute = product["attributes"][0]

    assert attribute["source_type"] == "website"
    assert attribute["source_url"] == "https://example.test/product"
    assert attribute["source_identifier"] == "https://example.test/product"
    assert attribute["page_number"] is None
    assert attribute["row_number"] is None


def test_unsupported_category_falls_back_to_other(monkeypatch, valid_chunks):
    payload = valid_payload()
    payload["category"] = "UnapprovedCategory"
    fake_client = FakeLLMClient(json.dumps({"products": [payload]}))
    monkeypatch.setattr(LLMExtractionService, "get_client", classmethod(lambda cls: fake_client))

    result = LLMExtractionService.extract_from_chunks(valid_chunks, {"source_type": "pdf"})
    product = result["products"][0]
    assert product["category"] == "Other"


def test_pydantic_validation_rejects_invalid_confidence():
    with pytest.raises(ValueError):
        AttributeExtractionSchema(
            attribute_name="voltage",
            raw_value="230 V",
            normalized_value="230",
            confidence_score=1.5,
        )


def test_provider_configuration_error(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("app.services.llm_extraction_service.settings.openai_api_key", None)

    with pytest.raises(LLMExtractionError, match="not configured"):
        LLMExtractionService.get_client()


@pytest.fixture
def api_db(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'extraction.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = session_factory()
    yield session
    session.close()


def test_extraction_api_persists_product_and_provenance(monkeypatch, api_db):
    job = IngestionJob(job_name="Motor PDF", status="completed", source_type="pdf")
    api_db.add(job)
    api_db.flush()
    source = RawDocumentSource(
        job_id=job.id,
        file_name="motor.pdf",
        source_url=None,
        raw_text_content="Rated voltage: 230 V AC",
    )
    api_db.add(source)
    api_db.flush()
    chunk = EvidenceChunk(
        job_id=job.id,
        source_id=source.id,
        stable_chunk_id="pdf_abc123",
        snippet_text="Rated voltage: 230 V AC",
        page_number=2,
        source_type="pdf",
        source_identifier="motor.pdf",
    )
    api_db.add(chunk)
    api_db.commit()

    monkeypatch.setattr(
        LLMExtractionService,
        "extract_from_chunks",
        classmethod(lambda cls, chunks, source_metadata: {"products": [ProductExtractionResponse.model_validate(valid_payload()).model_dump()]}),
    )

    def override_get_db():
        yield api_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = TestClient(app).post(f"/api/v1/extract/{job.id}?wait=true")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["extracted_products"][0]["category"] == "Motor"
    assert body["extracted_products"][0]["attributes"][0]["page_number"] == 2

    api_db.expire_all()
    stored_chunk = api_db.query(EvidenceChunk).filter(EvidenceChunk.id == chunk.id).one()
    assert stored_chunk.attribute_id is not None
    attribute = stored_chunk.attribute
    assert attribute.evidence_chunk_id == "pdf_abc123"
    assert attribute.source_type == "pdf"
    assert attribute.page_number == 2


def test_explicit_sku_is_preserved_with_authoritative_provenance(monkeypatch):
    chunks = [
        {
            "evidence_chunk_id": "csv_row_1",
            "text": "SKU: SIM-001\nProduct Name: SIMOTICS GP Motor\nVoltage: 400V",
            "source_type": "csv",
            "source_identifier": "product_catalog.csv",
            "source_url": None,
            "page_number": None,
            "row_number": 1,
        }
    ]
    payload = valid_payload("csv_row_1")
    payload["sku"] = "SIM-001"
    payload["sku_evidence_chunk_id"] = "csv_row_1"
    fake_client = FakeLLMClient(json.dumps({"products": [payload]}))
    monkeypatch.setattr(LLMExtractionService, "get_client", classmethod(lambda cls: fake_client))

    result = LLMExtractionService.extract_from_chunks(chunks, {"source_type": "csv"})["products"][0]

    assert result["sku"] == "SIM-001"
    assert result["sku_evidence_chunk_id"] == "csv_row_1"
    assert result["sku_source_type"] == "csv"
    assert result["sku_source_identifier"] == "product_catalog.csv"
    assert result["sku_row_number"] == 1
    assert "sku" not in result["missing_attributes"]


def test_unlabelled_sku_is_never_hallucinated(monkeypatch):
    chunks = [
        {
            "evidence_chunk_id": "pdf_without_id",
            "text": "SIMOTICS GP low-voltage motor. Rated voltage: 400 V.",
            "source_type": "pdf",
            "source_identifier": "motor.pdf",
            "source_url": None,
            "page_number": 4,
            "row_number": None,
        }
    ]
    payload = valid_payload("pdf_without_id")
    payload["sku"] = "SIM-GUESSED-001"
    payload["sku_evidence_chunk_id"] = "pdf_without_id"
    fake_client = FakeLLMClient(json.dumps({"products": [payload]}))
    monkeypatch.setattr(LLMExtractionService, "get_client", classmethod(lambda cls: fake_client))

    result = LLMExtractionService.extract_from_chunks(chunks, {"source_type": "pdf"})["products"][0]

    assert result["sku"] is None
    assert result["sku_evidence_chunk_id"] is None
    assert "sku" in result["missing_attributes"]


@pytest.mark.parametrize(
    ("value", "unit", "expected"),
    [
        ("0.09 to 1000 kW kW", "kW", "0.09 to 1000 kW"),
        ("400 V V", "V", "400 V"),
        ("5.5 kW", "kW", "5.5 kW"),
        ("12 kg", "kg", "12 kg"),
        ("25 mm", "mm", "25 mm"),
        ("8 A", "A", "8 A"),
        ("50 Hz", "Hz", "50 Hz"),
    ],
)
def test_duplicate_units_are_normalized_without_removing_single_units(monkeypatch, value, unit, expected):
    chunks = [
        {
            "evidence_chunk_id": "pdf_unit",
            "text": f"Power range: {value}",
            "source_type": "pdf",
            "source_identifier": "ranges.pdf",
            "source_url": None,
            "page_number": 3,
            "row_number": None,
        }
    ]
    payload = {
        "product_name": "Drive",
        "sku": None,
        "attributes": [
            {
                "attribute_name": "power_range",
                "raw_value": value,
                "normalized_value": value,
                "unit": unit,
                "confidence_score": 0.96,
                "evidence_chunk_id": "pdf_unit",
                "page_number": 3,
                "row_number": None,
            }
        ],
        "missing_attributes": [],
    }
    fake_client = FakeLLMClient(json.dumps({"products": [payload]}))
    monkeypatch.setattr(LLMExtractionService, "get_client", classmethod(lambda cls: fake_client))

    result = LLMExtractionService.extract_from_chunks(chunks, {"source_type": "pdf"})["products"][0]
    attribute = result["attributes"][0]

    assert attribute["raw_value"] == value
    assert attribute["normalized_value"] == expected
    assert attribute["confidence_score"] == (0.75 if expected != value else 0.99)


@pytest.mark.parametrize(
    "chunk",
    [
        {
            "evidence_chunk_id": "pdf_page_2",
            "text": "SKU: PDF-001\nVoltage: 230 V",
            "source_type": "pdf",
            "source_identifier": "motor.pdf",
            "source_url": None,
            "page_number": 2,
            "row_number": None,
        },
        {
            "evidence_chunk_id": "web_source",
            "text": "SKU: WEB-001\nVoltage: 24 V",
            "source_type": "website",
            "source_identifier": "https://example.test/product",
            "source_url": "https://example.test/product",
            "page_number": None,
            "row_number": None,
        },
        {
            "evidence_chunk_id": "csv_row_4",
            "text": "SKU: CSV-001\nVoltage: 400 V",
            "source_type": "csv",
            "source_identifier": "catalog.csv",
            "source_url": None,
            "page_number": None,
            "row_number": 4,
        },
    ],
)
def test_pdf_website_and_csv_provenance_remains_authoritative(monkeypatch, chunk):
    payload = valid_payload(chunk["evidence_chunk_id"])
    payload["sku"] = None
    payload["attributes"][0]["raw_value"] = chunk["text"].split("Voltage: ", 1)[1]
    payload["attributes"][0]["normalized_value"] = payload["attributes"][0]["raw_value"]
    payload["attributes"][0]["unit"] = "V"
    fake_client = FakeLLMClient(json.dumps({"products": [payload]}))
    monkeypatch.setattr(LLMExtractionService, "get_client", classmethod(lambda cls: fake_client))

    result = LLMExtractionService.extract_from_chunks([chunk], {"source_type": chunk["source_type"]})["products"][0]
    attribute = result["attributes"][0]

    assert attribute["source_type"] == chunk["source_type"]
    assert attribute["source_identifier"] == chunk["source_identifier"]
    assert attribute["source_url"] == chunk["source_url"]
    assert attribute["page_number"] == chunk["page_number"]
    assert attribute["row_number"] == chunk["row_number"]


def test_missing_attribute_has_no_confidence_score():
    attribute = AttributeExtractionSchema(
        attribute_name="sku",
        raw_value=None,
        normalized_value=None,
        confidence_score=None,
    )
    assert attribute.confidence_score is None



def test_large_evidence_input_is_processed_in_bounded_batches(monkeypatch):
    monkeypatch.setattr(settings, "llm_batch_size", 50)
    chunks = [
        {
            "evidence_chunk_id": f"csv_row_{index}",
            "text": f"SKU: SKU-{index}",
            "source_type": "csv",
            "source_identifier": "catalog.csv",
            "source_url": None,
            "page_number": None,
            "row_number": index,
        }
        for index in range(1, 121)
    ]
    calls = []

    def fake_batch(cls, batch, source_metadata):
        calls.append((batch, source_metadata))
        return {"products": [{"row_number": batch[0]["row_number"]}]}

    monkeypatch.setattr(LLMExtractionService, "_extract_single_batch", classmethod(fake_batch))

    result = LLMExtractionService.extract_from_chunks(chunks, {"source_type": "csv"})

    assert [len(batch) for batch, _ in calls] == [50, 50, 20]
    assert [chunk["row_number"] for batch, _ in calls for chunk in batch] == list(range(1, 121))
    assert len(result["products"]) == 3


class HtmlProviderClient:
    def __init__(self):
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        raise RuntimeError("502 Bad Gateway: <html><body>upstream proxy error</body></html>")


def test_html_provider_failure_is_converted_to_readable_extraction_error(monkeypatch, valid_chunks):
    monkeypatch.setattr(LLMExtractionService, "get_client", classmethod(lambda cls: HtmlProviderClient()))

    with pytest.raises(LLMExtractionError, match="HTML/non-JSON response"):
        LLMExtractionService.extract_from_chunks(valid_chunks, {"source_type": "pdf"})


def test_extraction_endpoint_returns_json_for_provider_failure(monkeypatch, api_db):
    job = IngestionJob(job_name="Provider failure", status="completed", source_type="csv")
    api_db.add(job)
    api_db.flush()
    source = RawDocumentSource(job_id=job.id, file_name="catalog.csv", raw_text_content="SKU,Name\\nSKU-1,Motor")
    api_db.add(source)
    api_db.flush()
    api_db.add(
        EvidenceChunk(
            job_id=job.id,
            source_id=source.id,
            stable_chunk_id="csv_row_1",
            snippet_text="SKU: SKU-1\\nName: Motor",
            source_type="csv",
            source_identifier="catalog.csv",
            row_number=1,
        )
    )
    api_db.commit()

    monkeypatch.setattr(
        LLMExtractionService,
        "extract_from_chunks",
        classmethod(lambda cls, chunks, source_metadata: (_ for _ in ()).throw(LLMExtractionError("HTML/non-JSON provider response"))),
    )

    def override_get_db():
        yield api_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = TestClient(app).post(f"/api/v1/extract/{job.id}?wait=true")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 502
    assert response.headers["content-type"].startswith("application/json")
    assert "HTML/non-JSON provider response" in response.json()["detail"]
