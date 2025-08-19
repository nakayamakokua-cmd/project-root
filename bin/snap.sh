#!/usr/bin/env bash
set -euo pipefail
TS=$(date +"%Y%m%d-%H%M%S")
OUT="codex/snapshots/${TS}"
mkdir -p "$OUT"

設計・辞書・設定の現行値を保存

cp -a codex/context "$OUT/context"
cp -a codex/prompts "$OUT/prompts"
cp -a config "$OUT/config"

直近の差分を recent_changes に追記

{
echo "## ${TS}"
git status --porcelain || true
} >> codex/context/_recent_changes.md
echo "snapshot: $OUT"
