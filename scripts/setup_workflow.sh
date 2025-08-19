#!/bin/bash

echo "🚀 Git運用環境をセットアップします..."

# 1. ディレクトリ作成
mkdir -p codex/context

# 2. workflow_rules.mdを作成
echo "📝 workflow_rules.mdを作成します..."
cat > codex/context/workflow_rules.md << 'EOF'
# Git運用ルール

## ブランチルール
- mainブランチには直接pushしない
- 必ずfeature/ブランチで作業する
- 作業完了後はPRを作成する

## コミットルール
- 日本語で明確に記載
- [カテゴリ] 変更内容 の形式

## 作業フロー
1. feature/ブランチで作業
2. コミット
3. PR作成
4. マージ
EOF

# 3. 変更履歴ファイルを作成
echo "📋 変更履歴ファイルを作成します..."
cat > codex/context/_recent_changes.md << 'EOF'
# 最近の変更履歴

### 2025-08-19 初期設定
- Git運用ルールを整備
- workflow_rules.md を作成

---
EOF

echo "✅ セットアップ完了！"
echo ""
echo "📚 CodexCLI起動時の指示:"
echo "『プロジェクトを継続します。"
echo " codex/context/workflow_rules.md のGit運用ルールに従って作業してください。』"