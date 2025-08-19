from __future__ import annotations
import sys, json, os, time
from pathlib import Path
from typing import Any, Dict

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from scripts.utils import load_settings, parse_filename_meta, now_str

# ダミー実装（オフライン/キー未設定時フォールバック）
def fake_transcribe(path: str) -> dict:
    return {
        "transcript_text": "（ダミー）音声のテスト出力です。",
        "segments": [
            {"t": "00:10", "speaker": "OP", "text": "もしもし。KOKUAの田中でございます。"},
            {"t": "00:12", "speaker": "CUS", "text": "はい。"},
            {"t": "00:20", "speaker": "CUS", "text": "営業はお断りしています。"}
        ],
        "meta": {"language":"ja", "note":"テスト", "engine":"fake"},
    }

class TranscribeError(Exception):
    pass

def _parse_json_maybe(text: str) -> Dict[str, Any] | None:
    try:
        return json.loads(text)
    except Exception:
        return None

def _build_prompt() -> str:
    return (
        "次の音声を日本語で正確に文字起こししてください。"
        "結果は必ずJSONのみで返してください。スキーマ: "
        "{\"transcript_text\": string, \"segments\": [{\"t\": \"MM:SS\", \"speaker\": \"OP|CUS\", \"text\": string}], "
        "\"meta\": {\"language\": \"ja\"}}。"
        "話者は大まかで良いので、オペレータ=OP, 顧客=CUS として区別し、"
        "各セグメントの先頭相対時刻 t は分:秒で記載してください。"
    )

def _coerce_segments(obj: Dict[str, Any]) -> Dict[str, Any]:
    # 期待キーが欠ける場合の補完
    trans = obj.get("transcript_text") or obj.get("text") or ""
    segs = obj.get("segments") or []
    if not isinstance(segs, list) or not segs:
        # 1本に畳み込む
        segs = [{"t": "00:00", "speaker": "OP", "text": trans or ""}]
    # 正規化
    norm = []
    for s in segs:
        t = str(s.get("t") or s.get("time") or "00:00")
        sp = str(s.get("speaker") or s.get("spk") or "").upper()
        sp = "OP" if sp.startswith("OP") else ("CUS" if sp.startswith("CUS") else "CUS")
        txt = str(s.get("text") or s.get("utterance") or "")
        norm.append({"t": t, "speaker": sp, "text": txt})
    return {"transcript_text": trans, "segments": norm}

def _gemini_call(model_name: str, api_key: str, audio_path: str) -> Dict[str, Any]:
    try:
        import google.generativeai as genai
    except Exception as e:
        raise TranscribeError(f"google-generativeai の読み込みに失敗: {e}")

    genai.configure(api_key=api_key)

    # JSON返却を強制する設定（対応版ライブラリが必要）
    generation_config = {
        "response_mime_type": "application/json",
        "temperature": 0.2,
    }
    model = genai.GenerativeModel(model_name, generation_config=generation_config)

    # ファイルをアップロードして参照
    file_obj = genai.upload_file(path=audio_path)

    prompt = _build_prompt()
    resp = model.generate_content([prompt, file_obj])

    # 一部バージョンは resp.text にJSON文字列が入る
    text = getattr(resp, "text", None) or ""
    data = _parse_json_maybe(text)
    if not data:
        # code block的な返答などに備える: 最初の候補パーツを走査
        try:
            for cand in (resp.candidates or []):
                for part in (cand.content.parts or []):
                    chunk = getattr(part, "text", None)
                    if not chunk:
                        continue
                    data = _parse_json_maybe(chunk)
                    if data:
                        break
                if data:
                    break
        except Exception:
            pass
    if not data:
        raise TranscribeError("Gemini応答のJSON解析に失敗しました")
    base = _coerce_segments(data)
    base.setdefault("meta", {})
    base["meta"].update({"language": "ja", "engine": "gemini", "model": model_name})
    return base

@retry(reraise=True, stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=1, max=8),
       retry=retry_if_exception_type((TranscribeError, Exception)))
def do_gemini_transcribe(path: str, settings: dict) -> dict:
    """Geminiへ音声を投げてJSONでセグメントを取得。失敗時はリトライ。
    ネット不可・キー未設定時は fake にフォールバック。
    """
    gem = settings.get("gemini", {})
    api_env = gem.get("api_key_env", "GEMINI_API_KEY")
    api_key = os.environ.get(api_env)
    model = gem.get("model_transcribe", "gemini-2.5-pro")
    if not api_key:
        return fake_transcribe(path)

    try:
        return _gemini_call(model, api_key, path)
    except Exception as e:
        # 一時的失敗は tenacity でリトライ。最終的失敗は fake にフォールバック。
        raise TranscribeError(str(e))

def main():
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.transcriber <audio_file>", file=sys.stderr)
        sys.exit(1)

    audio_path = sys.argv[1]
    settings = load_settings()

    # 実装方針：APIキーがあれば Gemini 経由（失敗時は指数バックオフ/フォールバック）
    try:
        trans = do_gemini_transcribe(audio_path, settings)
    except Exception:
        trans = fake_transcribe(audio_path)

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
