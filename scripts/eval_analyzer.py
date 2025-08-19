from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Any

# 既存実装の関数を利用
from scripts.analyzer import detect_candidates, finalize_ng, build_reason_chain, detect_branch_kind, parse_time_to_seconds


def eval_one(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    segments = data.get("segments", [])
    # 候補抽出
    cands = detect_candidates(segments)
    last_tsec = 0
    if segments:
        last_t = segments[-1].get("t", "00:00")
        last_tsec = parse_time_to_seconds(last_t)
    ng = finalize_ng(cands, last_tsec)
    ng_reason = build_reason_chain(cands)
    branch = detect_branch_kind(segments)

    actual = {
        "ng_major": ng.get("ng_major"),
        "ng_minor": ng.get("ng_minor"),
        "ng_reason_chain": ng_reason,
        "branch_kind": branch,
    }
    exp = data.get("expected", {})

    def contains_all(hay: str, needles: list[str]) -> bool:
        return all(n in hay for n in needles)

    res = {
        "file": path.name,
        "expected": exp,
        "actual": actual,
        "pass": True,
        "checks": {}
    }

    # チェック（指定があるもののみ）
    checks = {}
    if exp.get("ng_major"):
        checks["ng_major"] = (actual["ng_major"] == exp["ng_major"])
    if exp.get("ng_minor"):
        checks["ng_minor"] = (actual["ng_minor"] == exp["ng_minor"])
    if exp.get("branch_kind"):
        checks["branch_kind"] = (actual["branch_kind"] == exp["branch_kind"])
    if exp.get("reason_contains"):
        checks["reason_contains"] = contains_all(actual["ng_reason_chain"], exp["reason_contains"])  # type: ignore

    res["checks"] = checks
    res["pass"] = all(checks.values()) if checks else True
    return res


def main():
    base = Path("data/fixtures/analyzer")
    base.mkdir(parents=True, exist_ok=True)
    files = sorted(base.glob("*.json"))
    if not files:
        print(f"No fixtures in {base}")
        return
    results = [eval_one(p) for p in files]
    total = len(results)
    passed = sum(1 for r in results if r.get("pass"))
    print(f"Analyzer eval: {passed}/{total} passed")
    for r in results:
        mark = "✅" if r["pass"] else "❌"
        print(f" {mark} {r['file']} :: checks={r['checks']}")
    # 詳細レポート
    Path("logs").mkdir(parents=True, exist_ok=True)
    Path("logs/eval_analyzer_report.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

