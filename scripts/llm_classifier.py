from __future__ import annotations
import os, sys, json
from typing import Any, Dict
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from scripts.utils import read_json, load_settings


class ClassifyError(Exception):
    pass


def build_schema_prompt(ng_master: Dict[str, Any]) -> str:
    cats = ng_master.get("categories", [])
    lines = ["あなたはコールログの分類器です。以下の制約でJSONのみを返してください。",
             "- 返答は application/json（コードブロックなし）",
             "- 日本語名は指定の候補から選ぶ（表記揺れ禁止）",
             "- スキーマ: { ng_major, ng_minor, ng_reason_chain, branch_kind }",
             "- ng_reason_chain は中分類名を時系列出現順でカンマ連結",
             "- branch_kind は #3-1/#3-2/#3-3/#3-4/MEDAPANI のいずれか"]
    lines.append("\n【大分類/中分類 候補】")
    for c in cats:
        mj = c.get("name_jp")
        minors = ", ".join(m.get("name_jp") for m in c.get("minors", []))
        lines.append(f"- {mj}: {minors}")
    return "\n".join(lines)


def read_text_from_segments(segs: list[dict]) -> str:
    # 簡易で、話者と発話を1行テキストに
    out = []
    for s in segs:
        sp = str(s.get("speaker",""))[:3]
        tx = str(s.get("text",""))
        out.append(f"{sp}: {tx}")
    return "\n".join(out)


def gemini_call(model_name: str, api_key: str, system_prompt: str, transcript: Dict[str, Any]) -> Dict[str, Any]:
    try:
        import google.generativeai as genai
    except Exception as e:
        raise ClassifyError(f"google-generativeai import failed: {e}")

    genai.configure(api_key=api_key)
    generation_config = {
        "response_mime_type": "application/json",
        "temperature": 0.2,
    }
    model = genai.GenerativeModel(model_name, generation_config=generation_config, system_instruction=system_prompt)
    content = {
        "role": "user",
        "parts": [
            {"text": "以下の会話ログを分類してください。"},
            {"text": read_text_from_segments(transcript.get("segments", []))}
        ],
    }
    resp = model.generate_content(content)
    text = getattr(resp, "text", None) or ""
    try:
        data = json.loads(text)
    except Exception:
        # バリアント回復
        data = None
        for cand in getattr(resp, "candidates", []) or []:
            for part in getattr(cand, "content", {}).parts or []:
                t = getattr(part, "text", None)
                if not t:
                    continue
                try:
                    data = json.loads(t)
                    break
                except Exception:
                    continue
            if data:
                break
    if not data:
        raise ClassifyError("failed to parse JSON from Gemini response")
    return data


@retry(reraise=True, stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=1, max=8),
       retry=retry_if_exception_type((ClassifyError, Exception)))
def classify(transcript: Dict[str, Any], settings: dict) -> Dict[str, Any]:
    ng_master = read_json(settings["masters"]["ng_master_path"]) if settings.get("masters") else {}
    gem = settings.get("gemini", {})
    api_key = os.environ.get(gem.get("api_key_env", "GEMINI_API_KEY"))
    if not api_key:
        raise ClassifyError("GEMINI_API_KEY is not set")
    model = gem.get("model_classify", gem.get("model_analyze", "gemini-2.5-pro"))
    sys_prompt = build_schema_prompt(ng_master)
    out = gemini_call(model, api_key, sys_prompt, transcript)
    # 正規化
    result = {
        "ng_major": out.get("ng_major") or "",
        "ng_minor": out.get("ng_minor") or "",
        "ng_reason_chain": out.get("ng_reason_chain") or "",
        "branch_kind": out.get("branch_kind") or "",
        "source": "gemini",
        "model": model,
    }
    return result


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.llm_classifier <transcript.json>")
        sys.exit(1)
    settings = load_settings()
    trans = read_json(sys.argv[1])
    res = classify(trans, settings)
    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

