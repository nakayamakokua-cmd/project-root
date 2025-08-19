from __future__ import annotations
import json
import re
from pathlib import Path
from datetime import datetime, timezone, timedelta

def load_settings() -> dict:
    with open("config/settings.json", "r", encoding="utf-8") as f:
        return json.load(f)

def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def ensure_dirs(*paths: str) -> None:
    for p in paths:
        Path(p).mkdir(parents=True, exist_ok=True)

def parse_filename_meta(filename: str) -> dict:
    """
    期待形式: 2025-08-08_0126253377_kokua5_u849bUjBAPkZ_112600.mp3
    date: 第1トークン (YYYY-MM-DD)
    phone: 第2トークン (数値抽出→0始まりハイフン無し/E.164風)
    """
    stem = Path(filename).stem
    toks = stem.split("_")
    date_iso = None
    phone_raw = None
    if len(toks) >= 2:
        # 日付
        m = re.match(r"(\d{4}-\d{2}-\d{2})", toks[0])
        if m:
            date_iso = m.group(1)
        # 電話番号（半角数字だけ）
        digits = re.sub(r"\D", "", toks[1])
        if digits:
            # 先頭0維持、ハイフン無し
            if digits.startswith("0"):
                phone_raw = digits
            else:
                # 国内0始まりに寄せる（簡易）
                phone_raw = "0" + digits
    phone_valid = phone_raw if phone_raw and len(phone_raw) in (10, 11) else ""
    return {
        "date": date_iso,
        "phone_e164": phone_valid,
        "filename": Path(filename).name,
        "phone_raw": phone_raw or "",
        "phone_valid": bool(phone_valid),
    }

def read_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def write_json(path: str, obj: dict) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
