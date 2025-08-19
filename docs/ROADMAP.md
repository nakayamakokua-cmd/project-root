# ROADMAP

## Current Status
- Sheets書き込み: 設定/認証の後方互換、CSV/NDJSON退避、ヘッダー自動追記
- 解析: マスタ連動（競合語/日程語/優先順）、終話ウィンドウ優先、`phone_flag` 追加
- 監視: リトライ（1/2/4s）、ログ出力、失敗時退避メモ、Make `watch`

## Next
- 可観測性: 失敗統計/実行時間を `logs/` にメトリクス出力

## Doing
- なし（随時更新）

## Done
- Sheets安定化、マスタ連動、監視リトライ/ログ、NDJSON再送、設計ドキュ差分追記
- 文字起こし: Gemini 本接続（API呼出し・指数バックオフ・JSON整形/フォールバック）
- 辞書拡充: `script_master.json` dictionaries（negative/positive/date_terms/schedule_words）を増補

## Decisions
- 正準設定: `settings.sheets.*`（`settings.google.*` はフォールバック）
- 終話優先: 終話ウィンドウ（max 60s, 20% tail）
- 分岐固定: 最初の顧客反応で固定（途中は履歴のみ）
- 失敗退避: `Outputs/csv/append_fallback.(csv|ndjson)`、`Audio/error` に音源退避+理由
