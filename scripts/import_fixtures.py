from __future__ import annotations
import sys, json, csv, re
from pathlib import Path
from typing import Dict, List


def guess_speaker(line: str) -> str:
    l = line.strip()
    # 明示プレフィックス
    if re.match(r"^(OP:|オペ|営業:)", l):
        return "OP"
    if re.match(r"^(CUS:|客:|先方:|相手:)", l):
        return "CUS"
    # 断り系は顧客とみなす
    if re.search(r"(結構です|不要|興味ありません|間に合って|お断り|検討していません)", l):
        return "CUS"
    return "CUS"


def lines_to_segments(text: str) -> List[Dict[str, str]]:
    # 行優先で分割。行が無ければ句点で粗く分割
    if "\n" in text:
        parts = [p.strip() for p in text.splitlines() if p.strip()]
    else:
        parts = re.split(r"[。！？!?]", text)
        parts = [p.strip() for p in parts if p.strip()]
    segs: List[Dict[str, str]] = []
    sec = 0
    for p in parts:
        sec += 1
        m = re.match(r"^(?:OP:|CUS:|オペ|営業:|客:|先方:|相手:)(.*)$", p)
        txt = m.group(1).strip() if m else p
        spk = guess_speaker(p)
        t = f"00:{sec:02d}"
        segs.append({"t": t, "speaker": spk, "text": txt})
    if not segs:
        segs = [{"t": "00:00", "speaker": "CUS", "text": text}]
    return segs


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.import_fixtures <path.csv>")
        sys.exit(1)
    in_path = Path(sys.argv[1])
    if not in_path.exists():
        print(f"not found: {in_path}")
        sys.exit(1)

    out_dir = Path("data/fixtures/analyzer")
    out_dir.mkdir(parents=True, exist_ok=True)

    with in_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = ["id", "text"]
        for r in required:
            if r not in reader.fieldnames:
                print(f"CSVに必須列 {r} がありません。列見本: id,text,ng_major,ng_minor,branch_kind,reason_contains")
                sys.exit(1)
        count = 0
        for row in reader:
            rid = str(row.get("id") or f"row{count}")
            text = str(row.get("text") or "").strip()
            segs = lines_to_segments(text)
            expected: Dict[str, object] = {}
            for k in ("ng_major","ng_minor","branch_kind"):
                v = (row.get(k) or "").strip()
                if v:
                    expected[k] = v
            rc = (row.get("reason_contains") or "").strip()
            if rc:
                expected["reason_contains"] = [x.strip() for x in rc.split(";") if x.strip()]
            obj = {
                "transcript_text": text,
                "segments": segs,
                "meta": {"language": "ja"},
                "file_meta": {"filename": f"bulk_{rid}.mp3"},
            }
            if expected:
                obj["expected"] = expected
            out_path = out_dir / f"bulk_{rid}.json"
            out_path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
            count += 1
    print(f"wrote fixtures to {out_dir}")


if __name__ == "__main__":
    main()

