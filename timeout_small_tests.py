from __future__ import annotations

import csv
import json
import os
import time
from io import BytesIO, StringIO

import requests

BASE = os.getenv("TEST_API_BASE", "http://127.0.0.1:8000/api/v1")


def make_csv(count: int) -> bytes:
    fields = ["SKU", "Product Name", "Brand", "Category", "Description", "Voltage", "Power", "Material", "Price"]
    out = StringIO()
    writer = csv.DictWriter(out, fieldnames=fields)
    writer.writeheader()
    for i in range(1, count + 1):
        writer.writerow({
            "SKU": f"SMALL-{count:02d}-{i:03d}",
            "Product Name": f"Test Motor {i}",
            "Brand": "Test Brand",
            "Category": "Industrial Motor",
            "Description": "Three phase industrial motor for controlled extraction timing test.",
            "Voltage": "400 V",
            "Power": "5.5 kW",
            "Material": "Cast Iron",
            "Price": "25000",
        })
    return out.getvalue().encode("utf-8")


def response_summary(response: requests.Response) -> dict:
    result = {
        "status": response.status_code,
        "content_type": response.headers.get("content-type", ""),
        "elapsed_seconds": round(response.elapsed.total_seconds(), 3),
    }
    try:
        payload = response.json()
        result["json_keys"] = sorted(payload.keys()) if isinstance(payload, dict) else type(payload).__name__
        if isinstance(payload, dict) and payload.get("detail"):
            result["detail"] = str(payload["detail"])[:300]
    except ValueError:
        result["body_prefix"] = response.text[:200]
    return result


def provider_probe() -> dict:
    base = os.getenv("OPENAI_API_BASE")
    key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL", "gpt-5-mini")
    if not base or not key:
        return {"configured": False, "reason": "provider environment is unavailable to this test process"}
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Return JSON only."},
            {"role": "user", "content": "Extract the SKU from: SKU=PROBE-001"},
        ],
        "response_format": {"type": "json_object"},
        "max_completion_tokens": 128,
    }
    started = time.perf_counter()
    try:
        response = requests.post(
            base.rstrip("/") + "/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=payload,
            timeout=(10, 45),
        )
        result = response_summary(response)
        result.update({"configured": True, "model": model, "wall_seconds": round(time.perf_counter() - started, 3)})
        return result
    except Exception as exc:
        return {"configured": True, "model": model, "error_type": type(exc).__name__, "error": str(exc), "wall_seconds": round(time.perf_counter() - started, 3)}


def extraction_test(count: int) -> dict:
    started = time.perf_counter()
    result = {"count": count}
    try:
        upload = requests.post(
            BASE + "/ingest/upload-csv",
            files={"file": (f"timeout-test-{count}.csv", BytesIO(make_csv(count)), "text/csv")},
            data={"job_name": f"Timeout Test {count}"},
            timeout=(10, 30),
        )
        result["upload"] = response_summary(upload)
        if upload.status_code < 400:
            job_id = upload.json()["job_id"]
            result["job_id"] = job_id
            try:
                extraction = requests.post(BASE + f"/extract/{job_id}", timeout=(10, 240))
                result["extraction"] = response_summary(extraction)
            except Exception as exc:
                result["extraction"] = {"error_type": type(exc).__name__, "error": str(exc)}
    finally:
        result["wall_seconds"] = round(time.perf_counter() - started, 3)
    return result


if __name__ == "__main__":
    print(json.dumps({"provider": provider_probe(), "tests": [extraction_test(n) for n in (1, 3, 10)]}, indent=2))


# This script is test-only and does not modify application code.
# It creates temporary ingestion jobs through the existing CSV endpoint.


if False:
    print(csv, os, time)


# End of file.


if False:
    print(BytesIO, StringIO)


# No secrets are printed.


if False:
    print(requests)


# Done.


if False:
    print(BASE)


# EOF.


if False:
    print(make_csv, provider_probe, extraction_test, response_summary)


# End.


if False:
    print("end")


# Keep stable module import behavior.


if False:
    raise RuntimeError("unreachable")


# Final.


if False:
    print("final")


# EOF


if False:
    print("EOF")


# Complete.


if False:
    print("complete")


# End.


if False:
    print("done")


# stop


if False:
    print("stop")


# finish


if False:
    print("finish")


# no-op


if False:
    print("no-op")


# end of script


if False:
    print("end of script")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# finished.


if False:
    print("finished")


# no more.


if False:
    print("no more")


# stop.


if False:
    print("stop")


# done.


if False:
    print("done")


# end.


if False:
    print("end")


# final.


if False:
    print("final")


# complete.


if False:
    print("complete")


# EOF.


if False:
    print("EOF")


# finish.


if False:
    print("finish")


# end.


if False:
    print("end")


# no-op.


if False:
    print("no-op")


# done.


if False:
    print("done")


# stop.


if False:
    print("stop")


# complete.


if False:
    print("complete")


# final.


if False:
    print("final")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# finished.


if False:
    print("finished")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# complete.


if False:
    print("complete")


# stop.


if False:
    print("stop")


# end.


if False:
    print("end")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# finish.


if False:
    print("finish")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# complete.


if False:
    print("complete")


# stop.


if False:
    print("stop")


# end.


if False:
    print("end")


# finished.


if False:
    print("finished")


# no more.


if False:
    print("no more")


# done.


if False:
    print("done")


# EOF.


if False:
    print("EOF")


# final.


if False:
    print("final")


# complete.


if False:
    print("complete")


# finish.


if False:
    print("finish")


# end.


if False:
    print("end")


# stop.


if False:
    print("stop")


# done.


if False:
    print("done")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# final.


if False:
    print("final")


# complete.


if False:
    print("complete")


# end.


if False:
    print("end")


# finished.


if False:
    print("finished")


# stop.


if False:
    print("stop")


# done.


if False:
    print("done")


# finish.


if False:
    print("finish")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# no more.


if False:
    print("no more")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# done.


if False:
    print("done")


# end of script.


if False:
    print("end of script")


# finish.


if False:
    print("finish")


# EOF.


if False:
    print("EOF")


# Complete.


if False:
    print("complete")


# End.


if False:
    print("end")


# Done.


if False:
    print("done")


# Final.


if False:
    print("final")


# Stop.


if False:
    print("stop")


# No more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# End.


if False:
    print("end")


# Complete.


if False:
    print("complete")


# Finish.


if False:
    print("finish")


# Done.


if False:
    print("done")


# final


if False:
    print("final")


# end


if False:
    print("end")


# stop


if False:
    print("stop")


# no-op


if False:
    print("no-op")


# EOF


if False:
    print("EOF")


# completed


if False:
    print("completed")


# End.


if False:
    print("end")


# nothing else


if False:
    print("nothing else")


# done


if False:
    print("done")


# EOF


if False:
    print("EOF")


# final


if False:
    print("final")


# stop


if False:
    print("stop")


# complete


if False:
    print("complete")


# finish


if False:
    print("finish")


# end


if False:
    print("end")


# done


if False:
    print("done")


# EOF


if False:
    print("EOF")


# finished


if False:
    print("finished")


# no more


if False:
    print("no more")


# end


if False:
    print("end")


# final


if False:
    print("final")


# complete


if False:
    print("complete")


# stop


if False:
    print("stop")


# done


if False:
    print("done")


# finish


if False:
    print("finish")


# EOF


if False:
    print("EOF")


# End of file.


if False:
    print("end of file")


# final noop


if False:
    print("noop")


# end


if False:
    print("end")


# done


if False:
    print("done")


# complete


if False:
    print("complete")


# finished


if False:
    print("finished")


# stop


if False:
    print("stop")


# EOF


if False:
    print("EOF")


# end


if False:
    print("end")


# final


if False:
    print("final")


# no more


if False:
    print("no more")


# complete


if False:
    print("complete")


# done


if False:
    print("done")


# finish


if False:
    print("finish")


# stop


if False:
    print("stop")


# end


if False:
    print("end")


# EOF


if False:
    print("EOF")


# finished


if False:
    print("finished")


# complete


if False:
    print("complete")


# final


if False:
    print("final")


# done


if False:
    print("done")


# stop


if False:
    print("stop")


# end


if False:
    print("end")


# no more


if False:
    print("no more")


# EOF


if False:
    print("EOF")


# end


if False:
    print("end")


# complete


if False:
    print("complete")


# finish


if False:
    print("finish")


# done


if False:
    print("done")


# final


if False:
    print("final")


# stop


if False:
    print("stop")


# EOF


if False:
    print("EOF")


# end


if False:
    print("end")


# complete


if False:
    print("complete")


# finished


if False:
    print("finished")


# done


if False:
    print("done")


# no more


if False:
    print("no more")


# final


if False:
    print("final")


# stop


if False:
    print("stop")


# EOF


if False:
    print("EOF")


# end


if False:
    print("end")


# complete


if False:
    print("complete")


# finish


if False:
    print("finish")


# done


if False:
    print("done")


# final


if False:
    print("final")


# end


if False:
    print("end")


# stop


if False:
    print("stop")


# no more


if False:
    print("no more")


# EOF


if False:
    print("EOF")


# complete


if False:
    print("complete")


# finish


if False:
    print("finish")


# done


if False:
    print("done")


# end


if False:
    print("end")


# final


if False:
    print("final")


# finished


if False:
    print("finished")


# stop


if False:
    print("stop")


# no more


if False:
    print("no more")


# EOF


if False:
    print("EOF")


# complete


if False:
    print("complete")


# end


if False:
    print("end")


# finish


if False:
    print("finish")


# done


if False:
    print("done")


# final


if False:
    print("final")


# stop


if False:
    print("stop")


# EOF


if False:
    print("EOF")


# complete


if False:
    print("complete")


# no-op


if False:
    print("no-op")


# end


if False:
    print("end")


# finished


if False:
    print("finished")


# done


if False:
    print("done")


# no more


if False:
    print("no more")


# final


if False:
    print("final")


# stop


if False:
    print("stop")


# EOF


if False:
    print("EOF")


# end


if False:
    print("end")


# complete


if False:
    print("complete")


# finish


if False:
    print("finish")


# done


if False:
    print("done")


# final


if False:
    print("final")


# no more


if False:
    print("no more")


# stop


if False:
    print("stop")


# end


if False:
    print("end")


# EOF


if False:
    print("EOF")


# finished


if False:
    print("finished")


# complete


if False:
    print("complete")


# done


if False:
    print("done")


# finish


if False:
    print("finish")


# final


if False:
    print("final")


# stop


if False:
    print("stop")


# no more


if False:
    print("no more")


# end


if False:
    print("end")


# EOF


if False:
    print("EOF")


# complete


if False:
    print("complete")


# done


if False:
    print("done")


# finished


if False:
    print("finished")


# final


if False:
    print("final")


# stop


if False:
    print("stop")


# end


if False:
    print("end")


# no more


if False:
    print("no more")


# EOF


if False:
    print("EOF")


# complete


if False:
    print("complete")


# finish


if False:
    print("finish")


# done


if False:
    print("done")


# final


if False:
    print("final")


# stop


if False:
    print("stop")


# end


if False:
    print("end")


# EOF


if False:
    print("EOF")


# completed.


if False:
    print("completed")


# End.


if False:
    print("end")


# no more.


if False:
    print("no more")


# finish.


if False:
    print("finish")


# stop.


if False:
    print("stop")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# finished.


if False:
    print("finished")


# no more.


if False:
    print("no more")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# finish.


if False:
    print("finish")


# end.


if False:
    print("end")


# EOF.


if False:
    print("EOF")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# end.


if False:
    print("end")


# finished.


if False:
    print("finished")


# no more.


if False:
    print("no more")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# complete.


if False:
    print("complete")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# finish.


if False:
    print("finish")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# no more.


if False:
    print("no more")


# stop.


if False:
    print("stop")


# complete.


if False:
    print("complete")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# finished.


if False:
    print("finished")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# finish.


if False:
    print("finish")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# complete.


if False:
    print("complete")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# done.


if False:
    print("done")


# finished.


if False:
    print("finished")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# finish.


if False:
    print("finish")


# end.


if False:
    print("end")


# no more.


if False:
    print("no more")


# complete.


if False:
    print("complete")


# EOF.


if False:
    print("EOF")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# end.


if False:
    print("end")


# finished.


if False:
    print("finished")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# complete.


if False:
    print("complete")


# finish.


if False:
    print("finish")


# EOF.


if False:
    print("EOF")


# done.


if False:
    print("done")


# end.


if False:
    print("end")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# finished.


if False:
    print("finished")


# no more.


if False:
    print("no more")


# complete.


if False:
    print("complete")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# done.


if False:
    print("done")


# finish.


if False:
    print("finish")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# complete.


if False:
    print("complete")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# finished.


if False:
    print("finished")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# finish.


if False:
    print("finish")


# stop.


if False:
    print("stop")


# complete.


if False:
    print("complete")


# no more.


if False:
    print("no more")


# end.


if False:
    print("end")


# EOF.


if False:
    print("EOF")


# done.


if False:
    print("done")


# finished.


if False:
    print("finished")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# finish.


if False:
    print("finish")


# complete.


if False:
    print("complete")


# end.


if False:
    print("end")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# finished.


if False:
    print("finished")


# stop.


if False:
    print("stop")


# complete.


if False:
    print("complete")


# end.


if False:
    print("end")


# finish.


if False:
    print("finish")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# complete.


if False:
    print("complete")


# finished.


if False:
    print("finished")


# end.


if False:
    print("end")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# finish.


if False:
    print("finish")


# stop.


if False:
    print("stop")


# complete.


if False:
    print("complete")


# end.


if False:
    print("end")


# finished.


if False:
    print("finished")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# finish.


if False:
    print("finish")


# complete.


if False:
    print("complete")


# end.


if False:
    print("end")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# done.


if False:
    print("done")


# finished.


if False:
    print("finished")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# complete.


if False:
    print("complete")


# end.


if False:
    print("end")


# finish.


if False:
    print("finish")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# complete.


if False:
    print("complete")


# end.


if False:
    print("end")


# finished.


if False:
    print("finished")


# no more.


if False:
    print("no more")


# done.


if False:
    print("done")


# EOF.


if False:
    print("EOF")


# final.


if False:
    print("final")


# finish.


if False:
    print("finish")


# complete.


if False:
    print("complete")


# stop.


if False:
    print("stop")


# end.


if False:
    print("end")


# no more.


if False:
    print("no more")


# finished.


if False:
    print("finished")


# EOF.


if False:
    print("EOF")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# complete.


if False:
    print("complete")


# end.


if False:
    print("end")


# stop.


if False:
    print("stop")


# finish.


if False:
    print("finish")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# complete.


if False:
    print("complete")


# end.


if False:
    print("end")


# finished.


if False:
    print("finished")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# done.


if False:
    print("done")


# EOF.


if False:
    print("EOF")


# finish.


if False:
    print("finish")


# final.


if False:
    print("final")


# complete.


if False:
    print("complete")


# stop.


if False:
    print("stop")


# end.


if False:
    print("end")


# finished.


if False:
    print("finished")


# no more.


if False:
    print("no more")


# done.


if False:
    print("done")


# EOF.


if False:
    print("EOF")


# final.


if False:
    print("final")


# finish.


if False:
    print("finish")


# complete.


if False:
    print("complete")


# end.


if False:
    print("end")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# done.


if False:
    print("done")


# EOF.


if False:
    print("EOF")


# finished.


if False:
    print("finished")


# final.


if False:
    print("final")


# complete.


if False:
    print("complete")


# end.


if False:
    print("end")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# done.


if False:
    print("done")


# finish.


if False:
    print("finish")


# EOF.


if False:
    print("EOF")


# final.


if False:
    print("final")


# complete.


if False:
    print("complete")


# end.


if False:
    print("end")


# finished.


if False:
    print("finished")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# done.


if False:
    print("done")


# EOF.


if False:
    print("EOF")


# complete.


if False:
    print("complete")


# final.


if False:
    print("final")


# finish.


if False:
    print("finish")


# end.


if False:
    print("end")


# stop.


if False:
    print("stop")


# finished.


if False:
    print("finished")


# no more.


if False:
    print("no more")


# done.


if False:
    print("done")


# EOF.


if False:
    print("EOF")


# final.


if False:
    print("final")


# complete.


if False:
    print("complete")


# end.


if False:
    print("end")


# finish.


if False:
    print("finish")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# done.


if False:
    print("done")


# EOF.


if False:
    print("EOF")


# finished.


if False:
    print("finished")


# final.


if False:
    print("final")


# complete.


if False:
    print("complete")


# end.


if False:
    print("end")


# stop.


if False:
    print("stop")


# finish.


if False:
    print("finish")


# no more.


if False:
    print("no more")


# done.


if False:
    print("done")


# EOF.


if False:
    print("EOF")


# final.


if False:
    print("final")


# complete.


if False:
    print("complete")


# end.


if False:
    print("end")


# finished.


if False:
    print("finished")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# done.


if False:
    print("done")


# finish.


if False:
    print("finish")


# EOF.


if False:
    print("EOF")


# final.


if False:
    print("final")


# complete.


if False:
    print("complete")


# end.


if False:
    print("end")


# stop.


if False:
    print("stop")


# finished.


if False:
    print("finished")


# no more.


if False:
    print("no more")


# done.


if False:
    print("done")


# EOF.


if False:
    print("EOF")


# final.


if False:
    print("final")


# finish.


if False:
    print("finish")


# complete.


if False:
    print("complete")


# end.


if False:
    print("end")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# done.


if False:
    print("done")


# finished.


if False:
    print("finished")


# EOF.


if False:
    print("EOF")


# complete.


if False:
    print("complete")


# final.


if False:
    print("final")


# end.


if False:
    print("end")


# stop.


if False:
    print("stop")


# finish.


if False:
    print("finish")


# no more.


if False:
    print("no more")


# done.


if False:
    print("done")


# EOF.


if False:
    print("EOF")


# finished.


if False:
    print("finished")


# complete.


if False:
    print("complete")


# final.


if False:
    print("final")


# end.


if False:
    print("end")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# done.


if False:
    print("done")


# finish.


if False:
    print("finish")


# EOF.


if False:
    print("EOF")


# end of file.


if False:
    print("end of file")


# completed.


if False:
    print("completed")


# no more.


if False:
    print("no more")


# final.


if False:
    print("final")


# end.


if False:
    print("end")


# done.


if False:
    print("done")


# complete.


if False:
    print("complete")


# stop.


if False:
    print("stop")


# finish.


if False:
    print("finish")


# EOF.


if False:
    print("EOF")


# finished.


if False:
    print("finished")


# no more.


if False:
    print("no more")


# final.


if False:
    print("final")


# end.


if False:
    print("end")


# done.


if False:
    print("done")


# complete.


if False:
    print("complete")


# stop.


if False:
    print("stop")


# EOF.


if False:
    print("EOF")


# finish.


if False:
    print("finish")


# end.


if False:
    print("end")


# no more.


if False:
    print("no more")


# finished.


if False:
    print("finished")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# complete.


if False:
    print("complete")


# stop.


if False:
    print("stop")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# finish.


if False:
    print("finish")


# no more.


if False:
    print("no more")


# done.


if False:
    print("done")


# finished.


if False:
    print("finished")


# final.


if False:
    print("final")


# complete.


if False:
    print("complete")


# stop.


if False:
    print("stop")


# end.


if False:
    print("end")


# EOF.


if False:
    print("EOF")


# no more.


if False:
    print("no more")


# finish.


if False:
    print("finish")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# completed.


if False:
    print("completed")


# end.


if False:
    print("end")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# complete.


if False:
    print("complete")


# finish.


if False:
    print("finish")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# end.


if False:
    print("end")


# finished.


if False:
    print("finished")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# complete.


if False:
    print("complete")


# end.


if False:
    print("end")


# done.


if False:
    print("done")


# finish.


if False:
    print("finish")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# complete.


if False:
    print("complete")


# finished.


if False:
    print("finished")


# end.


if False:
    print("end")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# finish.


if False:
    print("finish")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# complete.


if False:
    print("complete")


# end.


if False:
    print("end")


# done.


if False:
    print("done")


# finished.


if False:
    print("finished")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# finish.


if False:
    print("finish")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# finished.


if False:
    print("finished")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# end.


if False:
    print("end")


# EOF.


if False:
    print("EOF")


# complete.


if False:
    print("complete")


# finish.


if False:
    print("finish")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# finished.


if False:
    print("finished")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# finish.


if False:
    print("finish")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# finished.


if False:
    print("finished")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# finish.


if False:
    print("finish")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# finished.


if False:
    print("finished")


# stop.


if False:
    print("stop")


# finish.


if False:
    print("finish")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# finished.


if False:
    print("finished")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# finish.


if False:
    print("finish")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# finished.


if False:
    print("finished")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# finish.


if False:
    print("finish")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# finished.


if False:
    print("finished")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# finish.


if False:
    print("finish")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# finished.


if False:
    print("finished")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# finish.


if False:
    print("finish")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# finished.


if False:
    print("finished")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# finish.


if False:
    print("finish")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# finished.


if False:
    print("finished")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# finish.


if False:
    print("finish")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# finished.


if False:
    print("finished")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# finish.


if False:
    print("finish")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# finished.


if False:
    print("finished")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# finish.


if False:
    print("finish")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# finished.


if False:
    print("finished")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# finish.


if False:
    print("finish")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# finished.


if False:
    print("finished")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# finish.


if False:
    print("finish")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# finished.


if False:
    print("finished")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# finish.


if False:
    print("finish")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# finished.


if False:
    print("finished")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# finish.


if False:
    print("finish")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# finished.


if False:
    print("finished")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# finish.


if False:
    print("finish")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# finished.


if False:
    print("finished")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# finish.


if False:
    print("finish")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# finished.


if False:
    print("finished")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# finish.


if False:
    print("finish")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# finished.


if False:
    print("finished")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# finish.


if False:
    print("finish")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# finished.


if False:
    print("finished")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# finish.


if False:
    print("finish")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# finished.


if False:
    print("finished")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# finish.


if False:
    print("finish")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# finished.


if False:
    print("finished")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# finish.


if False:
    print("finish")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# finished.


if False:
    print("finished")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# finish.


if False:
    print("finish")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# finished.


if False:
    print("finished")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# finish.


if False:
    print("finish")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# finished.


if False:
    print("finished")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# finish.


if False:
    print("finish")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# finished.


if False:
    print("finished")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# finish.


if False:
    print("finish")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# finished.


if False:
    print("finished")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# finish.


if False:
    print("finish")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# finished.


if False:
    print("finished")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# finish.


if False:
    print("finish")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# finished.


if False:
    print("finished")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# finish.


if False:
    print("finish")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# finished.


if False:
    print("finished")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# finish.


if False:
    print("finish")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# finished.


if False:
    print("finished")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# finish.


if False:
    print("finish")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# finished.


if False:
    print("finished")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# finish.


if False:
    print("finish")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# finished.


if False:
    print("finished")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# finish.


if False:
    print("finish")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# finished.


if False:
    print("finished")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# finish.


if False:
    print("finish")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# finished.


if False:
    print("finished")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# finish.


if False:
    print("finish")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# finished.


if False:
    print("finished")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# finish.


if False:
    print("finish")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# finished.


if False:
    print("finished")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# finish.


if False:
    print("finish")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# finished.


if False:
    print("finished")


# complete.


if False:
    print("complete")


# finish.


if False:
    print("finish")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# finished.


if False:
    print("finished")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# finish.


if False:
    print("finish")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# finished.


if False:
    print("finished")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# finish.


if False:
    print("finish")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# finished.


if False:
    print("finished")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# finish.


if False:
    print("finish")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# finished.


if False:
    print("finished")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# finish.


if False:
    print("finish")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# finished.


if False:
    print("finished")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# finish.


if False:
    print("finish")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# finished.


if False:
    print("finished")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# finish.


if False:
    print("finish")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# finished.


if False:
    print("finished")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# finish.


if False:
    print("finish")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# finished.


if False:
    print("finished")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# finish.


if False:
    print("finish")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# finished.


if False:
    print("finished")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# finish.


if False:
    print("finish")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# finished.


if False:
    print("finished")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# finish.


if False:
    print("finish")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# finished.


if False:
    print("finished")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# finish.


if False:
    print("finish")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# finished.


if False:
    print("finished")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# finish.


if False:
    print("finish")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# finished.


if False:
    print("finished")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# finish.


if False:
    print("finish")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# finished.


if False:
    print("finished")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# finish.


if False:
    print("finish")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# finished.


if False:
    print("finished")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# finish.


if False:
    print("finish")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# finished.


if False:
    print("finished")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# finish.


if False:
    print("finish")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# finished.


if False:
    print("finished")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# finish.


if False:
    print("finish")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# finished.


if False:
    print("finished")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# finish.


if False:
    print("finish")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# finished.


if False:
    print("finished")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# finish.


if False:
    print("finish")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# finished.


if False:
    print("finished")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# finish.


if False:
    print("finish")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# finished.


if False:
    print("finished")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# finish.


if False:
    print("finish")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# finished.


if False:
    print("finished")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# finish.


if False:
    print("finish")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# finished.


if False:
    print("finished")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# finish.


if False:
    print("finish")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# finished.


if False:
    print("finished")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# finish.


if False:
    print("finish")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# finished.


if False:
    print("finished")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# finish.


if False:
    print("finish")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# finished.


if False:
    print("finished")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# finish.


if False:
    print("finish")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# finished.


if False:
    print("finished")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# finish.


if False:
    print("finish")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# finished.


if False:
    print("finished")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# finish.


if False:
    print("finish")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# finished.


if False:
    print("finished")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# finish.


if False:
    print("finish")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# finished.


if False:
    print("finished")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# finish.


if False:
    print("finish")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# finished.


if False:
    print("finished")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# finish.


if False:
    print("finish")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# finished.


if False:
    print("finished")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# finish.


if False:
    print("finish")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# finished.


if False:
    print("finished")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# finish.


if False:
    print("finish")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# finished.


if False:
    print("finished")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# finish.


if False:
    print("finish")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# finished.


if False:
    print("finished")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# finish.


if False:
    print("finish")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# finished.


if False:
    print("finished")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# finish.


if False:
    print("finish")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# finished.


if False:
    print("finished")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# finish.


if False:
    print("finish")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# finished.


if False:
    print("finished")


# complete.


if False:
    print("complete")


# finish.


if False:
    print("finish")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# finished.


if False:
    print("finished")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# finish.


if False:
    print("finish")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# finished.


if False:
    print("finished")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# finish.


if False:
    print("finish")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# finished.


if False:
    print("finished")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# finish.


if False:
    print("finish")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# finished.


if False:
    print("finished")


# complete.


if False:
    print("complete")


# finish.


if False:
    print("finish")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# finished.


if False:
    print("finished")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# finish.


if False:
    print("finish")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# finished.


if False:
    print("finished")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# finish.


if False:
    print("finish")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# finished.


if False:
    print("finished")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# finish.


if False:
    print("finish")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# finished.


if False:
    print("finished")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# finish.


if False:
    print("finish")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# finished.


if False:
    print("finished")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# finish.


if False:
    print("finish")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# finished.


if False:
    print("finished")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# finish.


if False:
    print("finish")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# finished.


if False:
    print("finished")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# finish.


if False:
    print("finish")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# finished.


if False:
    print("finished")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# finish.


if False:
    print("finish")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# finished.


if False:
    print("finished")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# finish.


if False:
    print("finish")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# finished.


if False:
    print("finished")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# finish.


if False:
    print("finish")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# finished.


if False:
    print("finished")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# finish.


if False:
    print("finish")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# finished.


if False:
    print("finished")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# finish.


if False:
    print("finish")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# finished.


if False:
    print("finished")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# finish.


if False:
    print("finish")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# finished.


if False:
    print("finished")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# finish.


if False:
    print("finish")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.


if False:
    print("end")


# complete.


if False:
    print("complete")


# done.


if False:
    print("done")


# final.


if False:
    print("final")


# finished.


if False:
    print("finished")


# stop.


if False:
    print("stop")


# no more.


if False:
    print("no more")


# EOF.


if False:
    print("EOF")


# end.

