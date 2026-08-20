from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import requests

BASE = "http://127.0.0.1:8000/api/v1"
DATASET = Path("/home/ubuntu/upload/Unihack_SampleDataset-Input.csv")


def check(method: str, url: str, **kwargs):
    response = requests.request(method, url, timeout=30, **kwargs)
    print(f"{method} {url} -> {response.status_code} {response.headers.get('content-type', '')}")
    if response.status_code >= 400:
        print(response.text[:1000])
    response.raise_for_status()
    return response


def main() -> int:
    out: dict[str, object] = {"base": BASE, "dataset": str(DATASET)}
    check("GET", f"{BASE}/health")
    check("GET", f"{BASE}/health/ready")
    dashboard = check("GET", f"{BASE}/dashboard/overview").json()
    out["dashboard"] = {
        "batch_summary": dashboard.get("availability", {}).get("batch_summary"),
        "metrics": dashboard.get("metrics"),
        "availability": dashboard.get("availability"),
    }

    with DATASET.open("rb") as handle:
        upload = check(
            "POST",
            f"{BASE}/catalog/batches/upload",
            files={"file": (DATASET.name, handle, "text/csv")},
            params={"dataset_name": "E2E audit supplied 1000-row input"},
        ).json()
    out["upload"] = upload
    batch_id = upload["batch_id"]

    start = check(
        "POST",
        f"{BASE}/catalog/batches/{batch_id}/start",
        json={"mode": "standard", "use_llm": False},
    ).json()
    out["start"] = start

    deadline = time.time() + 90
    status = start
    while time.time() < deadline:
        time.sleep(1)
        status = check("GET", f"{BASE}/catalog/batches/{batch_id}/status").json()
        if status.get("status") in {"COMPLETED", "FAILED", "CANCELLED"}:
            break
    out["final_status"] = status

    for path, key in [
        (f"/catalog/batches/{batch_id}/results?page=1&page_size=5", "results"),
        (f"/catalog/batches/{batch_id}/failures?page=1&page_size=20", "failures"),
        (f"/catalog/batches/{batch_id}/summary", "summary"),
        (f"/catalog/batches/{batch_id}/review-queue", "review_queue"),
    ]:
        out[key] = check("GET", BASE + path).json()

    reports = {}
    for report_type in ["catalog-summary", "failed-products", "conflict-report", "human-review-report", "evaluation-report"]:
        reports[report_type] = check("GET", f"{BASE}/catalog/batches/{batch_id}/reports/{report_type}").json()
    out["reports"] = reports

    exports = {}
    for fmt in ["json", "csv", "xlsx"]:
        response = check("GET", f"{BASE}/catalog/batches/{batch_id}/export", params={"format": fmt, "filter": "all"})
        exports[fmt] = {
            "bytes": len(response.content),
            "content_type": response.headers.get("content-type"),
            "content_disposition": response.headers.get("content-disposition"),
        }
    out["exports"] = exports

    print("\nE2E_CATALOG_RESULT")
    print(json.dumps({"batch_id": batch_id, **out}, indent=2, default=str)[:20000])
    return 0 if status.get("status") == "COMPLETED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
