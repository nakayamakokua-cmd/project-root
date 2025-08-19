import json, re, os
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config"

def load_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def load_settings():
    return load_json(CONFIG / "settings.json")

def load_ng_master(settings=None):
    settings = settings or load_settings()
    return load_json(ROOT / settings["masters"]["ng_master_path"])

def load_script_master(settings=None):
    settings = settings or load_settings()
    return load_json(ROOT / settings["masters"]["script_master_path"])

def parse_filename_meta(filename: str):
    """
    例: 2025-08-08_0126253377_kokua5_u849bUjBAPkZ_112600.mp3
    -> date=2025-08-08, phone=0126253377
    """
    name = Path(filename).stem
    parts = name.split("_")
    date_iso = None
    phone = None
    if len(parts) >= 2:
        # 日付
        if re.match(r"^\d{4}-\d{2}-\d{2}$", parts[0]):
            date_iso = parts[0]
        # 電話番号（第2トークンを採用、数字以外除去→0始まりハイフン無し）
        digits = re.sub(r"\D", "", parts[1])
        if digits and digits[0] != "0":
            # 0始まりに矯正はしない。要件により必要ならここで補正。
            phone = digits
        else:
            phone = digits or None
    return {
        "date": date_iso,
        "phone": phone
    }

def ensure_dirs(settings=None):
    settings = settings or load_settings()
    for key in ("temp_dir","log_dir"):
        d = ROOT / settings["io"][key]
        d.mkdir(parents=True, exist_ok=True)

def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

