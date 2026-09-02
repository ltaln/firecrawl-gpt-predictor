import argparse
import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse


def markdown_of(record):
    return record.get("response", {}).get("data", {}).get("markdown", "")


def read_records(snapshot):
    records = []
    for p in snapshot.glob("*.json"):
        if p.name in {"manifest.json", "source_validation.json", "url_discovery.json"}:
            continue
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(obj, dict) and obj.get("url") and obj.get("category"):
            records.append(obj)
    return records


def match_no(record, date):
    p = urlparse(record["url"])
    q = parse_qs(p.query)
    if p.path in {"/tx/10013.php", "/tx/10017.php"}:
        v = (q.get("changci") or [""])[0]
        return int(v) if v.isdigit() else None
    if p.path in {"/tx/10015.php", "/tx/10016.php"}:
        code = (q.get("code") or [""])[0]
        compact = date.replace("-", "")
        if re.fullmatch(r"\d{11}", code) and code.startswith(compact):
            return int(code[-3:])
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True)
    args = ap.parse_args()

    latest_path = Path("data/raw") / args.date / "latest.json"
    latest = json.loads(latest_path.read_text(encoding="utf-8"))
    snapshot = Path(latest["snapshot_dir"])
    records = read_records(snapshot)

    mixed = sorted((r for r in records if r["category"] == "mixed_data"), key=lambda r: int(parse_qs(urlparse(r["url"]).query)["id"][0]))
    if not mixed:
        raise SystemExit("No mixed_data pages found")

    outdir = Path("data/matches") / args.date / latest["snapshot_id"]
    outdir.mkdir(parents=True, exist_ok=True)
    shared = {r["category"]: r for r in records if r["category"] in {"match_list", "daily_asian_handicap_summary", "internal_model_analysis"}}

    index = []
    for i, mix in enumerate(mixed, 1):
        code = f"{args.date.replace('-', '')}{i:03d}"
        pages = {"mixed_data": mix}
        for r in records:
            if match_no(r, args.date) == i:
                pages[r["category"]] = r

        sections = []
        for category in ["mixed_data", "asian_handicap_changes", "score_odds_changes", "predicted_lineup", "historical_lineup_ratings"]:
            r = pages.get(category)
            if r:
                sections.append({"category": category, "url": r["url"], "markdown": markdown_of(r)})

        package = {
            "date": args.date,
            "match_no": i,
            "code": code,
            "snapshot_id": latest["snapshot_id"],
            "sections": sections,
            "shared_context": [
                {"category": c, "url": r["url"], "markdown": markdown_of(r)}
                for c, r in shared.items()
            ],
            "complete": all(c in pages for c in ["mixed_data", "asian_handicap_changes", "score_odds_changes", "predicted_lineup", "historical_lineup_ratings"]),
        }
        fn = f"match_{i:03d}_{code}.json"
        (outdir / fn).write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
        index.append({"match_no": i, "code": code, "file": fn, "complete": package["complete"], "section_count": len(sections)})

    summary = {
        "date": args.date,
        "snapshot_id": latest["snapshot_id"],
        "match_count": len(index),
        "complete_matches": sum(x["complete"] for x in index),
        "matches": index,
    }
    (outdir / "index.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    latest_out = Path("data/matches") / args.date / "latest.json"
    latest_out.parent.mkdir(parents=True, exist_ok=True)
    latest_out.write_text(json.dumps({"snapshot_id": latest["snapshot_id"], "package_dir": str(outdir), "index": str(outdir / "index.json")}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
