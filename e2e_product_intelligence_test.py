from __future__ import annotations

import json
from pathlib import Path

import requests

BASE = "http://127.0.0.1:8000/api/v1"
PRODUCT_ID = 1007
OUT = Path("/tmp/e2e_product_exports")
OUT.mkdir(parents=True, exist_ok=True)


def request(method: str, path: str, **kwargs):
    response = requests.request(method, BASE + path, timeout=60, **kwargs)
    print(f"{method} {path} -> {response.status_code} {response.headers.get('content-type', '')}")
    if response.status_code >= 400:
        print(response.text[:1200])
    response.raise_for_status()
    return response


def main() -> int:
    out: dict[str, object] = {"product_id": PRODUCT_ID}
    out["product_list"] = request("GET", "/enrichment/products?limit=5").json()
    out["analyze_source_only"] = request(
        "POST", f"/analyze/{PRODUCT_ID}", json={"use_llm": False, "mode": "SOURCE_ONLY"}
    ).json()
    out["enrichment"] = request("GET", f"/enrichment/{PRODUCT_ID}").json()
    out["attributes"] = request("GET", f"/enrichment/{PRODUCT_ID}/attributes").json()
    out["evidence"] = request("GET", f"/enrichment/{PRODUCT_ID}/evidence").json()
    out["conflicts"] = request("GET", f"/enrichment/{PRODUCT_ID}/conflicts").json()

    commerce = request("GET", f"/commerce-output/{PRODUCT_ID}").json()
    fields = request("GET", f"/commerce-output/{PRODUCT_ID}/fields").json()
    out["commerce"] = commerce
    out["commerce_fields"] = fields

    product_exports = {}
    for fmt in ["json", "csv"]:
        response = request("GET", f"/enrichment/{PRODUCT_ID}/export", params={"format": fmt})
        path = OUT / f"enrichment_{PRODUCT_ID}.{fmt}"
        path.write_bytes(response.content)
        product_exports[fmt] = {"bytes": len(response.content), "path": str(path), "content_type": response.headers.get("content-type")}

    commerce_exports = {}
    for fmt in ["json", "csv", "xlsx"]:
        response = request("GET", f"/commerce-output/{PRODUCT_ID}/export", params={"format": fmt})
        suffix = fmt
        path = OUT / f"commerce_{PRODUCT_ID}.{suffix}"
        path.write_bytes(response.content)
        commerce_exports[fmt] = {"bytes": len(response.content), "path": str(path), "content_type": response.headers.get("content-type")}

    out["product_exports"] = product_exports
    out["commerce_exports"] = commerce_exports
    out["discovery_provider_status"] = request("GET", "/discovery/provider-status").json()
    detail_response = requests.get(BASE + f"/discovery/product/{PRODUCT_ID}", timeout=60)
    print(f"GET /discovery/product/{PRODUCT_ID} -> {detail_response.status_code} {detail_response.headers.get('content-type', '')}")
    out["discovery_detail_before_run"] = {"status_code": detail_response.status_code, "body": detail_response.json()}
    discovery_response = requests.post(BASE + f"/discovery/product/{PRODUCT_ID}", json={"user_urls": []}, timeout=60)
    print(f"POST /discovery/product/{PRODUCT_ID} -> {discovery_response.status_code} {discovery_response.headers.get('content-type', '')}")
    out["discovery_run_without_provider"] = {"status_code": discovery_response.status_code, "body": discovery_response.json()}
    out["discovery_enabled_without_provider"] = request(
        "POST", f"/analyze/{PRODUCT_ID}", json={"use_llm": False, "mode": "DISCOVERY_ENABLED"}
    ).json()

    compact = {
        "product_id": PRODUCT_ID,
        "analyze_status": out["analyze_source_only"].get("status"),
        "enrichment_keys": sorted(out["enrichment"].keys()),
        "attribute_count": len(out["attributes"]),
        "evidence_count": len(out["evidence"]),
        "conflict_count": len(out["conflicts"]),
        "commerce_keys": sorted(out["commerce"].keys()),
        "commerce_field_count": len(out["commerce_fields"]),
        "product_exports": product_exports,
        "commerce_exports": commerce_exports,
        "discovery_provider_status": out["discovery_provider_status"],
        "discovery_detail_before_run": out["discovery_detail_before_run"],
        "discovery_run_without_provider": out["discovery_run_without_provider"],
        "discovery_enabled_status": out["discovery_enabled_without_provider"].get("status"),
    }
    print("\nE2E_PRODUCT_RESULT")
    print(json.dumps(compact, indent=2, default=str))
    print("\nE2E_PRODUCT_SAMPLE")
    print(json.dumps({"enrichment": out["enrichment"], "attributes": out["attributes"], "evidence": out["evidence"], "conflicts": out["conflicts"]}, indent=2, default=str)[:12000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
