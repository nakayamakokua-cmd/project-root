from __future__ import annotations
import sys, json, re
from pathlib import Path
from typing import List, Dict, Any
from scripts.utils import load_settings, read_json, write_json, parse_filename_meta, now_str
import subprocess, os

"""
入力: transcript_json（scripts/transcriber.py の出力）
  {
    "transcript_text": "...",
    "segments": [
      {"t": "00:10", "speaker": "OP", "text": "…"},
      ...
    ],
    "meta": {...},
    "file_meta": {"date": "...", "phone": "...", "filename": "...", "processed_at": "..."}
  }

出力（MVP拡張・スプレッドシート行に対応）:
  {
    "audio_id": "xxx.mp3",
    "date": "YYYY-MM-DD" or null,
    "operator": "担当者/または会話概要",
    "ng_major": "（大分類 日本語）",
    "ng_minor": "（中分類 日本語）",
    "ng_reason_chain": "中分類日本語を時系列順にカンマ区切り",
    "branch_kind": "#3-1 / #3-2 / #3-3 / #3-4 / MEDAPANI（#2直→日程） など",
    "phone_e164": "0始まりハイフン無し",
    "processed_at": "YYYY-MM-DD HH:MM:SS"
  }
"""

NEG_DICT_KEYS = {
    "1": "システム・ツール状況",
    "2": "業務ニーズ無し",
    "3": "即NG",
    "4": "タイミング・時期要因",
    "5": "権限・担当範囲",
    "6": "認識・情報不足",
}

# フレーズ辞書（最低限）。本番は config/dictionaries_v1.json へ拡張してOK
PHRASES = {
    "即NG": {
        "営業一律お断り": [r"営業.*お断り", r"結構です", r"不要です", r"興味(ない|ありません)"],
        "即時拒否・低関心": [r"いいです", r"間に合って(る|ます)"],
        "過去検討済み・不要結論": [r"以前.*検討.*不要", r"検討しません", r"検討していません", r"検討していない"],
    },
    "権限・担当範囲": {
        "判断権限なし": [r"決裁権.*ない", r"権限.*ない"],
        "担当者不明／履歴不明": [r"どなた.*(存じ|わか)らない", r"担当者.*不明"],
    },
    "タイミング・時期要因": {
        "繁忙期で不可": [r"(忙し|繁忙)"],
        "先の予定不透明": [r"(予定|スケジュール).*わからない"],
    },
    "システム・ツール状況": {
        "既存システム導入済み": [r"(導入済|使ってます)"],
        "競合サービス利用中": [r"(BtoBプラットフォーム|TOKIUM|バクラク|Inbox|Billone)"],
        "システム入れ替え予定なし": [r"(今ので十分|入れ替え予定.*ない)"],
        "会計システム非対応": [r"会計.*連携.*できない"],
        "顧客業務の特殊形態": [r"(原本保管|相殺計算|特殊)"],
        "最近同内容の商談実施済み": [r"(別代理店|親会社).*説明.*済"],
    },
    "業務ニーズ無し": {
        "業務量が少ない": [r"(件数|量).*(少ない|少なめ)"],
        "現行運用で十分": [r"(今の|現行).*(問題|十分)"],
        "受領業務が存在しない": [r"(発行のみ|受け取っていない)"],
    },
    "認識・情報不足": {
        "話の経緯/内容が不明": [r"(話|内容).*(わからない|不明)"],
        "発行/受取の誤認": [r"(発行|受取).*誤解|受け取りではなく発行"],
        "機能の誤認・限定理解": [r"(機能|できること).*誤解"],
        "部分利用経験による不要判断": [r"(昔|以前).*使って.*(不要|十分)"],
    },
}

# ng_master の priority_order（キー配列）で上書き可能な既定順
PRIORITY = [
    "即NG",
    "権限・担当範囲",
    "タイミング・時期要因",
    "システム・ツール状況",
    "業務ニーズ無し",
    "認識・情報不足",
]

# ========= マスタ連動（競合語・日程語・優先順） =========
SETTINGS = load_settings()
try:
    NG_MASTER = read_json(SETTINGS["masters"]["ng_master_path"])
except Exception:
    NG_MASTER = {}
try:
    SCRIPT_MASTER = read_json(SETTINGS["masters"]["script_master_path"])
except Exception:
    SCRIPT_MASTER = {}

def _compile_union(words: List[str]) -> re.Pattern:
    words = [w for w in words if isinstance(w, str) and w]
    if not words:
        return re.compile(r"$")  # match nothing
    pat = "|".join(map(re.escape, words))
    return re.compile(rf"({pat})", re.IGNORECASE)

# competitors from ng_master
_competitors = NG_MASTER.get("competitors", []) if isinstance(NG_MASTER, dict) else []
COMPETITOR_RE = _compile_union(_competitors or ["BtoBプラットフォーム","TOKIUM","バクラク","Billone","Inbox"])  # 既定補完

# date/schedule words from script_master
_dicts = (SCRIPT_MASTER.get("dictionaries") or {}) if isinstance(SCRIPT_MASTER, dict) else {}
DATE_TERMS = list({*(_dicts.get("date_terms") or []), *(_dicts.get("schedule_words") or [])})
DATE_HINT_RE = _compile_union(DATE_TERMS + [r"\d{1,2}/\d{1,2}", "月曜","火曜","水曜","木曜","金曜","午前","午後","◯日週"])  # 既定補完

# not considering/timing hints（負例辞書からの抽出＋既定）
NEG_TERMS = _dicts.get("negative") or []
NOT_CONSIDER_RE = re.compile(r"(検討していない|検討.*していない|今は.*検討|予定.*ない)")
if NEG_TERMS:
    _neg_sel = [w for w in NEG_TERMS if any(k in w for k in ["検討","予定","必要性","間に合って"])]
    if _neg_sel:
        NOT_CONSIDER_RE = _compile_union(_neg_sel)
TIMING_RE = re.compile(r"(忙し|繁忙|予定.*わから)")

# priority from ng_master
try:
    _key_to_major = {c["key"]: c["name_jp"] for c in NG_MASTER.get("categories", [])}
    _order_keys = NG_MASTER.get("priority_order") or []
    _prio_labels = [
        _key_to_major[k] for k in _order_keys if k in _key_to_major
    ]
    if _prio_labels:
        PRIORITY = _prio_labels
except Exception:
    pass

# 動的フレーズ更新（競合語をマージ）
if "システム・ツール状況" in PHRASES and "競合サービス利用中" in PHRASES["システム・ツール状況"]:
    PHRASES["システム・ツール状況"]["競合サービス利用中"] = [COMPETITOR_RE.pattern]

# ========= ステップB（コーチング: E1〜E4 + G） =========
def compile_from_master(key: str, defaults: list[str]) -> re.Pattern:
    pat_cfg = ((SCRIPT_MASTER.get("coaching") or {}).get("patterns") or {}).get(key)
    items = pat_cfg if isinstance(pat_cfg, list) and pat_cfg else defaults
    return _compile_union(items)

E1_RE = compile_from_master("E1", ["会計","自動仕訳","仕訳","連携"])
E2_RE = compile_from_master("E2", ["受領","受取","入力","確認","保管","自動"]) 
E3_RE = compile_from_master("E3", ["業務負担","工数","削減","効率化"]) 
E4_RE = compile_from_master("E4", ["情報提供","導入前提ではない","前提ではない","非圧"]) 
G_RE  = compile_from_master("G",  DATE_TERMS + [r"\d{1,2}/\d{1,2}", "月曜","火曜","水曜","木曜","金曜","午前","午後","◯日週"]) 

def compute_coaching(segments: List[Dict[str, Any]]) -> Dict[str, Any]:
    sf = (SCRIPT_MASTER.get("scoring") or {}).get("script_fit") or {}
    goal_w = int(sf.get("goal_weight", 20))
    elem_w = int(sf.get("element_weight", 20))
    threshold = int(sf.get("pass_threshold", 70))

    # OP（オペレータ）発話から検出
    def is_op(s):
        return str(s.get("speaker",""))[:2].upper() == "OP"
    evi: Dict[str, Any] = {}

    def hit(key: str, regex: re.Pattern) -> bool:
        for seg in segments:
            if not is_op(seg):
                continue
            txt = seg.get("text","")
            if regex.search(txt):
                if key not in evi:
                    evi[key] = {"t": seg.get("t"), "text": txt}
                return True
        return False

    e1 = hit("E1", E1_RE)
    e2 = hit("E2", E2_RE)
    e3 = hit("E3", E3_RE)
    e4 = hit("E4", E4_RE)
    g  = hit("G",  G_RE)

    score = (elem_w * sum([e1,e2,e3,e4])) + (goal_w if g else 0)
    passed = score >= threshold

    return {
        "signals": {"E1": e1, "E2": e2, "E3": e3, "E4": e4, "G": g},
        "score": score,
        "pass_threshold": threshold,
        "passed": passed,
        "evidence": evi,
        "weights": {"element_weight": elem_w, "goal_weight": goal_w},
    }

def parse_time_to_seconds(tstr: str) -> int:
    # "MM:SS" or "HH:MM:SS"
    parts = [int(p) for p in tstr.split(":")]
    if len(parts) == 2:
        m, s = parts
        return m * 60 + s
    elif len(parts) == 3:
        h, m, s = parts
        return h * 3600 + m * 60 + s
    return 0

def detect_candidates(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    CUS発話中心に各カテゴリの正規表現を当てて候補抽出
    """
    cands = []
    for seg in segments:
        text = seg.get("text", "")
        speaker = seg.get("speaker", "")
        t = seg.get("t", "00:00")
        tsec = parse_time_to_seconds(t)
        # どのカテゴリ/中分類に合致するか
        for major, minors in PHRASES.items():
            for minor, pats in minors.items():
                for pat in pats:
                    if re.search(pat, text):
                        cands.append({
                            "tsec": tsec,
                            "speaker": speaker,
                            "major": major,
                            "minor": minor,
                            "text": text,
                            "score_hint": 0,  # 後続の確定度で加点
                        })
                        break
    # CUS（顧客）発話をやや重く
    for c in cands:
        if c["speaker"].upper().startswith("CUS"):
            c["score_hint"] += 0.5
    # 発話強度ざっくり（終話感を含む語に+2, 強い否定+1）
    strong_end = [r"結構です", r"お断り", r"必要ありません", r"不要です"]
    strong_neg = [r"検討しません", r"予定ない", r"間に合って"]
    for c in cands:
        if any(re.search(p, c["text"]) for p in strong_end):
            c["score_hint"] += 2.0
        elif any(re.search(p, c["text"]) for p in strong_neg):
            c["score_hint"] += 1.0
    # 時間→スコア→優先カテゴリの順で安定ソート
    def prio_index(major: str) -> int:
        return PRIORITY.index(major) if major in PRIORITY else len(PRIORITY)
    return sorted(cands, key=lambda x: (x["tsec"], x["score_hint"], prio_index(x["major"])) )

def finalize_ng(cands: List[Dict[str, Any]], last_tsec: int) -> Dict[str, Any]:
    """
    終話ウィンドウ（max(60sec, 20%終盤)）内の最後を採用。無ければ終盤候補の確度タイブレーク。
    """
    if not cands:
        return {"ng_major": "不明", "ng_minor": "不明", "final": None}

    win = max(60, int(last_tsec * 0.2))
    window_start = max(0, last_tsec - win)
    in_window = [c for c in cands if c["tsec"] >= window_start]

    if in_window:
        # 終話ウィンドウ内の最終候補。同時刻が複数なら優先カテゴリ→score_hint
        same_t = [c for c in in_window if c["tsec"] == in_window[-1]["tsec"]]
        if len(same_t) == 1:
            final = in_window[-1]
        else:
            def prio_idx(c):
                return PRIORITY.index(c["major"]) if c["major"] in PRIORITY else len(PRIORITY)
            # minorタイブレーク（同一major）の簡易優先度: タイミング系は「繁忙期で不可」を優先
            def minor_bonus(c):
                if c["major"] == "タイミング・時期要因" and c.get("minor") == "繁忙期で不可":
                    return 0.5
                return 0.0
            final = sorted(same_t, key=lambda c: (prio_idx(c), c["score_hint"], minor_bonus(c)))[-1]
    else:
        tail = cands[-5:]
        def prio_idx(c):
            return PRIORITY.index(c["major"]) if c["major"] in PRIORITY else len(PRIORITY)
        tail_sorted = sorted(tail, key=lambda c: (c["tsec"], prio_idx(c), c["score_hint"]))
        final = tail_sorted[-1]

    return {"ng_major": final["major"], "ng_minor": final["minor"], "final": final}

def build_reason_chain(cands: List[Dict[str, Any]]) -> str:
    """
    中分類の日本語名を、**出現順**（重複除去しながら）でカンマ連結
    """
    seen = set()
    ordered = []
    for c in cands:
        key = (c["major"], c["minor"])
        if key not in seen:
            seen.add(key)
            ordered.append(c["minor"])
    return ",".join(ordered)

def pick_by_priority(major: str, fallback_major: str) -> str:
    """ 使わないが将来の補正用のフック """
    return major or fallback_major

def detect_branch_kind(segments: List[Dict[str, Any]]) -> str:
    """
    “最初の顧客反応”で固定。
    ざっくりルール：
      - システム/競合を示す語 → #3-2
      - 導入未検討系 → #3-3
      - 時期/忙しい → #3-4
      - それ以外で説明が続く → #3-1
      - #2直で日程確定（「◯日」「来週◯曜」など） → MEDAPANI
    """
    sys_pat = re.compile(r"(導入済|使ってます)")
    # 競合語もシステム系へ
    def has_competitor(text: str) -> bool:
        return bool(COMPETITOR_RE.search(text))
    not_considering_pat = NOT_CONSIDER_RE
    timing_pat = TIMING_RE
    date_hint = DATE_HINT_RE
    # 顧客の最初の反応（CUS）
    for seg in segments:
        if seg.get("speaker","").upper().startswith("CUS"):
            text = seg.get("text","")
            if date_hint.search(text):
                return "MEDAPANI"  # #2直→日程
            if sys_pat.search(text) or has_competitor(text):
                return "#3-2"
            if not_considering_pat.search(text):
                return "#3-3"
            if timing_pat.search(text):
                return "#3-4"
            return "#3-1"
    return "#3-1"

def main():
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.analyzer <transcript_json>", file=sys.stderr)
        sys.exit(1)

    settings = load_settings()
    ng_master = read_json(settings["masters"]["ng_master_path"])

    trans = read_json(sys.argv[1])
    segments = trans.get("segments", [])
    file_meta = trans.get("file_meta", {})

    # 候補抽出
    cands = detect_candidates(segments)

    # 終話ウィンドウで最終NG
    last_tsec = 0
    if segments:
        last_t = segments[-1].get("t","00:00")
        last_tsec = last_t and sum(int(x) * (60 ** i) for i, x in enumerate(reversed(last_t.split(":")))) or 0
    ng = finalize_ng(cands, last_tsec)

    # 理由チェーン（日本語、中分類）を**時系列順**に
    ng_reason_chain = build_reason_chain(cands)

    # 分岐パターン（最初の顧客反応で固定）
    branch_kind = detect_branch_kind(segments)

    # ステップB: コーチング（E1〜E4/G）
    coaching = compute_coaching(segments)

    # 代表オペレータ名：仮で固定（運用で名乗り抽出へ）
    operator = trans.get("meta", {}).get("note") or "未設定"

    # 電話番号・日付は file_meta を優先。無ければファイル名で補完
    audio_id = file_meta.get("filename") or "unknown"
    date_iso = file_meta.get("date")
    phone_e164 = file_meta.get("phone") or file_meta.get("phone_e164") or ""
    phone_flag = ""
    parsed = parse_filename_meta(audio_id)
    if (not date_iso):
        date_iso = parsed.get("date")
    if not phone_e164:
        phone_e164 = parsed.get("phone_e164", "")
    # 桁異常フラグ: rawがあり、10/11桁でなければ invalid_length。番号自体が無ければ missing。
    raw = parsed.get("phone_raw", "")
    if not phone_e164:
        phone_flag = "invalid_length" if raw else "missing"

    out = {
        "audio_id": audio_id,
        "date": date_iso,
        "operator": operator,
        "ng_major": ng.get("ng_major", "不明"),
        "ng_minor": ng.get("ng_minor", "不明"),
        "ng_reason_chain": ng_reason_chain,  # ← 日本語・時系列・カンマ区切り
        "branch_kind": branch_kind,
        "phone_e164": phone_e164,
        "phone_flag": phone_flag,
        "processed_at": now_str(),
    }

    # オプション: LLM分類（Gemini）で上書き（設定 + APIキーがある場合）
    used_llm = False
    settings = load_settings()
    if settings.get("features", {}).get("llm_classify"):
        api_env = settings.get("gemini", {}).get("api_key_env", "GEMINI_API_KEY")
        if os.environ.get(api_env):
            try:
                proc = subprocess.run([sys.executable, "-m", "scripts.llm_classifier", sys.argv[1]], check=True, capture_output=True, text=True)
                llm_res = json.loads(proc.stdout or "{}")
                # 最低限フィールドがある場合に採用
                if llm_res.get("ng_major") and llm_res.get("ng_minor"):
                    out.update({
                        "ng_major": llm_res.get("ng_major"),
                        "ng_minor": llm_res.get("ng_minor"),
                        "ng_reason_chain": llm_res.get("ng_reason_chain", out["ng_reason_chain"]) or out["ng_reason_chain"],
                        "branch_kind": llm_res.get("branch_kind", branch_kind) or branch_kind,
                    })
                    used_llm = True
            except Exception as e:
                # 無視してルールベース結果を採用
                pass

    # 監査用に .cache/last_analysis.json に保存
    write_json(".cache/last_analysis.json", {
        "candidates": cands,
        "final": ng.get("final"),
        "out_row": out,
        "coaching": coaching,
        "source": ("llm" if used_llm else "rule"),
    })

    # 標準出力はシート追記用の行 JSON
    json.dump(out, sys.stdout, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
