import os, io, json, time
from pathlib import Path
from typing import Dict, Any
import google.generativeai as genai

from scripts.utils import load_settings, parse_filename_meta, ensure_dirs, now_str

# 文字起こしプロンプト（要件反映）
PROMPT = """
こちらはSansan株式会社の請求書処理システムBill Oneのテレアポ音源です。
次の要件でJSONを出力してください。

【要件】
- #2（担当者接触後）以降の会話を中心に文字起こし
- 話者分離（OP=オペレーター / CUS=顧客）とタイムスタンプ（mm:ss精度で可）
- 1発話=1要素。{t, speaker, text} を配列で
- 冒頭〜終話の挨拶も含める（受付のみのやり取りは省略可）

【出力JSONスキーマ】
{
  "transcript_text": "全文テキスト",
  "segments": [
    {"t": "00:12", "speaker": "OP", "text": "…"},
    {"t": "00:19", "speaker": "CUS", "text": "…"}
  ],
  "meta": {"language": "ja", "note": "any"}
}
"""

def _configure_gemini(settings):
    api_key = os.environ.get(settings["gemini"]["api_key_env"])
    if not api_key:
        raise RuntimeError(f"環境変数 {settings['gemini']['api_key_env']} が未設定です。export してください。")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(settings["gemini"]["model_transcribe"])

def transcribe_local_file(path: Path) -> Dict[str, Any]:
    """ローカルmp3をGeminiで文字起こしする。"""
    settings = load_settings()
    ensure_dirs(settings)
    model = _configure_gemini(settings)

    # Geminiへアップロード
    upload = genai.upload_file(path=str(path))
    # 生成
    resp = model.generate_content(
        [PROMPT, upload],
        generation_config=genai.types.GenerationConfig(response_mime_type="application/json")
    )
    # JSON化
    try:
        data = json.loads(resp.text)
    except Exception:
        # モデルがJSON以外を返した場合の簡易フォールバック
        data = {"transcript_text": resp.text, "segments": [], "meta": {"language": "ja"}}

    # ファイル名からメタを補完
    meta = parse_filename_meta(path.name)
    data["file_meta"] = meta
    data["file_meta"]["filename"] = path.name
    data["file_meta"]["processed_at"] = now_str()
    return data

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("使い方: python -m scripts.transcriber data/sample.mp3")
        raise SystemExit(1)
    p = Path(sys.argv[1]).expanduser().resolve()
    out = transcribe_local_file(p)
    print(json.dumps(out, ensure_ascii=False, indent=2))
