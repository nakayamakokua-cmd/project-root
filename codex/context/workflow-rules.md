# Git運用ルール・作業規約

本ファイルは project-root リポジトリの運用ルールを定義する。
CodexCLIは必ずこのルールに従って作業すること。

## 1. ブランチ運用

### 基本原則
- **main ブランチ**: 本番環境（正式版）。直接のpushは禁止
- **feature/* ブランチ**: すべての作業用。必ずここで作業する

### ブランチ命名規則
```bash
# タスクベースの命名（推奨）
feature/gemini-integration    # Gemini統合
feature/fix-timeout           # タイムアウト修正  
feature/update-dictionary     # 辞書更新
feature/improve-performance   # パフォーマンス改善

# 日付ベースの命名（複数の小タスクをまとめる場合のみ）
feature/work-20250819         # 複数の細かい修正
```

### ブランチ作成ルール
- 新規タスク開始時: 新しいfeatureブランチを作成
- 既存タスク継続時: 同じfeatureブランチで作業を継続
- ブランチ作成コマンド例:
  ```bash
  git checkout -b feature/[タスク名]
  ```

## 2. コミット規約

### コミットメッセージ
- 日本語で記載
- 何をしたか明確に記述
- フォーマット: `[カテゴリ] 変更内容`

```bash
# 良い例
git commit -m "[修正] sheets_writer.pyのタイムアウトを40秒に延長"
git commit -m "[追加] Gemini APIの文字起こし機能を実装"
git commit -m "[更新] ng_master.jsonに新しい競合語を追加"

# 悪い例
git commit -m "fix"
git commit -m "update"
```

## 3. PR（プルリクエスト）運用

### PR作成タイミング
- 機能の実装が完了した時
- レビューが必要な時点
- 1日の作業終了時（WIPでも可）

### PRタイトル・説明
```markdown
# タイトル例
[feature/gemini-integration] Gemini文字起こし機能の実装

# 説明テンプレート
## 実装内容
- Gemini APIとの接続処理を追加
- エラーハンドリングを強化
- リトライ機構を実装

## 変更ファイル
- scripts/transcriber.py: Gemini連携追加
- config/settings.json: API設定追加
- docs/音源分析_基本設計_MVP.md: 仕様追記

## テスト結果
- ローカルテスト: ✅ 成功
- サンプル音声での動作確認: ✅ 完了

## 非エンジニア向け説明
音声の文字起こしに新しいAI（Gemini）を使えるようにしました。
これにより、より正確な文字起こしが可能になります。
```

## 4. 作業フロー

### 日次作業開始時
1. mainブランチの最新を取得
   ```bash
   git checkout main
   git pull origin main
   ```

2. 作業ブランチに切り替え（or 作成）
   ```bash
   # 継続の場合
   git checkout feature/[既存ブランチ名]
   git merge main  # mainの更新を取り込む
   
   # 新規の場合
   git checkout -b feature/[新しいブランチ名]
   ```

3. 作業実施

### 作業終了時
1. 変更をコミット
   ```bash
   git add .
   git commit -m "[カテゴリ] 変更内容"
   ```

2. リモートにpush
   ```bash
   git push origin feature/[ブランチ名]
   ```

3. PRを作成（またはドラフトPRを更新）

4. 進捗を記録
   - `codex/context/_recent_changes.md` に作業内容を追記
   - `docs/CHANGELOG.md` に重要な変更を記録

## 5. セーフティルール

### 禁止事項
- ❌ mainブランチへの直接push
- ❌ --force オプションの使用（履歴の書き換え）
- ❌ マスタファイルの構造変更（ng_master.json, script_master.json）を無断で行う

### 必須確認事項
- ✅ 設計書（docs/音源分析_基本設計_MVP.md）との整合性
- ✅ マスタファイルの構造維持
- ✅ テストの実行と成功
- ✅ エラーハンドリングの実装

## 6. トラブル時の対応

### コンフリクトが発生した場合
```bash
# mainの最新を取り込んでコンフリクトを解消
git checkout main
git pull origin main
git checkout feature/[ブランチ名]
git merge main
# コンフリクトを手動で解消
git add .
git commit -m "[解決] mainとのコンフリクトを解消"
```

### 間違えてmainにコミットした場合
```bash
# 直前のコミットを取り消し
git reset --soft HEAD~1
# featureブランチを作成して移動
git checkout -b feature/emergency-fix
git commit -m "[移動] mainから移動した変更"
git push origin feature/emergency-fix
```

### 作業を破棄して最初からやり直す場合
```bash
git checkout main
git branch -D feature/[ブランチ名]  # ローカルブランチ削除
git push origin --delete feature/[ブランチ名]  # リモートブランチ削除
git checkout -b feature/[新しいブランチ名]  # 新規作成
```

## 7. 自動化スクリプト

### セッション開始スクリプト（scripts/start_session.sh）
```bash
#!/bin/bash
echo "📝 前回の作業内容:"
tail -20 codex/context/_recent_changes.md
echo ""
echo "🌿 現在のブランチ:"
git branch --show-current
echo ""
echo "📊 未コミットの変更:"
git status --short
```

### セッション終了スクリプト（scripts/end_session.sh）
```bash
#!/bin/bash
DATE=$(date +'%Y-%m-%d %H:%M')
BRANCH=$(git branch --show-current)
echo "[$DATE] Branch: $BRANCH" >> codex/context/_recent_changes.md
git diff --stat >> codex/context/_recent_changes.md
echo "---" >> codex/context/_recent_changes.md
git add codex/context/_recent_changes.md
git commit -m "[記録] セッション終了時の状態を保存"
```

## 8. CodexCLI用の指示テンプレート

### 最小限の起動指示
```markdown
プロジェクトを継続します。
codex/context/workflow_rules.md のGit運用ルールに従って作業してください。
前回の状態は codex/context/_recent_changes.md を参照。
```

### タスク指定する場合
```markdown
codex/context/workflow_rules.md に従って、
[タスク内容] を実装してください。
適切なfeatureブランチで作業し、完了後PRを作成してください。
```

---

**最終更新**: 2025-08-19
**次回レビュー予定**: 運用開始から1週間後