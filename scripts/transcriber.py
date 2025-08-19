from __future__ import annotations
import sys, json, os, time
from pathlib import Path
from scripts.utils import load_settings, parse_filename_meta, now_str

# ダミー/簡易実装。Gemini API キーが設定されていれば将来の置換ポイントを通る構成。

def fake_transcribe(path: str) -> dict:
    return {
        "transcript_text": "…",
        "segments": [
            {"t": "00:10", "speaker": "OP", "text": "もしもし。"},
            {"t": "00:11", "speaker": "CUS", "text": "はい。"},
        ],
        "meta": {"language":"ja", "note":"テスト", "engine":"fake"},
    }

def do_gemini_transcribe(path: str, settings: dict) -> dict:
    # スケルトン：環境によってはネット不可のため、APIキーがあってもダミーを返す
    gem = settings.get("gemini", {})
    api_env = gem.get("api_key_env", "GEMINI_API_KEY")
    api_key = os.environ.get(api_env)
    model = gem.get("model_transcribe", "gemini-2.5-pro")
    if not api_key:
        return fake_transcribe(path)
    # ここに実際の API 呼び出し（429/5xx の指数バックオフ込み）を実装予定
    # 仕様上はネットが使えない環境でも安全に動くよう、現時点ではダミー出力
    time.sleep(0.1)
    out = fake_transcribe(path)
    out["meta"]["engine"] = "gemini"
    out["meta"]["model"] = model
    return out

def main():
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.transcriber <audio_file>", file=sys.stderr)
        sys.exit(1)

    audio_path = sys.argv[1]
    settings = load_settings()

    # 実装方針：APIキーがあれば Gemini 経由（現状は同等ダミー）、無ければ常にダミー
    trans = do_gemini_transcribe(audio_path, settings)

    parsed = parse_filename_meta(audio_path)
    trans["file_meta"] = {
        "date": parsed.get("date"),
        "phone": parsed.get("phone_e164"),
        "filename": Path(audio_path).name,
        "processed_at": now_str(),
    }

    json.dump(trans, sys.stdout, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
