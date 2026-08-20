"""Configurable OpenAI-compatible LLM service for product intelligence extraction."""
import json
import os
import re
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

from openai import OpenAI
from pydantic import ValidationError

from app.config import settings
from app.schemas.product_schema import AttributeExtractionSchema, ProductExtractionResponse
from app.utils.logger import logger


class LLMExtractionError(Exception):
    """Raised when an LLM response cannot be safely used."""


class LLMExtractionService:
    """Extract structured product information from persisted evidence chunks."""

    DEFAULT_CATEGORIES = (
        "Motor",
        "Pump",
        "Valve",
        "Sensor",
        "Bearing",
        "Compressor",
        "Other",
    )
    _IDENTIFIER_LABEL_PATTERN = re.compile(
        r"\b(?:sku|product\s*(?:id|identifier|number|no\.?)|part\s*(?:number|no\.?)|"
        r"catalog(?:ue)?\s*(?:number|no\.?)|order\s*(?:number|no\.?)|"
        r"item\s*(?:id|number|no\.?)|model\s*(?:number|no\.?))\b\s*[:#-]?\s*"
        r"(?P<value>[A-Za-z0-9][A-Za-z0-9._/\-]{1,99})",
        re.IGNORECASE,
    )
    _COMMON_UNITS = ("kW", "V", "kg", "mm", "A", "Hz")

    @classmethod
    def categories(cls) -> List[str]:
        """Return configurable product categories from PRODUCT_CATEGORIES."""
        configured = os.getenv("PRODUCT_CATEGORIES")
        if configured:
            values = [value.strip() for value in configured.split(",") if value.strip()]
            if values:
                return values
        return list(cls.DEFAULT_CATEGORIES)

    @classmethod
    def get_client(cls) -> OpenAI:
        """Create a client using environment-aware configuration."""
        provider = (os.getenv("LLM_PROVIDER") or settings.llm_provider or "openai_compatible").lower()
        api_key = os.getenv("OPENAI_API_KEY") or settings.openai_api_key
        base_url = (
            os.getenv("OPENAI_API_BASE")
            or os.getenv("OPENAI_BASE_URL")
            or settings.openai_api_base
        )

        if not api_key or api_key.strip() in {"sk-placeholder-key", "your-api-key", "changeme"}:
            logger.error("LLM extraction failed because the API key is missing or a placeholder.")
            raise LLMExtractionError(
                "LLM provider is not configured. Set OPENAI_API_KEY before starting extraction."
            )

        client_kwargs: Dict[str, Any] = {
            "api_key": api_key,
            "timeout": float(settings.llm_timeout_seconds),
            "max_retries": max(0, int(settings.llm_max_retries)),
        }
        if base_url:
            client_kwargs["base_url"] = base_url

        logger.info("Initializing LLM client: provider=%s, base_url=%s", provider, base_url)
        return OpenAI(**client_kwargs)

    @classmethod
    def _response_schema(cls) -> Dict[str, Any]:
        """Build the JSON shape the model is instructed to return."""
        nullable_string = {"type": ["string", "null"]}
        nullable_integer = {"type": ["integer", "null"]}
        nullable_number = {"type": ["number", "null"], "minimum": 0, "maximum": 1}
        attribute_schema = {
            "type": "object",
            "properties": {
                "attribute_name": {"type": "string"},
                "raw_value": nullable_string,
                "normalized_value": nullable_string,
                "unit": nullable_string,
                "confidence_score": nullable_number,
                "evidence_chunk_id": nullable_string,
                "page_number": nullable_integer,
                "row_number": nullable_integer,
            },
            "required": [
                "attribute_name",
                "raw_value",
                "normalized_value",
                "unit",
                "confidence_score",
                "evidence_chunk_id",
                "page_number",
                "row_number",
            ],
            "additionalProperties": False,
        }
        product_schema = {
            "type": "object",
            "properties": {
                "product_name": nullable_string,
                "sku": nullable_string,
                "sku_evidence_chunk_id": nullable_string,
                "brand": nullable_string,
                "category": nullable_string,
                "description": nullable_string,
                "attributes": {"type": "array", "items": attribute_schema},
                "missing_attributes": {"type": "array", "items": {"type": "string"}},
            },
            "required": [
                "product_name",
                "sku",
                "sku_evidence_chunk_id",
                "brand",
                "category",
                "description",
                "attributes",
                "missing_attributes",
            ],
            "additionalProperties": False,
        }
        return {
            "type": "object",
            "properties": {"products": {"type": "array", "items": product_schema}},
            "required": ["products"],
            "additionalProperties": False,
        }

    @classmethod
    def _build_prompt(
        cls, chunks: List[Mapping[str, Any]], source_metadata: Mapping[str, Any]
    ) -> str:
        evidence = []
        for chunk in chunks:
            evidence.append(
                json.dumps(
                    {
                        "id": chunk.get("evidence_chunk_id") or chunk.get("chunk_id"),
                        "type": chunk.get("source_type"),
                        "src": chunk.get("source_identifier"),
                        "page": chunk.get("page_number"),
                        "row": chunk.get("row_number"),
                        "text": chunk.get("text", "")[:2000],
                    },
                    ensure_ascii=False,
                )
            )

        source_type = source_metadata.get("source_type", "unknown")
        instruction = "Extract industrial product intelligence from the evidence below."
        if source_type == "csv":
            instruction = (
                "Extract multiple products from this CSV catalog. Each evidence row represents "
                "a separate product. Extract every product represented in the supplied rows."
            )

        return f"""{instruction}

Allowed categories: {', '.join(cls.categories())}.

Rules:
- Use ONLY facts present in the supplied evidence. Do not invent values.
- Return null for a missing field. Never generate or infer a SKU/Product ID.
- Set `sku` only when an explicit source label identifies it as a SKU, product ID, part number, catalog number, order number, item ID, or model number. Cite that record with `sku_evidence_chunk_id`.
- If no such explicit identifier exists, return `sku: null` and `sku_evidence_chunk_id: null`, and include `sku` in `missing_attributes`.
- Every non-missing attribute MUST cite exactly one evidence_chunk_id from the supplied evidence.
- Preserve raw_value exactly as written in evidence. normalized_value may clean formatting, but must not change the factual value.
- For CSV sources, ensure every evidence row is processed as a separate product.
- Return JSON matching this schema:
{json.dumps(cls._response_schema(), indent=2)}

Job source metadata:
{json.dumps(dict(source_metadata), ensure_ascii=False)}

Evidence records:
{chr(10).join(evidence)}
"""

    @staticmethod
    def _append_missing(result: ProductExtractionResponse, attribute_name: str) -> None:
        """Record a missing attribute once, without creating a misleading attribute record."""
        normalized = attribute_name.strip()
        if normalized and normalized not in result.missing_attributes:
            result.missing_attributes.append(normalized)

    @classmethod
    def _normalize_unit_token(cls, unit: Optional[str]) -> Optional[str]:
        """Collapse an accidentally repeated unit token without removing a single valid unit."""
        if not unit:
            return unit
        cleaned = " ".join(str(unit).split())
        for known_unit in cls._COMMON_UNITS:
            repeated = re.compile(rf"^(?:{re.escape(known_unit)})(?:\s+{re.escape(known_unit)})+$", re.I)
            if repeated.fullmatch(cleaned):
                return known_unit
        return cleaned or None

    @classmethod
    def _normalize_duplicate_units(cls, value: Optional[str], unit: Optional[str]) -> Optional[str]:
        """Remove repeated terminal units such as 'kW kW' while preserving a single unit."""
        if value is None:
            return None
        normalized = str(value)
        candidates = [candidate for candidate in (unit, *cls._COMMON_UNITS) if candidate]
        for candidate in candidates:
            pattern = re.compile(
                rf"(?<![A-Za-z0-9])({re.escape(str(candidate))})(?:\s+\1)+(?![A-Za-z0-9])",
                re.IGNORECASE,
            )
            normalized = pattern.sub(lambda match: match.group(1), normalized)
        return normalized

    @classmethod
    def normalize_value_for_comparison(cls, value: Optional[str], unit: Optional[str] = None) -> str:
        """Canonicalize presentation variants for comparison without changing stored source values.

        The helper intentionally builds on duplicate-unit normalization already used by extraction.
        It accepts common spelling/case variants such as ``400V`` and ``400 volts`` while
        preserving the persisted raw and normalized values used for provenance display.
        """
        cleaned = cls._normalize_duplicate_units(value, unit) or ""
        cleaned = re.sub(r"(?<=\d)(?=[A-Za-z])", " ", str(cleaned))
        cleaned = " ".join(cleaned.split()).casefold()
        aliases = (
            (r"\bkilowatts?\b", "kw"),
            (r"\bwatts?\b", "w"),
            (r"\bvolts?\b", "v"),
            (r"\bamperes?\b|\bamps?\b", "a"),
            (r"\bhertz\b", "hz"),
            (r"\bkilograms?\b", "kg"),
            (r"\bmillimet(?:er|re)s?\b", "mm"),
        )
        for pattern, replacement in aliases:
            cleaned = re.sub(pattern, replacement, cleaned)
        cleaned = " ".join(cleaned.split()).rstrip(".,;:")

        if unit:
            canonical_unit = cls.normalize_value_for_comparison(str(unit), None)
            tokens = set(cleaned.split())
            if canonical_unit and canonical_unit not in tokens:
                cleaned = f"{cleaned} {canonical_unit}".strip()
        return cleaned

    @staticmethod
    def _collapsed(value: str) -> str:
        """Normalize whitespace only for evidence comparison, never for raw-value storage."""
        return re.sub(r"\s+", " ", value).strip().casefold()

    @classmethod
    def _confidence_from_evidence(
        cls, attribute: AttributeExtractionSchema, source_text: str, normalized_changed: bool
    ) -> Optional[float]:
        """Assign an evidence-derived confidence instead of trusting uniform model scores."""
        raw_value = attribute.raw_value
        if raw_value is None or not str(raw_value).strip():
            return None
        raw = str(raw_value)
        text = source_text or ""
        field_label = re.sub(r"[_\-]+", " ", attribute.attribute_name).casefold()
        compact_text = cls._collapsed(text)
        compact_raw = cls._collapsed(raw)

        if raw in text and field_label in compact_text:
            score = 0.99  # Explicit field/value pair in the authoritative evidence.
        elif raw in text:
            score = 0.95  # Exact value present in evidence.
        elif raw.casefold() in text.casefold():
            score = 0.88  # Direct value with only case normalization.
        elif compact_raw and compact_raw in compact_text:
            score = 0.55  # Weak formatting/whitespace match.
        else:
            return None  # No defensible evidence for the claimed value.

        if normalized_changed:
            return min(score, 0.75)  # Interpretation/normalization is medium confidence.
        return score

    @classmethod
    def _identifier_candidates(
        cls, chunks: List[Mapping[str, Any]]
    ) -> List[Tuple[str, Mapping[str, Any]]]:
        """Return explicit identifier values with their authoritative evidence chunks."""
        candidates: List[Tuple[str, Mapping[str, Any]]] = []
        for chunk in chunks:
            for match in cls._IDENTIFIER_LABEL_PATTERN.finditer(str(chunk.get("text") or "")):
                value = match.group("value").strip().rstrip(".,;:")
                if value:
                    candidates.append((value, chunk))
        return candidates

    @classmethod
    def _apply_identifier_provenance(
        cls, result: ProductExtractionResponse, chunks: List[Mapping[str, Any]]
    ) -> None:
        """Accept only explicitly labelled source identifiers and preserve their provenance."""
        cited_ids = {
            attribute.evidence_chunk_id
            for attribute in result.attributes
            if attribute.evidence_chunk_id
        }
        requested_id = result.sku_evidence_chunk_id
        if requested_id:
            cited_ids.add(requested_id)

        scoped_chunks = [
            chunk
            for chunk in chunks
            if not cited_ids
            or str(chunk.get("evidence_chunk_id") or chunk.get("chunk_id")) in cited_ids
        ]
        candidates = cls._identifier_candidates(scoped_chunks)
        if not candidates and len(chunks) == 1:
            candidates = cls._identifier_candidates(chunks)

        requested_sku = result.sku.strip() if isinstance(result.sku, str) else None
        selected: Optional[Tuple[str, Mapping[str, Any]]] = None
        if requested_sku:
            selected = next(
                (candidate for candidate in candidates if candidate[0].casefold() == requested_sku.casefold()),
                None,
            )

        # A unique, explicit ID in the product's cited evidence is safe to use even if the model omitted it.
        unique_candidates = {}
        for value, chunk in candidates:
            unique_candidates.setdefault(value.casefold(), (value, chunk))
        if selected is None and len(unique_candidates) == 1:
            selected = next(iter(unique_candidates.values()))

        if selected is None:
            result.sku = None
            result.sku_evidence_chunk_id = None
            result.sku_source_type = None
            result.sku_source_identifier = None
            result.sku_source_url = None
            result.sku_page_number = None
            result.sku_row_number = None
            cls._append_missing(result, "sku")
            return

        sku, chunk = selected
        result.sku = sku  # Preserve the source's original identifier spelling and punctuation.
        result.sku_evidence_chunk_id = str(chunk.get("evidence_chunk_id") or chunk.get("chunk_id"))
        result.sku_source_type = chunk.get("source_type")
        result.sku_source_identifier = chunk.get("source_identifier")
        result.sku_source_url = chunk.get("source_url")
        result.sku_page_number = chunk.get("page_number")
        result.sku_row_number = chunk.get("row_number")
        result.missing_attributes = [name for name in result.missing_attributes if name.casefold() != "sku"]

    @classmethod
    def _apply_authoritative_provenance(
        cls, result: ProductExtractionResponse, chunks: List[Mapping[str, Any]]
    ) -> ProductExtractionResponse:
        """Validate citations and fill all provenance from authoritative database records."""
        chunk_map = {
            str(chunk.get("evidence_chunk_id") or chunk.get("chunk_id")): chunk
            for chunk in chunks
            if chunk.get("evidence_chunk_id") or chunk.get("chunk_id")
        }

        allowed_categories = set(cls.categories())
        if result.category is not None and result.category not in allowed_categories:
            logger.warning(
                "LLM suggested category '%s' not in allowed list. Defaulting to 'Other'.",
                result.category,
            )
            result.category = "Other"

        normalized_attributes: List[AttributeExtractionSchema] = []
        for attribute in result.attributes:
            citation = attribute.evidence_chunk_id
            if not citation or citation not in chunk_map:
                logger.warning(
                    "Attribute '%s' cites invalid chunk '%s'. Skipping.",
                    attribute.attribute_name,
                    citation,
                )
                continue

            chunk = chunk_map[citation]
            if attribute.raw_value is None or not str(attribute.raw_value).strip():
                cls._append_missing(result, attribute.attribute_name)
                continue

            source_value = str(chunk.get("text") or "")
            original_normalized = attribute.normalized_value if attribute.normalized_value is not None else attribute.raw_value
            attribute.unit = cls._normalize_unit_token(attribute.unit)
            attribute.normalized_value = cls._normalize_duplicate_units(original_normalized, attribute.unit)
            normalized_changed = str(attribute.normalized_value or "") != str(attribute.raw_value)
            evidence_confidence = cls._confidence_from_evidence(attribute, source_value, normalized_changed)
            if evidence_confidence is None:
                logger.warning(
                    "Attribute '%s' has no matching value in cited evidence '%s'; treating as missing.",
                    attribute.attribute_name,
                    citation,
                )
                cls._append_missing(result, attribute.attribute_name)
                continue

            attribute.confidence_score = evidence_confidence
            attribute.evidence_chunk_id = citation
            attribute.source_type = chunk.get("source_type")
            attribute.source_identifier = chunk.get("source_identifier")
            attribute.source_url = chunk.get("source_url")
            attribute.page_number = chunk.get("page_number")
            attribute.row_number = chunk.get("row_number")
            normalized_attributes.append(attribute)

        result.attributes = normalized_attributes
        cls._apply_identifier_provenance(result, chunks)
        return result

    @classmethod
    def _apply_provenance_to_multi(
        cls, results: List[ProductExtractionResponse], chunks: List[Mapping[str, Any]]
    ) -> List[ProductExtractionResponse]:
        """Apply source-backed validation and provenance to multiple product results."""
        return [cls._apply_authoritative_provenance(product, chunks) for product in results]

    @classmethod
    def _extract_single_batch(
        cls, chunks: List[Mapping[str, Any]], source_metadata: Mapping[str, Any]
    ) -> Dict[str, Any]:
        """Extract one bounded evidence batch with structured validation and provenance."""
        client = cls.get_client()
        model = os.getenv("OPENAI_MODEL") or settings.openai_model
        prompt = cls._build_prompt(chunks, source_metadata)
        logger.info("Requesting LLM extraction: model=%s, chunks=%s", model, len(chunks))

        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a precise industrial data extractor. Return JSON."},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
            )
            if not response.choices:
                logger.error("LLM returned no choices. Response: %s", response)
                raise LLMExtractionError("LLM returned no choices in response.")

            raw_content = response.choices[0].message.content
            if not raw_content or not raw_content.strip():
                logger.error("LLM returned an empty content string.")
                raise LLMExtractionError("LLM returned an empty response.")

            logger.info("LLM response received (length=%s)", len(raw_content))
            payload = json.loads(raw_content)
            if "products" in payload and isinstance(payload["products"], list):
                products = [ProductExtractionResponse.model_validate(product) for product in payload["products"]]
                validated_products = cls._apply_provenance_to_multi(products, chunks)
                logger.info("Extraction successful: products_count=%s", len(validated_products))
                return {"products": [product.model_dump() for product in validated_products]}

            validated = ProductExtractionResponse.model_validate(payload)
            validated = cls._apply_authoritative_provenance(validated, chunks)
            logger.info("Extraction successful: single product='%s'", validated.product_name)
            return {"products": [validated.model_dump()]}
        except json.JSONDecodeError as exc:
            logger.error("LLM JSON decode error: %s", exc)
            raise LLMExtractionError("LLM returned malformed JSON.") from exc
        except ValidationError as exc:
            logger.error("LLM validation error: %s", exc)
            raise LLMExtractionError("LLM response failed schema validation.") from exc
        except LLMExtractionError:
            raise
        except Exception as exc:
            message = str(exc)
            if "<html" in message.casefold() or "<!doctype" in message.casefold():
                logger.error("LLM provider returned an HTML/non-JSON response: %s", type(exc).__name__)
                raise LLMExtractionError(
                    "LLM provider returned an HTML/non-JSON response. Check OPENAI_API_BASE and provider authentication."
                ) from exc
            logger.error("LLM API error: %s: %s", type(exc).__name__, message)
            raise LLMExtractionError("Extraction failed while contacting the configured LLM provider.") from exc

    @classmethod
    def extract_from_chunks(
        cls,
        chunks: List[Mapping[str, Any]],
        source_metadata: Mapping[str, Any],
        progress_callback: Optional[Callable[[int, int, int, int], None]] = None,
        cancellation_check: Optional[Callable[[], bool]] = None,
    ) -> Dict[str, Any]:
        """Extract all supplied evidence in bounded batches without dropping CSV rows."""
        if not chunks:
            raise LLMExtractionError("No evidence chunks supplied.")

        max_chunks = max(1, int(settings.llm_batch_size))
        batches = [chunks[index:index + max_chunks] for index in range(0, len(chunks), max_chunks)]
        if len(batches) > 1:
            logger.info(
                "Processing %s evidence chunks in %s LLM batches (batch_size=%s).",
                len(chunks),
                len(batches),
                max_chunks,
            )

        extracted_products: List[Dict[str, Any]] = []
        processed_evidence_count = 0
        for batch_index, batch in enumerate(batches, start=1):
            if cancellation_check and cancellation_check():
                raise LLMExtractionError("Extraction cancelled by request.")
            logger.info("Starting LLM extraction batch %s/%s: chunks=%s", batch_index, len(batches), len(batch))
            result = cls._extract_single_batch(batch, source_metadata)
            extracted_products.extend(result.get("products", []))
            processed_evidence_count += len(batch)
            if progress_callback:
                progress_callback(batch_index, len(batches), processed_evidence_count, len(extracted_products))

        logger.info("Extraction complete: total_products_count=%s", len(extracted_products))
        return {"products": extracted_products}


def canonicalize_comparison_value(value: Optional[str], unit: Optional[str] = None) -> str:
    """Return a comparison-only canonical value without modifying persisted source values.

    This module-level helper is intentionally shared by investigation, conflict, and
    controlled-discovery workflows so formatting variants such as ``400V`` and
    ``400 volts`` compare consistently while provenance retains the original text.
    """
    return LLMExtractionService.normalize_value_for_comparison(value, unit)
