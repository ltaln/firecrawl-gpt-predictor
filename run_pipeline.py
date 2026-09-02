import argparse
import json
import os
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests
from openai import OpenAI

FIRECRAWL_ENDPOINT = "https://api.firecrawl.dev/v2/scrape"


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
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=90,
    )
    r.raise_for_status()
    body = r.json()
    if not body.get("success"):
        raise RuntimeError(f"Firecrawl failed for {url}: {body}")
    return body


def load_urls(cli_urls: list[str] | None) -> list[str]:
    if cli_urls:
        return cli_urls
    path = Path("urls.txt")
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")]


def build_prompt(target_date: str, scraped_docs: list[dict]) -> str:
    compact = []
    for item in scraped_docs:
        data = item.get("response", {}).get("data", {})
        compact.append({
            "url": item["url"],
            "metadata": data.get("metadata", {}),
            "markdown": data.get("markdown", ""),
        })

    return f"""你是一名谨慎的足球赛前数据分析助手。请只依据下面抓取到的网页数据分析 {target_date} 的比赛。

要求：
- 先识别网页中属于目标日期的全部比赛；不要凭空补比赛。
- 对每场比赛提取双方、赛事、时间、赔率/盘口/指数（若页面有）、近期信息（若页面有）。
- 给出倾向：胜/平/负、让球方向、大小球方向；没有足够信息就写“数据不足”。
- 每个结论给出 0-100 的置信度，并明确列出支撑证据。
- 严禁把预测写成确定结果；这是概率分析，不保证盈利。
- 最后输出 JSON，结构为：date, matches[], summary。matches 中包含 home, away, competition, kickoff, evidence[], prediction, confidence, risks[]。

抓取数据：
{json.dumps(compact, ensure_ascii=False)}
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--urls", nargs="*")
    args = parser.parse_args()

    firecrawl_key = os.environ.get("FIRECRAWL_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")
    model = os.environ.get("OPENAI_MODEL", "gpt-5.6-sol")
    if not firecrawl_key:
        raise SystemExit("Missing FIRECRAWL_API_KEY")
    if not openai_key:
        raise SystemExit("Missing OPENAI_API_KEY")

    urls = load_urls(args.urls)
    raw_dir = Path("data/raw") / args.date
    pred_dir = Path("data/predictions")
    raw_dir.mkdir(parents=True, exist_ok=True)
    pred_dir.mkdir(parents=True, exist_ok=True)

    scraped_docs = []
    for url in urls:
        response = scrape_url(url, firecrawl_key)
        record = {"url": url, "fetched_at": datetime.utcnow().isoformat() + "Z", "response": response}
        scraped_docs.append(record)
        (raw_dir / f"{slugify(url)}.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    client = OpenAI(api_key=openai_key)
    response = client.responses.create(
        model=model,
        input=build_prompt(args.date, scraped_docs),
    )
    text = response.output_text
    out_path = pred_dir / f"{args.date}.md"
    out_path.write_text(text, encoding="utf-8")

    manifest = {
        "date": args.date,
        "model": model,
        "urls": urls,
        "prediction_file": str(out_path),
    }
    (pred_dir / f"{args.date}.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
