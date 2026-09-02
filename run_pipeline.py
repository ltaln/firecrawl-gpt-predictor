import argparse
import json
import os
import re
from datetime import datetime, timezone
from difflib import SequenceMatcher
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

import requests
from openai import OpenAI

FIRECRAWL_ENDPOINT = "https://api.firecrawl.dev/v2/scrape"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140 Safari/537.36"


class VisibleTextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.skip = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() in {"script", "style", "noscript", "svg"}:
            self.skip += 1

    def handle_endtag(self, tag):
        if tag.lower() in {"script", "style", "noscript", "svg"} and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            text = re.sub(r"\s+", " ", data).strip()
            if text:
                self.parts.append(text)


def slugify(url: str) -> str:
    p = urlparse(url)
    raw = f"{p.netloc}{p.path}_{p.query}".strip("_")
    raw = re.sub(r"[^A-Za-z0-9._-]+", "_", raw)
    return raw[:180] or "page"


def scrape_url(url: str, api_key: str) -> dict:
    payload = {
        "url": url,
        "formats": ["markdown", "html", "rawHtml"],
        "onlyMainContent": False,
        "onlyCleanContent": False,
        "blockAds": False,
        "removeBase64Images": True,
        "proxy": "auto",
        "maxAge": 0,
        "timeout": 60000,
    }
    r = requests.post(
        FIRECRAWL_ENDPOINT,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=90,
    )
    r.raise_for_status()
    body = r.json()
    if not body.get("success"):
        raise RuntimeError(f"Firecrawl failed for {url}: {body}")
    return body


def fetch_source(url: str) -> dict:
    r = requests.get(url, headers={"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9"}, timeout=60)
    r.raise_for_status()
    if not r.encoding or r.encoding.lower() == "iso-8859-1":
        r.encoding = r.apparent_encoding or "utf-8"
    return {
        "status_code": r.status_code,
        "final_url": r.url,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "html": r.text,
    }


def visible_text(html: str) -> str:
    p = VisibleTextParser()
    p.feed(html or "")
    return "\n".join(p.parts)


def normalize_dynamic(text: str) -> str:
    text = re.sub(r"\d+\s*(秒|分钟|小时|天)后", "<RELATIVE_TIME>", text)
    text = re.sub(r"\d+\s*(秒|分钟|小时|天)前", "<RELATIVE_TIME>", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def line_coverage(source_text: str, firecrawl_text: str) -> tuple[float, list[str]]:
    source_lines = []
    for line in source_text.splitlines():
        n = normalize_dynamic(line)
        if len(n) >= 2:
            source_lines.append(n)
    fc = normalize_dynamic(firecrawl_text)
    if not source_lines:
        return 1.0, []
    missing = [line for line in source_lines if line not in fc]
    return (len(source_lines) - len(missing)) / len(source_lines), missing[:30]


def validate_source(url: str, source: dict, firecrawl: dict) -> dict:
    data = firecrawl.get("data", {})
    source_text = visible_text(source.get("html", ""))
    fc_raw_text = visible_text(data.get("rawHtml", ""))
    source_norm = normalize_dynamic(source_text)
    fc_norm = normalize_dynamic(fc_raw_text)
    coverage, missing = line_coverage(source_text, fc_raw_text)
    similarity = SequenceMatcher(None, source_norm, fc_norm, autojunk=False).ratio() if source_norm or fc_norm else 1.0
    return {
        "url": url,
        "source_status_code": source.get("status_code"),
        "source_final_url": source.get("final_url"),
        "source_html_chars": len(source.get("html", "")),
        "firecrawl_raw_html_chars": len(data.get("rawHtml", "")),
        "source_visible_text_chars": len(source_norm),
        "firecrawl_visible_text_chars": len(fc_norm),
        "normalized_similarity": round(similarity, 6),
        "source_line_coverage": round(coverage, 6),
        "missing_source_lines_sample": missing,
        "result": "PASS" if coverage >= 0.98 else "CHECK",
    }


def load_urls(cli_urls: list[str] | None) -> list[str]:
    if cli_urls:
        return cli_urls
    return [line.strip() for line in Path("urls.txt").read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")]


def build_prompt(target_date: str, scraped_docs: list[dict]) -> str:
    compact = []
    for item in scraped_docs:
        data = item.get("response", {}).get("data", {})
        compact.append({"url": item["url"], "metadata": data.get("metadata", {}), "markdown": data.get("markdown", "")})
    return f"请只依据以下抓取数据分析 {target_date} 的足球比赛，不要补充未抓取信息。\n{json.dumps(compact, ensure_ascii=False)}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--urls", nargs="*")
    parser.add_argument("--scrape-only", action="store_true")
    parser.add_argument("--skip-source-validation", action="store_true")
    args = parser.parse_args()

    firecrawl_key = os.environ.get("FIRECRAWL_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")
    model = os.environ.get("OPENAI_MODEL", "gpt-5.6-sol")
    if not firecrawl_key:
        raise SystemExit("Missing FIRECRAWL_API_KEY")

    urls = load_urls(args.urls)
    run_started = datetime.now(timezone.utc)
    snapshot_id = run_started.strftime("%Y%m%dT%H%M%SZ")
    raw_dir = Path("data/raw") / args.date / "snapshots" / snapshot_id
    source_dir = raw_dir / "source"
    pred_dir = Path("data/predictions")
    raw_dir.mkdir(parents=True, exist_ok=True)
    source_dir.mkdir(parents=True, exist_ok=True)
    pred_dir.mkdir(parents=True, exist_ok=True)

    scraped_docs = []
    validations = []
    for url in urls:
        source = None
        if not args.skip_source_validation:
            print(f"Direct source fetch: {url}")
            try:
                source = fetch_source(url)
                (source_dir / f"{slugify(url)}.html").write_text(source["html"], encoding="utf-8")
            except Exception as exc:
                source = {"error": str(exc), "fetched_at": datetime.now(timezone.utc).isoformat()}

        print(f"Firecrawl scrape: {url}")
        response = scrape_url(url, firecrawl_key)
        record = {"url": url, "fetched_at": datetime.now(timezone.utc).isoformat(), "snapshot_id": snapshot_id, "response": response}
        scraped_docs.append(record)
        (raw_dir / f"{slugify(url)}.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

        if source and "html" in source:
            validations.append(validate_source(url, source, response))
        elif source:
            validations.append({"url": url, "result": "SOURCE_FETCH_FAILED", "error": source.get("error")})

    validation_report = {
        "date": args.date,
        "snapshot_id": snapshot_id,
        "validated_urls": len(validations),
        "passed": sum(1 for x in validations if x.get("result") == "PASS"),
        "results": validations,
    }
    validation_path = raw_dir / "source_validation.json"
    validation_path.write_text(json.dumps(validation_report, ensure_ascii=False, indent=2), encoding="utf-8")

    scrape_manifest = {
        "date": args.date,
        "snapshot_id": snapshot_id,
        "started_at": run_started.isoformat(),
        "urls": urls,
        "scraped_pages": len(scraped_docs),
        "source_validation": str(validation_path),
        "mode": "scrape-only" if args.scrape_only or not openai_key else "scrape-and-predict",
        "files": [str(raw_dir / f"{slugify(u)}.json") for u in urls],
    }
    manifest_path = raw_dir / "manifest.json"
    manifest_path.write_text(json.dumps(scrape_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    latest_manifest = Path("data/raw") / args.date / "latest.json"
    latest_manifest.write_text(json.dumps({"date": args.date, "snapshot_id": snapshot_id, "snapshot_dir": str(raw_dir), "manifest": str(manifest_path), "source_validation": str(validation_path)}, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(validation_report, ensure_ascii=False, indent=2))
    if args.scrape_only or not openai_key:
        return

    client = OpenAI(api_key=openai_key)
    response = client.responses.create(model=model, input=build_prompt(args.date, scraped_docs))
    out_path = pred_dir / f"{args.date}-{snapshot_id}.md"
    out_path.write_text(response.output_text, encoding="utf-8")


if __name__ == "__main__":
    main()
