import argparse
import json
import os
import re
from collections import deque
from datetime import datetime, timezone
from difflib import SequenceMatcher
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from openai import OpenAI

FIRECRAWL_ENDPOINT = "https://api.firecrawl.dev/v2/scrape"
BASE_URL = "https://www.hh520.com/"
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


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "a":
            return
        for key, value in attrs:
            if key.lower() == "href" and value:
                self.links.append(value)


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


def load_seed_urls(cli_urls: list[str] | None, target_date: str) -> list[str]:
    seeds = []
    if cli_urls:
        seeds.extend(cli_urls)
    else:
        path = Path("urls.txt")
        if path.exists():
            seeds.extend(
                line.strip()
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.startswith("#")
            )
    compact_date = target_date.replace("-", "")
    seeds.extend([
        BASE_URL,
        f"{BASE_URL}?date={compact_date}",
        f"{BASE_URL}tx/10012.php?date={target_date}",
        f"{BASE_URL}tx/7.php",
    ])
    seen = set()
    ordered = []
    for url in seeds:
        if url not in seen:
            seen.add(url)
            ordered.append(url)
    return ordered


def extract_links(html: str, base_url: str) -> list[str]:
    parser = LinkParser()
    parser.feed(html or "")
    result = []
    for href in parser.links:
        absolute = urljoin(base_url, href)
        p = urlparse(absolute)
        if p.scheme in {"http", "https"} and p.netloc.lower() in {"hh520.com", "www.hh520.com"}:
            result.append(absolute)
    return result


def classify_supported_url(url: str, target_date: str) -> str | None:
    p = urlparse(url)
    path = p.path
    q = parse_qs(p.query)
    compact = target_date.replace("-", "")

    if path in {"", "/"}:
        date_value = (q.get("date") or [""])[0]
        if not date_value or date_value == compact:
            return "match_list"
        return None

    if path == "/xi.php" and (q.get("id") or [""])[0].isdigit():
        return "mixed_data"

    if path == "/tx/10017.php":
        if (q.get("riqi") or [""])[0] == target_date and (q.get("changci") or [""])[0].isdigit():
            return "score_odds_changes"
        return None

    if path in {"/tx/10016.php", "/tx/10015.php"}:
        code = (q.get("code") or [""])[0]
        if re.fullmatch(r"\d{11}", code) and code.startswith(compact):
            return "predicted_lineup" if path.endswith("10016.php") else "historical_lineup_ratings"
        return None

    if path == "/tx/10012.php":
        if (q.get("date") or [""])[0] == target_date:
            return "daily_asian_handicap_summary"
        return None

    if path == "/tx/10013.php":
        if (q.get("date") or [""])[0] == target_date and (q.get("changci") or [""])[0].isdigit():
            return "asian_handicap_changes"
        return None

    if path == "/tx/7.php":
        return "internal_model_analysis"

    return None


def discover_supported_urls(html: str, base_url: str, target_date: str) -> list[tuple[str, str]]:
    found = []
    seen = set()
    for url in extract_links(html, base_url):
        category = classify_supported_url(url, target_date)
        if category and url not in seen:
            seen.add(url)
            found.append((url, category))
    return found


def build_prompt(target_date: str, scraped_docs: list[dict]) -> str:
    compact = []
    for item in scraped_docs:
        data = item.get("response", {}).get("data", {})
        compact.append({
            "url": item["url"],
            "category": item.get("category"),
            "metadata": data.get("metadata", {}),
            "markdown": data.get("markdown", ""),
        })
    return f"请只依据以下抓取数据分析 {target_date} 的足球比赛，不要补充未抓取信息。\n{json.dumps(compact, ensure_ascii=False)}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--urls", nargs="*")
    parser.add_argument("--scrape-only", action="store_true")
    parser.add_argument("--skip-source-validation", action="store_true")
    parser.add_argument("--max-pages", type=int, default=500)
    args = parser.parse_args()

    firecrawl_key = os.environ.get("FIRECRAWL_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")
    model = os.environ.get("OPENAI_MODEL", "gpt-5.6-sol")
    if not firecrawl_key:
        raise SystemExit("Missing FIRECRAWL_API_KEY")

    run_started = datetime.now(timezone.utc)
    snapshot_id = run_started.strftime("%Y%m%dT%H%M%SZ")
    raw_dir = Path("data/raw") / args.date / "snapshots" / snapshot_id
    source_dir = raw_dir / "source"
    pred_dir = Path("data/predictions")
    raw_dir.mkdir(parents=True, exist_ok=True)
    source_dir.mkdir(parents=True, exist_ok=True)
    pred_dir.mkdir(parents=True, exist_ok=True)

    queue = deque()
    queued = set()
    for seed in load_seed_urls(args.urls, args.date):
        category = classify_supported_url(seed, args.date) or "seed"
        queue.append((seed, category, "seed"))
        queued.add(seed)

    scraped_docs = []
    validations = []
    discovered_records = []
    processed = set()

    while queue and len(processed) < args.max_pages:
        url, category, discovered_from = queue.popleft()
        if url in processed:
            continue
        processed.add(url)

        source = None
        if not args.skip_source_validation:
            print(f"Direct source fetch: {url}")
            try:
                source = fetch_source(url)
                (source_dir / f"{slugify(url)}.html").write_text(source["html"], encoding="utf-8")
            except Exception as exc:
                source = {"error": str(exc), "fetched_at": datetime.now(timezone.utc).isoformat()}

        print(f"Firecrawl scrape [{category}]: {url}")
        response = scrape_url(url, firecrawl_key)
        record = {
            "url": url,
            "category": category,
            "discovered_from": discovered_from,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "snapshot_id": snapshot_id,
            "response": response,
        }
        scraped_docs.append(record)
        (raw_dir / f"{slugify(url)}.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

        if source and "html" in source:
            validations.append(validate_source(url, source, response))
        elif source:
            validations.append({"url": url, "result": "SOURCE_FETCH_FAILED", "error": source.get("error")})

        data = response.get("data", {})
        discovery_html = data.get("rawHtml") or data.get("html") or (source or {}).get("html", "")
        for new_url, new_category in discover_supported_urls(discovery_html, url, args.date):
            if new_url not in queued and new_url not in processed:
                queued.add(new_url)
                queue.append((new_url, new_category, url))
                discovered_records.append({"url": new_url, "category": new_category, "discovered_from": url})

    validation_report = {
        "date": args.date,
        "snapshot_id": snapshot_id,
        "validated_urls": len(validations),
        "passed": sum(1 for x in validations if x.get("result") == "PASS"),
        "checked": sum(1 for x in validations if x.get("result") == "CHECK"),
        "results": validations,
    }
    validation_path = raw_dir / "source_validation.json"
    validation_path.write_text(json.dumps(validation_report, ensure_ascii=False, indent=2), encoding="utf-8")

    category_counts = {}
    for item in scraped_docs:
        category_counts[item["category"]] = category_counts.get(item["category"], 0) + 1

    discovery_report = {
        "date": args.date,
        "snapshot_id": snapshot_id,
        "seed_urls": load_seed_urls(args.urls, args.date),
        "processed_pages": len(scraped_docs),
        "category_counts": category_counts,
        "discovered": discovered_records,
        "max_pages": args.max_pages,
        "truncated": bool(queue),
    }
    discovery_path = raw_dir / "url_discovery.json"
    discovery_path.write_text(json.dumps(discovery_report, ensure_ascii=False, indent=2), encoding="utf-8")

    scrape_manifest = {
        "date": args.date,
        "snapshot_id": snapshot_id,
        "started_at": run_started.isoformat(),
        "scraped_pages": len(scraped_docs),
        "category_counts": category_counts,
        "source_validation": str(validation_path),
        "url_discovery": str(discovery_path),
        "mode": "scrape-only" if args.scrape_only or not openai_key else "scrape-and-predict",
        "files": [str(raw_dir / f"{slugify(x['url'])}.json") for x in scraped_docs],
    }
    manifest_path = raw_dir / "manifest.json"
    manifest_path.write_text(json.dumps(scrape_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    latest_manifest = Path("data/raw") / args.date / "latest.json"
    latest_manifest.write_text(json.dumps({
        "date": args.date,
        "snapshot_id": snapshot_id,
        "snapshot_dir": str(raw_dir),
        "manifest": str(manifest_path),
        "source_validation": str(validation_path),
        "url_discovery": str(discovery_path),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({"validation": validation_report, "discovery": discovery_report}, ensure_ascii=False, indent=2))
    if args.scrape_only or not openai_key:
        return

    client = OpenAI(api_key=openai_key)
    response = client.responses.create(model=model, input=build_prompt(args.date, scraped_docs))
    out_path = pred_dir / f"{args.date}-{snapshot_id}.md"
    out_path.write_text(response.output_text, encoding="utf-8")


if __name__ == "__main__":
    main()
