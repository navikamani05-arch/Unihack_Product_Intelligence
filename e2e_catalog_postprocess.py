from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import openpyxl
import requests

BASE = "http://127.0.0.1:8000/api/v1"
BATCH_ID = 3
OUT = Path("/tmp/e2e_catalog_exports")
OUT.mkdir(parents=True, exist_ok=True)


def get(path: str, **kwargs):
    response = requests.get(BASE + path, timeout=30, **kwargs)
    print(f"GET {path} -> {response.status_code} {response.headers.get('content-type', '')}")
    response.raise_for_status()
    return response


def main() -> int:
    status = get(f"/catalog/batches/{BATCH_ID}/status").json()
    summary = get(f"/catalog/batches/{BATCH_ID}/summary").json()
    results = get(f"/catalog/batches/{BATCH_ID}/results?page=1&page_size=5").json()
    failures = get(f"/catalog/batches/{BATCH_ID}/failures?page=1&page_size=20").json()
    review = get(f"/catalog/batches/{BATCH_ID}/review-queue").json()
    reports = {}
    for report_type in ["catalog-summary", "failed-products", "conflict-report", "human-review-report", "evaluation-report"]:
        reports[report_type] = get(f"/catalog/batches/{BATCH_ID}/reports/{report_type}").json()

    exports = {}
    for fmt in ["json", "csv", "xlsx"]:
        response = get(f"/catalog/batches/{BATCH_ID}/export", params={"format": fmt, "filter": "all"})
        path = OUT / f"catalog_batch_{BATCH_ID}.{fmt}"
        path.write_bytes(response.content)
        item = {"bytes": len(response.content), "path": str(path), "content_type": response.headers.get("content-type")}
        if fmt == "json":
            payload = json.loads(response.content)
            item["top_level_type"] = type(payload).__name__
            if isinstance(payload, dict):
                item["item_count"] = len(payload.get("items", []))
            elif isinstance(payload, list):
                item["item_count"] = len(payload)
            else:
                item["item_count"] = None
        elif fmt == "csv":
            rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
            item["row_count_including_header"] = len(rows)
            item["column_count"] = len(rows[0]) if rows else 0
            item["header"] = rows[0][:20] if rows else []
        else:
            workbook = openpyxl.load_workbook(io.BytesIO(response.content), read_only=True, data_only=True)
            sheet = workbook.active
            rows = list(sheet.iter_rows(values_only=True))
            item["row_count_including_header"] = len(rows)
            item["column_count"] = len(rows[0]) if rows else 0
            item["header"] = list(rows[0][:20]) if rows else []
            workbook.close()
        exports[fmt] = item

    output = {
        "batch_id": BATCH_ID,
        "status": status,
        "summary": summary,
        "results_page": {"total": results.get("total"), "item_count": len(results.get("items", [])), "first_item": results.get("items", [None])[0]},
        "failures": {"total": failures.get("total"), "item_count": len(failures.get("items", []))},
        "review_queue": {"total": review.get("total"), "item_count": len(review.get("items", []))},
        "report_keys": {key: sorted(value.keys()) if isinstance(value, dict) else type(value).__name__ for key, value in reports.items()},
        "exports": exports,
    }
    print(json.dumps(output, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
