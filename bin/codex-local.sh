#!/usr/bin/env bash
set -euo pipefail

これは "codex" コマンドが無いときの簡易代替ランチャ。
実際のCodexCLI導入後は "codex ..." を使えばOK。
ここでは system + context を連結して、プロンプトをまとめて表示するだけ（手元のエディタやCLIに貼る前段）。

CFG="codex/config.yaml"
SYS=$(yq '.paths.system' "$CFG")
KICK=$(yq '.paths.kickoff' "$CFG")
CTX=$(yq '.paths.context[]' "$CFG")
echo "===== SYSTEM ====="
cat "$SYS"
echo
echo "===== KICKOFF ====="
cat "$KICK"
echo
for c in $CTX; do
echo "===== CONTEXT: $c ====="
cat "$c"
echo
done
echo "（↑このまとめを、お使いのCodexCLI/Chatにそのまま投入してください）"
