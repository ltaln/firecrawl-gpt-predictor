import argparse
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from match_identity import assemble, SECTIONS


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True)
    ap.add_argument("--snapshot-dir", type=Path, help="Reuse a saved Firecrawl snapshot without collecting again")
    ap.add_argument("--output-root", type=Path, default=Path("data/matches"))
    args = ap.parse_args()

    if args.snapshot_dir:
        snapshot = args.snapshot_dir
        latest = {"snapshot_id": snapshot.name}
    else:
        latest_path = Path("data/raw") / args.date / "latest.json"
        latest = json.loads(latest_path.read_text(encoding="utf-8"))
        snapshot = Path(latest["snapshot_dir"])
    records = read_records(snapshot)

    joined, unassigned = assemble(records, args.date)

    outdir = args.output_root / args.date / (latest["snapshot_id"] + "_identity_v1")
    outdir.mkdir(parents=True, exist_ok=True)
    shared = {r["category"]: r for r in records if r["category"] in {"match_list", "daily_asian_handicap_summary", "internal_model_analysis"}}
    for category in ('match_list', 'daily_asian_handicap_summary'):
        candidates = [r for r in records if r['category'] == category and
                      parse_qs(urlparse(r['url']).query).get('date') ==
                      [args.date.replace('-', '') if category == 'match_list' else args.date]]
        if candidates:
            shared[category] = max(candidates, key=lambda r: r.get('fetched_at', ''))
        else:
            shared.pop(category, None)

    index = []
    for fixture in joined:
        i, code, pages = fixture['match_no'], fixture['code'], fixture['pages']

        sections = []
        for category in ["mixed_data", "asian_handicap_changes", "score_odds_changes", "predicted_lineup", "historical_lineup_ratings"]:
            r = pages.get(category)
            if r:
                sections.append({"category": category, "url": r["url"], "markdown": markdown_of(r)})

        package = {
            "date": args.date,
            "match_no": i,
            "code": code,
            "xi": fixture['xi'],
            "kickoff_at_raw": fixture['kickoff_at_raw'],
            "identity_check": fixture['identity_check'],
            "package_version": "identity-v1",
            "snapshot_id": latest["snapshot_id"],
            "sections": sections,
            "shared_context": [
                {"category": c, "url": r["url"], "markdown": markdown_of(r)}
                for c, r in shared.items()
            ],
            "complete": all(c in pages for c in SECTIONS) and fixture['identity_check']['result'] == 'PASS',
        }
        fn = f"match_{i:03d}_{code}.json"
        (outdir / fn).write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
        index.append({"match_no": i, "code": code, "xi": fixture['xi'], "file": fn, "complete": package["complete"], "section_count": len(sections), "identity_check": fixture['identity_check']})

    summary = {
        "date": args.date,
        "snapshot_id": latest["snapshot_id"],
        "match_count": len(index),
        "complete_matches": sum(x["complete"] for x in index),
        "matches": index,
        "package_version": "identity-v1",
        "unassigned_discoveries": unassigned,
    }
    (outdir / "index.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    latest_out = args.output_root / args.date / "latest.json"
    latest_out.parent.mkdir(parents=True, exist_ok=True)
    latest_out.write_text(json.dumps({"snapshot_id": latest["snapshot_id"], "package_dir": str(outdir), "index": str(outdir / "index.json")}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
