from __future__ import annotations

import concurrent.futures
import json
import statistics
import time
from io import BytesIO

import requests

BASE = "http://127.0.0.1:8000/api/v1"


def call(method: str, path: str, expected=None, **kwargs):
    started = time.perf_counter()
    response = requests.request(method, BASE + path, timeout=60, **kwargs)
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    if expected is not None and response.status_code not in expected:
        raise AssertionError(f"{method} {path}: {response.status_code}, expected {expected}: {response.text[:500]}")
    return {"method": method, "path": path, "status": response.status_code, "elapsed_ms": elapsed_ms, "body": response.json() if "application/json" in response.headers.get("content-type", "") else response.text[:200]}


def main() -> int:
    checks = []
    # Search/filter and pagination boundaries.
    checks.append(call("GET", "/dashboard/products?search=Grizzly&page=1&page_size=10", expected={200}))
    checks.append(call("GET", "/dashboard/products?page=1&page_size=100", expected={200}))
    checks.append(call("GET", "/dashboard/products?page=0", expected={422}))
    checks.append(call("GET", "/dashboard/products?page_size=101", expected={422}))
    checks.append(call("GET", "/dashboard/products?search=%3Cscript%3Ealert(1)%3C/script%3E", expected={200}))

    # Not-found and unsupported-operation behavior.
    checks.append(call("GET", "/dashboard/products/99999999", expected={404}))
    checks.append(call("GET", "/catalog/batches/99999999/status", expected={404}))
    checks.append(call("GET", "/catalog/batches/3/reports/not-a-real-report", expected={400, 404, 422}))
    checks.append(call("GET", "/catalog/batches/3/export?format=not-real", expected={400, 404, 422}))
    checks.append(call("GET", "/evaluation/ground-truth/products/99999999", expected={200, 404, 422}))

    # Upload validation and filename safety: invalid extension should be rejected without processing.
    files = {"file": ("../../audit_payload.txt", BytesIO(b"not a supported catalog file"), "text/plain")}
    checks.append(call("POST", "/catalog/batches/upload", files=files, expected={400, 415, 422}))
    files = {"file": ("catalog.csv", BytesIO(b"not,csv\n\"unterminated"), "text/csv")}
    checks.append(call("POST", "/catalog/batches/upload", files=files, expected={400, 422}))

    # SSRF-safe discovery boundary. The URL should not be fetched as an accepted public source.
    checks.append(call("POST", "/discovery/product/1007", json={"user_urls": ["http://127.0.0.1:8000/api/v1/health"]}, expected={200, 400, 422}))
    checks.append(call("POST", "/discovery/product/1007", json={"user_urls": ["file:///etc/passwd"]}, expected={200, 400, 422}))
    checks.append(call("POST", "/discovery/product/1007", json={"user_urls": ["javascript:alert(1)"]}, expected={200, 400, 422}))

    # Evaluation honesty state.
    checks.append(call("GET", "/evaluation/ground-truth/availability", expected={200}))
    checks.append(call("GET", "/evaluation/summary", expected={200}))

    # Concurrent timing check on representative read-only endpoints.
    def timed(path: str):
        started = time.perf_counter()
        response = requests.get(BASE + path, timeout=60)
        elapsed_ms = (time.perf_counter() - started) * 1000
        return response.status_code, elapsed_ms

    paths = ["/health", "/health/ready", "/dashboard/overview", "/dashboard/products?page=1&page_size=25"] * 5
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        timings = list(pool.map(timed, paths))
    statuses = [status for status, _ in timings]
    latencies = [latency for _, latency in timings]
    performance = {
        "request_count": len(timings),
        "all_http_200": all(status == 200 for status in statuses),
        "status_counts": {str(status): statuses.count(status) for status in sorted(set(statuses))},
        "min_ms": round(min(latencies), 2),
        "median_ms": round(statistics.median(latencies), 2),
        "p95_ms": round(sorted(latencies)[max(0, int(len(latencies) * 0.95) - 1)], 2),
        "max_ms": round(max(latencies), 2),
    }

    compact = []
    for item in checks:
        body = item["body"]
        if isinstance(body, dict):
            body_summary = {key: body[key] for key in ("status", "detail", "total", "total_products", "products_processed", "official_available") if key in body}
        else:
            body_summary = str(body)[:160]
        compact.append({"method": item["method"], "path": item["path"], "status": item["status"], "elapsed_ms": item["elapsed_ms"], "body": body_summary})

    print("E2E_BOUNDARY_RESULT")
    print(json.dumps({"checks": compact, "performance": performance}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
