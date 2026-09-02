import argparse
import json
import os
from pathlib import Path

from openai import OpenAI

SYSTEM_PROMPT = """你是足球比赛数据分析模型。只允许依据输入的数据包进行判断，不补充外部信息，不臆造缺失数据。
请重点综合：混合数据、亚盘/水位变化、比分赔率变化、预测首发、历史首发与评分，以及共享的当日盘口汇总和站内模型分析。
输出必须是严格 JSON，字段如下：
{
  "match_no": 整数,
  "code": "比赛code",
  "home_team": "主队",
  "away_team": "客队",
  "result_probabilities": {"home": 0-100, "draw": 0-100, "away": 0-100},
  "primary_pick": "主胜/平/客胜",
  "double_chance": "主不败/客不败/主客分胜负/无",
  "predicted_score": "如 2-1",
  "confidence": 0-100,
  "key_evidence": ["最多6条关键依据"],
  "risk_flags": ["最多4条风险或矛盾点"],
  "data_quality": "high/medium/low"
}
三个胜平负概率之和必须为100。不要输出 JSON 之外的任何文字。"""


def load_packages(date):
    latest = Path("data/matches") / date / "latest.json"
    latest_obj = json.loads(latest.read_text(encoding="utf-8"))
    index = json.loads(Path(latest_obj["index"]).read_text(encoding="utf-8"))
    package_dir = Path(latest_obj["package_dir"])
    items = []
    for m in index["matches"]:
        path = package_dir / m["file"]
        items.append((m, json.loads(path.read_text(encoding="utf-8"))))
    return latest_obj, index, items


def parse_json_output(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].lstrip()
    return json.loads(text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True)
    ap.add_argument("--model", default=os.getenv("OPENAI_MODEL", "gpt-5.6-sol"))
    args = ap.parse_args()

    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise SystemExit("Missing OPENAI_API_KEY")

    latest, index, items = load_packages(args.date)
    client = OpenAI(api_key=key)
    outdir = Path("data/predictions") / args.date / latest["snapshot_id"]
    outdir.mkdir(parents=True, exist_ok=True)

    results = []
    for meta, package in items:
        payload = json.dumps(package, ensure_ascii=False)
        response = client.responses.create(
            model=args.model,
            instructions=SYSTEM_PROMPT,
            input=f"请分析以下第 {meta['match_no']} 场比赛数据包：\n{payload}",
        )
        parsed = parse_json_output(response.output_text)
        parsed["match_no"] = meta["match_no"]
        parsed["code"] = meta["code"]
        probs = parsed.get("result_probabilities", {})
        total = sum(float(probs.get(k, 0)) for k in ("home", "draw", "away"))
        if abs(total - 100) > 0.01:
            raise ValueError(f"Probability total is not 100 for match {meta['match_no']}: {total}")
        results.append(parsed)
        (outdir / f"match_{meta['match_no']:03d}_{meta['code']}.json").write_text(
            json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    summary = {
        "date": args.date,
        "snapshot_id": latest["snapshot_id"],
        "model": args.model,
        "match_count": len(results),
        "predictions": results,
    }
    (outdir / "predictions.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    latest_out = Path("data/predictions") / args.date / "latest.json"
    latest_out.parent.mkdir(parents=True, exist_ok=True)
    latest_out.write_text(json.dumps({
        "snapshot_id": latest["snapshot_id"],
        "model": args.model,
        "prediction_dir": str(outdir),
        "predictions": str(outdir / "predictions.json")
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
