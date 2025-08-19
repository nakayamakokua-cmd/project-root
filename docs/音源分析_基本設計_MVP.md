# 音源分析 基本設計（拡張MVP版）
本ドキュメントは本リポジトリの実装規約・指標・NG分類・算出ルール・バッチ運用をまとめる。実装と乖離が生じた場合は本書に差分を追記する。

## 不変方針
- 出力列に `ng_major` / `ng_minor` / `ng_reason_chain`（日本語・時系列カンマ区切り）を必ず含む
- 「分岐パターン」は最初の顧客反応で確定（途中遷移は履歴のみ）
- 最終NGは終話ウィンドウ（既定60秒）を優先。該当なし時は確定度で決定
- 解析は ステップA=構造化抽出 → ステップB=根拠抽出/コーチング生成 の2段
- バッチは Mac ローカル完結。失敗は /Audio/error 退避＋ログ保存。429/5xx は指数バックオフ

## Google Sheets 書き込み
- 主要スクリプト: `scripts/sheets_writer.py`
- 必須設定（正準）: `config/settings.json` の `sheets.spreadsheet_id` / `sheets.sheet_name`
- 後方互換: `settings.google` に同キーがある場合はフォールバックで利用（移行期間）
- 認証ファイル探索: `config/credentials.json` → `./credentials.json`。トークンは `config/token.json` → `./token.json`
- 失敗時フォールバック: `Outputs/csv/append_fallback.csv` に追記し、`.cache/last_sheets_error.txt` にエラー保存

## 解析ロジック（マスタ連動）
- NG分類辞書: `config/ng_master.json` の `categories`/`competitors`/`priority_order` を参照
  - `competitors`: 競合語の検出に使用（例: Billone, TOKIUM など）
  - `priority_order`: 同時刻・同確度時のカテゴリ優先度に使用
- 分岐検出: `config/script_master.json` の `dictionaries` を参照
  - `date_terms`/`schedule_words`: 「日程」語の検出（MEDAPANI 判定）
  - `negative`: 「未検討/予定なし」等の検出強化（#3-3 判定）
  - 既存ヒューリスティクス（忙しい/予定不明 等）と併用
  - タイブレーク: 同一時刻・同一カテゴリで複数の中分類が該当する場合、スコア同点時は「タイミング・時期要因」で「繁忙期で不可」を優先（軽微なヒューリスティクス）

## ステップB（コーチング: E1〜E4 + G）
- 目的: スクリプト適合度の簡易スコアを算出し、改善の糸口を提示
- 参照: `config/script_master.json`
  - `branches["#3-1"].E`: E1〜E4 の定義（意味ラベル）
  - `coaching.patterns`: E1〜E4/G の検出語彙（正規表現OR）
  - `scoring.script_fit`: `element_weight`（E1〜E4各）/`goal_weight`（G）/`pass_threshold`
- 実装: `scripts/analyzer.py` の `compute_coaching()`
  - OP発話から E1/E2/E3/E4/G を検出（最初の一致を evidence として記録）
  - スコア = `element_weight * (E1..E4の成立数)` + `goal_weight * G`
  - 合否 = `score >= pass_threshold`
  - 出力は `.cache/last_analysis.json` の `coaching` に保存（Sheetsの列は未変更）

## スプレッドシート列
- 既定列: audio_id, date, operator, ng_major, ng_minor, ng_reason_chain, branch_kind, phone_e164, phone_flag, processed_at
- 既存シートのヘッダーに不足列があれば右に自動追記

## バッチ運用（監視・退避・ログ）
- 監視スクリプト: `python -m scripts.watcher` または `make watch`
- 入力/出力ディレクトリ: `Audio/inbox` → 成功で `Audio/processed`、失敗で `Audio/error`
- リトライ: 各ステップ（transcribe/analyze/sheets）最大3回、指数バックオフ（1s/2s/4s）
- ログ: `logs/watcher.log` に実行記録。失敗時は `Audio/error/<stem>.err.txt` に理由保存
- 失敗時のスプレッドシート行は `Outputs/csv/append_fallback.(csv|ndjson)` に退避（後から `make resend-fallback` で再送）

### 自動実行モード（ポーリング）
- 開始: `make auto-start`（既定ポーリング間隔 30秒。`POLL_INTERVAL=15 make auto-start` で変更可）
- 停止: `make auto-stop`（内部的に `.cache/auto_runner.stop` で停止を指示）
- 状態: `make auto-status`
- ログ: `logs/auto_runner.log`（起動/停止/実行/エラー）
 - メトリクス: `logs/metrics.ndjson` に各音源ごとの所要時間（transcribe/analyze/sheets）と試行回数を1行JSONで追記

## 文字起こし（Gemini スケルトン）
- 設定: `config/settings.json` の `gemini` セクション（`api_key_env`, `model_transcribe`）
- 使用条件: 環境変数 `${api_key_env}` が存在する場合に Gemini 経路を選択（現状は安全のためダミー同等の出力）
- 将来方針: 429/5xx 時の指数バックオフと話者分離/タイムスタンプ取得を実装予定。出力形式は `scripts/transcriber.py` の現在仕様を維持

## 利用者向けガイド
- 非エンジニア向けの実行手順は `docs/クイックガイド_非エンジニア向け.md` を参照

## 差分履歴
- 2025-08-18: Sheets設定/認証の後方互換（`sheets`→`google` フォールバック、`config/…`と`./…`の両対応）を追加。過去の KeyError 再発防止。
- 2025-08-18: analyzer をマスタ連動化（ng_master の競合語/優先順、script_master の日程語/未検討語を取り込み）。分岐判定とNG候補抽出の精度向上。
- 2025-08-18: ステップB（E1〜E4/G）のスコアリングを追加。`script_master.json` に `coaching.patterns` を新設し、`compute_coaching()` を実装。
- 2025-08-18: watcher にリトライ/ログ/退避メモを追加、transcriber を Gemini 対応スケルトン化、Makefile に `watch` を追加。
- 2025-08-19: transcriber を Gemini 本接続。`google-generativeai` 経由でAPI呼出し、`response_mime_type=application/json` を指定。429/5xxは指数バックオフ（1/2/4/… 最大5回）で再試行し、最終失敗時はダミーにフォールバック。出力スキーマ（transcript_text/segments/meta）は維持。
 - 2025-08-19: `config/script_master.json` の dictionaries を増補（positive/negative/date_terms/schedule_words）。analyzer の辞書連動は既存仕様のまま（DATE_TERMS結合→日程ヒント、negative→未検討/不要の判定補強）。
 - 2025-08-19: watcher に観測メトリクスを追加（所要時間/試行回数）。`logs/metrics.ndjson` にNDJSON形式で出力。
## 評価（ローカル）
- アナライザ評価: `python -m scripts.eval_analyzer` または `make eval-analyzer`
  - フィクスチャ: `data/fixtures/analyzer/*.json`
  - 出力: 合否サマリと `logs/eval_analyzer_report.json`
 - 2025-08-19: analyzer 微調整—「検討していません」などの否定表現を即NG（過去検討済み・不要結論）にもマッピング、タイミング系の同点時に「繁忙期で不可」を優先。評価用スクリプト/フィクスチャを追加。
