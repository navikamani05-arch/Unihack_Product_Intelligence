from __future__ import annotations

import json
import requests

BASE = "http://127.0.0.1:8000/api/v1"
JOB_IDS = [33, 46]


def request(method: str, path: str, **kwargs):
    response = requests.request(method, BASE + path, timeout=60, **kwargs)
    print(f"{method} {path} -> {response.status_code} {response.headers.get('content-type', '')}")
    if response.status_code >= 400:
        print(response.text[:1200])
    response.raise_for_status()
    return response


def main() -> int:
    created = request("POST", "/investigations", json={"name": "E2E audit temporary investigation", "description": "Deleted after audit"}).json()
    investigation_id = created["id"]
    try:
        attached = []
        for job_id in JOB_IDS:
            attached.append(request("POST", f"/investigations/{investigation_id}/sources/{job_id}").json())
        comparison = request("GET", f"/investigations/{investigation_id}/comparison").json()
        conflicts = request("GET", f"/investigations/{investigation_id}/conflicts").json()
        detail = request("GET", f"/investigations/{investigation_id}").json()
        out = {
            "investigation_id": investigation_id,
            "attached_job_ids": [item["job_id"] for item in attached[0].get("source_jobs", [])] if attached else [],
            "detail_source_jobs": detail.get("source_jobs"),
            "comparison": {
                "source_identities": len(comparison.get("source_identities", [])),
                "matches": comparison.get("matches"),
                "attributes": len(comparison.get("attributes", [])),
            },
            "conflicts": {
                "total_sources": conflicts.get("total_sources"),
                "conflict_count": conflicts.get("conflict_count"),
                "conflict_items": conflicts.get("conflicts"),
                "summary_count": len(conflicts.get("attribute_summaries", [])),
            },
        }
        print("\nE2E_INVESTIGATION_RESULT")
        print(json.dumps(out, indent=2, default=str)[:16000])
    finally:
        delete_response = requests.delete(BASE + f"/investigations/{investigation_id}", timeout=60)
        print(f"DELETE /investigations/{investigation_id} -> {delete_response.status_code}")
        delete_response.raise_for_status()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
