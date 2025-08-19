from __future__ import annotations
import os
import sys
import json
from pathlib import Path
from typing import List, Dict

import httplib2
import google_auth_httplib2
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# ========= ユーティリティ =========
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

def load_settings() -> Dict:
    with open("config/settings.json", "r", encoding="utf-8") as f:
        return json.load(f)

def get_timeout() -> int:
    # 既定 30秒（以前の既定 5秒 を上書き）
    return int(os.environ.get("GOOGLE_API_TIMEOUT", "30"))

def get_num_retries() -> int:
    # 既定 3回
    return int(os.environ.get("GOOGLE_API_RETRIES", "3"))

def ensure_dirs(*paths: str) -> None:
    for p in paths:
        Path(p).mkdir(parents=True, exist_ok=True)

# ========= 認証 & サービス =========
def build_sheets_service() -> any:
    """
    httplib2.Http(timeout=...) を通して AuthorizedHttp を作成し、
    build(..., http=authed_http) で **全リクエストのタイムアウト**を強制。
    """
    timeout = get_timeout()
    http = httplib2.Http(timeout=timeout)

    creds: Credentials | None = None
    # 認証/トークンの後方互換: config/ を優先し、無ければプロジェクト直下も許可
    token_paths = [Path("config/token.json"), Path("token.json")]
    token_path = next((p for p in token_paths if p.exists()), token_paths[0])
    cred_paths = [Path("config/credentials.json"), Path("credentials.json")]
    cred_path  = next((p for p in cred_paths if p.exists()), cred_paths[0])  # OAuth クライアントID

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # 期限切れ→リフレッシュ
            creds.refresh(google_auth_httplib2.Request(http=http))  # type: ignore
        else:
            if not any(p.exists() for p in cred_paths):
                raise FileNotFoundError("config/credentials.json または ./credentials.json が見つかりません。")
            flow = InstalledAppFlow.from_client_secrets_file(str(cred_path), SCOPES)
            # NOTE: 初回のローカル同意画面フロー。以降は token.json を再利用
            creds = flow.run_local_server(port=0)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")

    authed_http = google_auth_httplib2.AuthorizedHttp(creds, http=http)
    service = build("sheets", "v4", http=authed_http, cache_discovery=False)
    return service

# ========= API ラッパ（リトライ付き） =========
@retry(
    reraise=True,
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type((HttpError, TimeoutError, OSError))
)
def sheets_get_values(svc, spreadsheet_id: str, rng: str) -> Dict:
    return svc.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id, range=rng
    ).execute(num_retries=get_num_retries())

@retry(
    reraise=True,
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type((HttpError, TimeoutError, OSError))
)
def sheets_update_values(svc, spreadsheet_id: str, rng: str, values: List[List[str]]) -> Dict:
    body = {"values": values, "majorDimension": "ROWS"}
    return svc.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id, range=rng,
        valueInputOption="RAW", body=body
    ).execute(num_retries=get_num_retries())

@retry(
    reraise=True,
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type((HttpError, TimeoutError, OSError))
)
def sheets_append_values(svc, spreadsheet_id: str, rng: str, values: List[List[str]]) -> Dict:
    body = {"values": values, "majorDimension": "ROWS"}
    return svc.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id, range=rng,
        valueInputOption="RAW", insertDataOption="INSERT_ROWS", body=body
    ).execute(num_retries=get_num_retries())

# ========= ヘッダー整備 =========
WANTED_COLS = [
    "audio_id","date","operator",
    "ng_major","ng_minor","ng_reason_chain",
    "branch_kind","phone_e164","phone_flag","processed_at"
]

def ensure_header_and_get_cols(svc, spreadsheet_id: str, sheet_name: str, wanted_cols: List[str]) -> List[str]:
    rng = f"{sheet_name}!1:1"
    res = sheets_get_values(svc, spreadsheet_id, rng)
    header = res.get("values", [[]])
    header_row = header[0] if header else []

    # 既存ヘッダーに足りない列を右側に追加
    missing = [c for c in wanted_cols if c not in header_row]
    if missing:
        new_header = header_row + missing
        sheets_update_values(svc, spreadsheet_id, f"{sheet_name}!1:1", [new_header])
        return new_header
    return header_row

# ========= CSV フォールバック =========
def fallback_to_csv(row: Dict):
    ensure_dirs("Outputs/csv")
    out = Path("Outputs/csv/append_fallback.csv")
    newfile = not out.exists()
    with out.open("a", encoding="utf-8") as f:
        if newfile:
            f.write(",".join(WANTED_COLS) + "\n")
        line = [str(row.get(k,"")) for k in WANTED_COLS]
        # CSVエスケープ簡易
        line = [x.replace('"','""') for x in line]
        f.write(",".join(f'"{x}"' for x in line) + "\n")
    print(f"⚠️ Sheetsに書けなかったので CSV へ追記: {out}")
    # 互換: NDJSON にも追記（Makefile の resend-fallback 対応）
    ndjson_path = Path("Outputs/csv/append_fallback.ndjson")
    with ndjson_path.open("a", encoding="utf-8") as nf:
        nf.write(json.dumps(row, ensure_ascii=False) + "\n")

# ========= メイン =========
def main():
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.sheets_writer <row_json>", file=sys.stderr)
        sys.exit(1)

    row_path = Path(sys.argv[1])
    row = json.loads(row_path.read_text(encoding="utf-8"))

    settings = load_settings()
    # sheets → google の順でフォールバック（移行期間サポート）
    sheets_cfg = settings.get("sheets") or settings.get("google") or {}
    spreadsheet_id = sheets_cfg.get("spreadsheet_id")
    sheet_name     = sheets_cfg.get("sheet_name")
    if not spreadsheet_id or not sheet_name:
        raise KeyError("settings.json に 'sheets' または 'google' の 'spreadsheet_id' / 'sheet_name' が必要です。")

    try:
        svc = build_sheets_service()
        col_order = ensure_header_and_get_cols(svc, spreadsheet_id, sheet_name, WANTED_COLS)

        # col_order に合わせて 1行を作る
        values = [[str(row.get(k,"")) for k in col_order]]
        # 2行目以降に append
        rng = f"{sheet_name}!A2"
        sheets_append_values(svc, spreadsheet_id, rng, values)
        print("✅ appended to Google Sheets")

    except Exception as e:
        # ネットワーク不安定などで失敗 → CSV に退避
        print(f"ERROR writing to Sheets: {e}", file=sys.stderr)
        fallback_to_csv(row)
        # 監査ログにも保存
        Path(".cache").mkdir(parents=True, exist_ok=True)
        Path(".cache/last_sheets_error.txt").write_text(repr(e), encoding="utf-8")

if __name__ == "__main__":
    main()
