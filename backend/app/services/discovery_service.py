"""Bounded Phase 7 discovery service.

The service never turns an external page into a product truth source automatically.  It stores
candidate URLs, validates them, records why a source was accepted or rejected, and keeps every
external assertion as separate evidence for human review.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import re
import socket
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from typing import Any, Iterable
from urllib.parse import urljoin, urlsplit, urlunsplit

import fitz
import requests
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.config import settings
from app.models.discovery import CandidateSource, DiscoveryEvidence, DiscoveryQuery, DiscoveryRun, SourceFetch
from app.models.product import ProductAttribute, ProductRecord
from app.services.llm_extraction_service import canonicalize_comparison_value


@dataclass
class ProviderResult:
    url: str
    title: str | None = None
    metadata: dict[str, Any] | None = None


class DiscoveryProvider:
    name = "none"

    def configured(self) -> bool:
        return False

    def search(self, query: str, limit: int) -> list[ProviderResult]:
        raise RuntimeError("External search provider not configured.")


class TavilyProvider(DiscoveryProvider):
    """Optional provider used only when explicitly configured by deployment settings."""

    name = "tavily"

    def configured(self) -> bool:
        return bool(settings.discovery_provider_api_key)

    def search(self, query: str, limit: int) -> list[ProviderResult]:
        if not self.configured():
            raise RuntimeError("External search provider not configured.")
        response = requests.post(
            "https://api.tavily.com/search",
            json={"api_key": settings.discovery_provider_api_key, "query": query, "max_results": limit, "include_raw_content": False},
            timeout=settings.discovery_fetch_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        return [
            ProviderResult(url=row["url"], title=row.get("title"), metadata={"score": row.get("score"), "content": row.get("content")})
            for row in payload.get("results", [])
            if row.get("url")
        ]


def provider_for_current_settings() -> DiscoveryProvider:
    if settings.discovery_provider.lower().strip() == "tavily":
        return TavilyProvider()
    return DiscoveryProvider()


def _compact(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", (value or "").lower())


def canonical_url(value: str) -> str:
    parts = urlsplit(value.strip())
    scheme = parts.scheme.lower()
    hostname = (parts.hostname or "").lower()
    port = f":{parts.port}" if parts.port else ""
    path = re.sub(r"/+", "/", parts.path or "/")
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    return urlunsplit((scheme, f"{hostname}{port}", path, parts.query, ""))


def _public_http_url(value: str) -> tuple[bool, str]:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False, "URL could not be parsed."
    if parsed.scheme.lower() not in {"http", "https"}:
        return False, "Only http and https URLs are supported."
    if not parsed.hostname or parsed.username or parsed.password:
        return False, "URL hostname is invalid."
    hostname = parsed.hostname.lower()
    if hostname in {"localhost", "localhost.localdomain"} or hostname.endswith(".local"):
        return False, "Local hosts are not allowed."
    try:
        addresses = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except OSError:
        return False, "Hostname could not be resolved."
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
            return False, "Private or reserved network targets are not allowed."
    return True, ""


def _clean_html(content: bytes) -> tuple[str, str | None]:
    soup = BeautifulSoup(content, "html.parser")
    for node in soup(["script", "style", "nav", "header", "footer", "aside", "noscript", "svg"]):
        node.decompose()
    title = soup.title.get_text(" ", strip=True) if soup.title else None
    text = "\n".join(part.strip() for part in soup.get_text("\n").splitlines() if part.strip())
    return text[:500_000], title


def _clean_pdf(content: bytes) -> tuple[str, int]:
    document = fitz.open(stream=content, filetype="pdf")
    try:
        pages = [page.get_text("text") for page in document]
        return "\n".join(pages)[:500_000], len(pages)
    finally:
        document.close()


class DiscoveryService:
    """Run bounded controlled discovery for a single persisted product."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def provider_status() -> dict[str, Any]:
        provider = provider_for_current_settings()
        ready = provider.configured()
        return {
            "provider_name": provider.name,
            "configured": ready,
            "message": "Provider configured for bounded discovery." if ready else "External search provider not configured.",
            "max_queries_per_product": settings.discovery_max_queries_per_product,
            "max_results_per_query": settings.discovery_max_results_per_query,
            "max_sources_per_product": settings.discovery_max_sources_per_product,
            "max_fetches_per_run": settings.discovery_max_fetches_per_run,
        }

    def _get_product(self, product_id: int) -> ProductRecord:
        product = self.db.get(ProductRecord, product_id)
        if not product:
            raise ValueError("Product not found.")
        return product

    def _queries_for_product(self, product: ProductRecord) -> list[tuple[str, str]]:
        identity = " ".join(value for value in [product.manufacturer, product.name, product.sku] if value).strip()
        if not identity:
            return []
        queries: list[tuple[str, str]] = [(identity, "Product identity query assembled from source-backed product fields.")]
        if product.sku:
            queries.append((f"{product.sku} datasheet", "Explicit source-backed SKU/Product ID plus datasheet intent."))
        if product.manufacturer and product.name:
            queries.append((f"{product.manufacturer} {product.name} specifications", "Manufacturer and product-name specification query."))
        return queries[: settings.discovery_max_queries_per_product]

    @staticmethod
    def _authority(source: CandidateSource, product: ProductRecord) -> tuple[str, float]:
        host = (source.domain or "").lower()
        manufacturer = _compact(product.manufacturer)
        if manufacturer and manufacturer in _compact(host):
            return "TIER_1_MANUFACTURER", 1.0
        if source.source_type == "pdf":
            return "TIER_2_DOCUMENT", 0.75
        return "TIER_3_UNKNOWN", 0.40

    def _identity(self, product: ProductRecord, text: str) -> tuple[float, str | None]:
        compact_text = _compact(text)
        if product.sku and _compact(product.sku) not in compact_text:
            return 0.0, "Explicit SKU / Product ID was not found in fetched source content."
        name_tokens = [token for token in re.findall(r"[a-z0-9]{3,}", (product.name or "").lower())]
        name_ratio = sum(token in compact_text for token in name_tokens) / len(name_tokens) if name_tokens else 0.0
        manufacturer_match = bool(product.manufacturer and _compact(product.manufacturer) in compact_text)
        if product.sku:
            score = 0.70 + (0.20 * name_ratio) + (0.10 if manufacturer_match else 0.0)
        else:
            score = (0.65 * name_ratio) + (0.35 if manufacturer_match else 0.0)
        if score < settings.discovery_min_identity_score:
            return score, "Product identity evidence was insufficient for safe approval."
        return min(score, 1.0), None

    @staticmethod
    def _sentences(text: str) -> Iterable[str]:
        for line in re.split(r"[\n\r]+|(?<=[.!?])\s+", text):
            compact = re.sub(r"\s+", " ", line).strip()
            if 12 <= len(compact) <= 1200:
                yield compact

    def _extract_evidence(self, run: DiscoveryRun, source: CandidateSource, fetch: SourceFetch, product: ProductRecord) -> int:
        attributes = self.db.query(ProductAttribute).filter(ProductAttribute.product_id == product.id).all()
        observed: list[tuple[str, str | None]] = [(attr.attribute_name, attr.normalized_value or attr.attribute_value) for attr in attributes]
        observed.extend([("sku", product.sku), ("product name", product.name), ("manufacturer", product.manufacturer)])
        count = 0
        seen: set[tuple[str, str]] = set()
        for sentence in self._sentences(fetch.extracted_text or ""):
            sentence_normalized = canonicalize_comparison_value(sentence)
            for name, value in observed:
                key = (name.lower(), sentence.lower())
                if key in seen or not name:
                    continue
                name_match = _compact(name) in _compact(sentence)
                value_match = bool(value and canonicalize_comparison_value(value) in sentence_normalized)
                if not (name_match or value_match):
                    continue
                raw_value: str | None = None
                match = re.search(rf"{re.escape(name)}\s*[:=\-]\s*([^;|\n]+)", sentence, flags=re.IGNORECASE)
                if match:
                    raw_value = match.group(1).strip()[:500]
                evidence = DiscoveryEvidence(
                    discovery_run_id=run.id,
                    product_id=product.id,
                    candidate_source_id=source.id,
                    source_fetch_id=fetch.id,
                    attribute_name=name,
                    raw_value=raw_value,
                    normalized_value=canonicalize_comparison_value(raw_value) if raw_value else None,
                    quote=sentence,
                    extraction_method="exact_label_or_value_match",
                    evidence_quality=source.quality_score,
                )
                self.db.add(evidence)
                seen.add(key)
                count += 1
                if count >= 80:
                    return count
        return count

    def _fetch(self, source: CandidateSource) -> SourceFetch:
        current_url = source.canonical_url
        for redirect_number in range(settings.discovery_max_redirects + 1):
            safe, reason = _public_http_url(current_url)
            if not safe:
                return SourceFetch(candidate_source_id=source.id, status="rejected", final_url=current_url, error_message=reason)
            try:
                response = requests.get(
                    current_url,
                    timeout=settings.discovery_fetch_timeout_seconds,
                    allow_redirects=False,
                    headers={"User-Agent": "AIProductIntelligenceDiscovery/1.0"},
                    stream=True,
                )
            except requests.RequestException as exc:
                return SourceFetch(candidate_source_id=source.id, status="failed", final_url=current_url, error_message=f"Fetch failed: {exc.__class__.__name__}")
            if response.is_redirect:
                location = response.headers.get("location")
                if not location:
                    return SourceFetch(candidate_source_id=source.id, status="failed", final_url=current_url, http_status=response.status_code, error_message="Redirect response lacked a location.")
                current_url = urljoin(current_url, location)
                continue
            content_type = (response.headers.get("content-type") or "").split(";", 1)[0].lower()
            if response.status_code != 200:
                return SourceFetch(candidate_source_id=source.id, status="failed", final_url=current_url, http_status=response.status_code, content_type=content_type, error_message="HTTP response was not successful.")
            if content_type not in {"text/html", "application/xhtml+xml", "application/pdf"}:
                return SourceFetch(candidate_source_id=source.id, status="rejected", final_url=current_url, http_status=response.status_code, content_type=content_type, error_message="Unsupported content type; only HTML and PDF are accepted.")
            declared_size = response.headers.get("content-length")
            if declared_size and int(declared_size) > settings.discovery_max_response_bytes:
                return SourceFetch(candidate_source_id=source.id, status="rejected", final_url=current_url, http_status=response.status_code, content_type=content_type, error_message="Response exceeds the configured size limit.")
            content = b""
            for chunk in response.iter_content(chunk_size=65536):
                content += chunk
                if len(content) > settings.discovery_max_response_bytes:
                    return SourceFetch(candidate_source_id=source.id, status="rejected", final_url=current_url, http_status=response.status_code, content_type=content_type, byte_count=len(content), error_message="Response exceeds the configured size limit.")
            try:
                if content_type == "application/pdf":
                    text, page_count = _clean_pdf(content)
                    source.source_type = "pdf"
                else:
                    text, title = _clean_html(content)
                    page_count = None
                    if not source.title:
                        source.title = title
                if not text.strip():
                    return SourceFetch(candidate_source_id=source.id, status="rejected", final_url=current_url, http_status=response.status_code, content_type=content_type, byte_count=len(content), error_message="No extractable text was found.")
                return SourceFetch(candidate_source_id=source.id, status="fetched", final_url=current_url, http_status=response.status_code, content_type=content_type, byte_count=len(content), page_count=page_count, extracted_text=text)
            except Exception as exc:  # parser errors are persisted, never hidden
                return SourceFetch(candidate_source_id=source.id, status="failed", final_url=current_url, http_status=response.status_code, content_type=content_type, byte_count=len(content), error_message=f"Content parsing failed: {exc.__class__.__name__}")
        return SourceFetch(candidate_source_id=source.id, status="rejected", final_url=current_url, error_message="Redirect limit exceeded.")

    def _create_candidate(self, run: DiscoveryRun, value: ProviderResult, query: DiscoveryQuery | None, user_provided: bool, seen_urls: set[str]) -> CandidateSource | None:
        try:
            normalized = canonical_url(value.url)
        except (TypeError, ValueError):
            return None
        if normalized in seen_urls:
            return None
        seen_urls.add(normalized)
        parts = urlsplit(normalized)
        source = CandidateSource(
            discovery_run_id=run.id,
            discovery_query_id=query.id if query else None,
            url=value.url,
            canonical_url=normalized,
            url_hash=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
            title=value.title,
            domain=parts.hostname,
            source_type="pdf" if parts.path.lower().endswith(".pdf") else "web",
            user_provided=user_provided,
            metadata_snapshot=value.metadata,
        )
        self.db.add(source)
        self.db.flush()
        return source

    def _finalize_source(self, run: DiscoveryRun, source: CandidateSource, product: ProductRecord) -> None:
        fetch = self._fetch(source)
        self.db.add(fetch)
        self.db.flush()
        if fetch.status != "fetched":
            source.status = "rejected" if fetch.status == "rejected" else "fetch_failed"
            source.rejection_reason = fetch.error_message
            if fetch.status == "rejected":
                run.rejected_count += 1
            else:
                run.fetch_failed_count += 1
            return
        score, rejection = self._identity(product, fetch.extracted_text or "")
        source.identity_score = score
        if rejection:
            source.status = "rejected"
            source.rejection_reason = rejection
            run.rejected_count += 1
            return
        source.authority_tier, authority_score = self._authority(source, product)
        evidence_hint = 0.0
        attr_values = [canonicalize_comparison_value(attribute.normalized_value or attribute.attribute_value) for attribute in self.db.query(ProductAttribute).filter(ProductAttribute.product_id == product.id).all()]
        text_normalized = canonicalize_comparison_value(fetch.extracted_text or "")
        if any(value and value in text_normalized for value in attr_values):
            evidence_hint = 1.0
        source.quality_score = round((score * 0.65) + (authority_score * 0.20) + (evidence_hint * 0.15), 4)
        source.status = "verified"
        run.verified_count += 1
        run.evidence_count += self._extract_evidence(run, source, fetch, product)

    def _cross_source_conflicts(self, run: DiscoveryRun) -> list[dict[str, Any]]:
        rows = self.db.query(DiscoveryEvidence).filter(
            DiscoveryEvidence.discovery_run_id == run.id,
            DiscoveryEvidence.attribute_name.isnot(None),
            DiscoveryEvidence.normalized_value.isnot(None),
        ).all()
        values: dict[str, set[str]] = {}
        source_counts: dict[str, set[int]] = {}
        for row in rows:
            values.setdefault(row.attribute_name or "", set()).add(row.normalized_value or "")
            source_counts.setdefault(row.attribute_name or "", set()).add(row.candidate_source_id)
        conflicts = [
            {"attribute_name": name, "values": sorted(value_set), "source_count": len(source_counts.get(name, set())), "explanation": "Verified discovery sources contain different normalized assertions; no value was selected automatically."}
            for name, value_set in values.items() if len(value_set) > 1
        ]
        run.conflict_count = len(conflicts)
        return conflicts

    def run(self, product_id: int, user_urls: list[str] | None = None) -> DiscoveryRun:
        product = self._get_product(product_id)
        provider = provider_for_current_settings()
        run = DiscoveryRun(
            product_id=product.id,
            status="running",
            provider_name=provider.name,
            provider_status="configured" if provider.configured() else "not_configured",
            max_queries=settings.discovery_max_queries_per_product,
            max_results_per_query=settings.discovery_max_results_per_query,
            max_sources=settings.discovery_max_sources_per_product,
            max_fetches=settings.discovery_max_fetches_per_run,
        )
        self.db.add(run)
        self.db.flush()
        seen_urls: set[str] = set()
        for url in (user_urls or [])[: settings.discovery_max_sources_per_product]:
            self._create_candidate(run, ProviderResult(url=url, metadata={"origin": "user_provided"}), None, True, seen_urls)
        if provider.configured():
            for query_text, reason in self._queries_for_product(product):
                query = DiscoveryQuery(discovery_run_id=run.id, query_text=query_text, reason=reason, provider_name=provider.name, status="running")
                self.db.add(query)
                self.db.flush()
                try:
                    results = provider.search(query_text, settings.discovery_max_results_per_query)
                    for result in results:
                        if len(seen_urls) >= settings.discovery_max_sources_per_product:
                            break
                        self._create_candidate(run, result, query, False, seen_urls)
                    query.status = "completed"
                    query.result_count = len(results)
                except Exception as exc:
                    query.status = "failed"
                    run.error_message = f"Provider search failed: {exc.__class__.__name__}"
                run.query_count += 1
        elif not user_urls:
            run.status = "provider_not_configured"
            run.error_message = "External search provider not configured. Add approved URLs or configure a provider."
        self.db.flush()
        candidates = self.db.query(CandidateSource).filter(CandidateSource.discovery_run_id == run.id).order_by(CandidateSource.id).limit(run.max_fetches).all()
        run.discovered_count = self.db.query(CandidateSource).filter(CandidateSource.discovery_run_id == run.id).count()
        for candidate in candidates:
            self._finalize_source(run, candidate, product)
        verified = self.db.query(CandidateSource).filter(CandidateSource.discovery_run_id == run.id, CandidateSource.status == "verified").order_by(CandidateSource.quality_score.desc()).all()
        for rank, source in enumerate(verified, start=1):
            source.rank = rank
        # Sessions deliberately use autoflush=False, so persist accepted-source evidence
        # before querying it for cross-source disagreements within this run.
        self.db.flush()
        conflicts = self._cross_source_conflicts(run)
        run.summary = {
            "provider": self.provider_status(),
            "message": run.error_message or "Discovery completed with source validation; no external assertion changed the product record.",
            "cross_source_conflicts": conflicts,
            "source_selection_policy": "Sources require a verified product identity and are ranked by identity, authority heuristic, and source-backed attribute evidence.",
        }
        if run.status == "running":
            run.status = "completed"
        run.completed_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(run)
        return run

    def latest(self, product_id: int) -> DiscoveryRun | None:
        return self.db.query(DiscoveryRun).filter(DiscoveryRun.product_id == product_id).order_by(DiscoveryRun.id.desc()).first()

    def detail(self, product_id: int) -> tuple[DiscoveryRun, list[DiscoveryQuery], list[CandidateSource], list[DiscoveryEvidence]]:
        run = self.latest(product_id)
        if not run:
            raise ValueError("No discovery run exists for this product.")
        queries = self.db.query(DiscoveryQuery).filter(DiscoveryQuery.discovery_run_id == run.id).order_by(DiscoveryQuery.id).all()
        sources = self.db.query(CandidateSource).filter(CandidateSource.discovery_run_id == run.id).order_by(CandidateSource.rank.is_(None), CandidateSource.rank, CandidateSource.id).all()
        evidence = self.db.query(DiscoveryEvidence).filter(DiscoveryEvidence.discovery_run_id == run.id, DiscoveryEvidence.product_id == product_id).order_by(DiscoveryEvidence.id).all()
        return run, queries, sources, evidence
