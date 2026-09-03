"""Verify a self-hosted Firecrawl against the saved Cloud URL contract and HH520."""

import argparse
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import requests

from run_pipeline import BASE_URL, fetch_source, normalize_dynamic, visible_text


PAYLOAD = {
    "formats": ["markdown", "html", "rawHtml"],
    "onlyMainContent": False,
    "onlyCleanContent": False,
    "blockAds": False,
    "removeBase64Images": True,
    "proxy": "auto",
    "maxAge": 0,
    "timeout": 60000,
}


def load_cloud_contract(date):
    latest = json.loads((Path("data/raw") / date / "latest.json").read_text(encoding="utf-8"))
    snapshot = Path(latest["snapshot_dir"])
    records = []
    excluded = {"manifest.json", "source_validation.json", "url_discovery.json"}
    for path in sorted(snapshot.glob("*.json")):
        if path.name in excluded:
            continue
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("url") == BASE_URL:
            continue
        records.append(record)
    return latest["snapshot_id"], records


def normalized_lines(html):
    return [
        line
        for line in (normalize_dynamic(x) for x in visible_text(html or "").splitlines())
        if len(line) >= 2
    ]


def coverage(reference, candidate):
    lines = normalized_lines(reference)
    candidate_text = normalize_dynamic(visible_text(candidate or ""))
    return (sum(line in candidate_text for line in lines) / len(lines)) if lines else 1.0


def verify_one(record, endpoint, api_key, threshold):
    url = record["url"]
    source = fetch_source(url)
    response = requests.post(
        endpoint,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"url": url, **PAYLOAD},
        timeout=120,
    )
    response.raise_for_status()
    body = response.json()
    if not body.get("success"):
        raise RuntimeError(f"self-hosted Firecrawl returned failure: {body}")

    cloud_data = record.get("response", {}).get("data", {})
    target_data = body.get("data", {})
    contract_fields = [name for name in ("markdown", "html", "rawHtml") if name in cloud_data]
    missing_fields = [name for name in contract_fields if name not in target_data]
    source_coverage = coverage(source.get("html", ""), target_data.get("rawHtml", ""))
    passed = not missing_fields and source_coverage >= threshold
    return {
        "url": url,
        "category": record.get("category"),
        "source_coverage": round(source_coverage, 6),
        "missing_cloud_contract_fields": missing_fields,
        "result": "PASS" if passed else "FAIL",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default="2026-09-02")
    parser.add_argument("--expected-pages", type=int, default=69)
    parser.add_argument("--threshold", type=float, default=0.98)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--output", default="selfhost-verification.json")
    args = parser.parse_args()

    endpoint = os.environ.get("FIRECRAWL_ENDPOINT")
    api_key = os.environ.get("FIRECRAWL_API_KEY")
    if not endpoint or not api_key:
        raise SystemExit("FIRECRAWL_ENDPOINT and FIRECRAWL_API_KEY are required")

    snapshot_id, records = load_cloud_contract(args.date)
    if len(records) != args.expected_pages:
        raise SystemExit(f"Cloud contract contains {len(records)} pages, expected {args.expected_pages}")

    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(verify_one, record, endpoint, api_key, args.threshold): record
            for record in records
        }
        for future in as_completed(futures):
            record = futures[future]
            try:
                result = future.result()
            except Exception as exc:
                result = {
                    "url": record["url"],
                    "category": record.get("category"),
                    "result": "FAIL",
                    "error": str(exc),
                }
            results.append(result)
            print(f"{result['result']}: {result['url']}")

    results.sort(key=lambda item: item["url"])
    passed = sum(item["result"] == "PASS" for item in results)
    report = {
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "cloud_contract_date": args.date,
        "cloud_snapshot_id": snapshot_id,
        "endpoint": endpoint,
        "expected_pages": args.expected_pages,
        "tested_pages": len(results),
        "passed_pages": passed,
        "failed_pages": len(results) - passed,
        "coverage_threshold": args.threshold,
        "results": results,
    }
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "results"}, ensure_ascii=False, indent=2))
    if passed != args.expected_pages:
        raise SystemExit(f"Self-host verification failed: {passed}/{args.expected_pages}")


if __name__ == "__main__":
    main()
