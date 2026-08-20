from __future__ import annotations

import json
import requests

BASE = "http://127.0.0.1:8000/api/v1"
PRODUCT_ID = 1007
ATTRIBUTE_ID = 3483


def request(method: str, path: str, **kwargs):
    response = requests.request(method, BASE + path, timeout=60, **kwargs)
    print(f"{method} {path} -> {response.status_code} {response.headers.get('content-type', '')}")
    if response.status_code >= 400:
        print(response.text[:1200])
    response.raise_for_status()
    return response


def main() -> int:
    out = {}
    out["reference_status"] = request("GET", "/reference-data/status").json()
    out["reference_list"] = request("GET", "/reference-data").json()
    out["manufacturer_search"] = request("GET", "/manufacturers/search", params={"q": "Woodstock"}).json()
    out["brand_search"] = request("GET", "/brands/search", params={"q": "Grizzly"}).json()
    out["lov"] = request("GET", "/lov/example-classpath", params={"attribute": "brand"}).json()
    out["uom_normalization"] = request("POST", "/normalize/uom", json={"value": "400 V V", "uom": "V"}).json()
    out["fraction_normalization"] = request("POST", "/normalize/fraction", json={"value": "1/2"}).json()
    out["attribute_resolution"] = request("POST", "/resolve/attribute", json={"classpath": "example-classpath", "attribute": "brand", "candidate_value": "Grizzly"}).json()

    review = request(
        "POST",
        f"/enrichment/{PRODUCT_ID}/review",
        json={"action": "MARK_UNRESOLVED", "attribute_id": ATTRIBUTE_ID, "reason": "E2E audit review decision; no source value changed."},
    ).json()
    out["review_decision"] = review
    out["enrichment_after_review"] = request("GET", f"/enrichment/{PRODUCT_ID}").json()

    compact = {
        "reference_dataset_count": len(out["reference_status"].get("datasets", [])),
        "reference_status": out["reference_status"],
        "manufacturer_match_type": out["manufacturer_search"].get("match_type"),
        "brand_match_type": out["brand_search"].get("match_type"),
        "lov_status": out["lov"].get("status"),
        "uom_normalization": out["uom_normalization"],
        "fraction_normalization": out["fraction_normalization"],
        "attribute_resolution": out["attribute_resolution"],
        "review_decision": out["review_decision"],
        "review_decision_count_after": len(out["enrichment_after_review"].get("review_decisions", [])),
        "raw_attribute_preserved": next((item.get("raw_value") for item in out["enrichment_after_review"].get("attributes", []) if item.get("attribute_id") == ATTRIBUTE_ID), None),
    }
    print("\nE2E_REFERENCE_REVIEW_RESULT")
    print(json.dumps(compact, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
