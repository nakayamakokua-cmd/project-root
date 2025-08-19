import argparse, os, sys, json, textwrap
from openai import OpenAI

def read(p): 
    with open(p, "r", encoding="utf-8") as f: 
        return f.read()

def build_messages(system_path, context_paths, init_path):
    system = read(system_path)
    # すべての context を 1 本の「system 追補」にまとめる
    ctx_blobs = []
    for p in context_paths:
        if not os.path.exists(p): continue
        name = os.path.basename(p)
        try:
            content = read(p)
        except Exception as e:
            content = f"<<failed to read {name}: {e}>>"
        ctx_blobs.append(f"\n--- [CONTEXT: {name}] ---\n{content}\n")
    context_bundle = "\n".join(ctx_blobs)

    system_full = textwrap.dedent(f"""\
    {system}

    ---
    [CONTEXT BUNDLE - READ ONLY]
    以下は常時参照する設計・辞書・スクリプト・設定です。生成時はこれらと整合して下さい。
    {context_bundle}
    """)

    init_user = read(init_path) if init_path and os.path.exists(init_path) else ""
    msgs = [{"role":"system","content":system_full}]
    if init_user.strip():
        msgs.append({"role":"user","content":init_user})
    return msgs

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--system", required=True)
    ap.add_argument("--context", nargs="*", default=[])
    ap.add_argument("--init", required=False)
    ap.add_argument("--model", default=os.environ.get("CODEX_MODEL","gpt-4o-mini"))
    args = ap.parse_args()

    if not os.environ.get("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY が未設定です。`export OPENAI_API_KEY=...` を実行してください。", file=sys.stderr)
        sys.exit(1)

    client = OpenAI()
    messages = build_messages(args.system, args.context, args.init)

    # init 実行（あれば）
    if len(messages) > 1:
        resp = client.chat.completions.create(
            model=args.model,
            messages=messages,
            temperature=0.2
        )
        print(resp.choices[0].message.content)
        messages.append({"role":"assistant","content":resp.choices[0].message.content})

    # REPL
    print("\n--- Interactive (Ctrl+C で終了) ---")
    try:
        while True:
            user = input("\nYou> ")
            messages.append({"role":"user","content":user})
            resp = client.chat.completions.create(
                model=args.model,
                messages=messages,
                temperature=0.2
            )
            out = resp.choices[0].message.content
            print("\nAI>\n" + out)
            messages.append({"role":"assistant","content":out})
    except (EOFError, KeyboardInterrupt):
        print("\nBye.")
