# CHANGELOG

## 2025-08-19
- [B-002] Gemini本接続: `scripts/transcriber.py` にAPI呼出しを実装。`google-generativeai` を用い、`response_mime_type=application/json` でJSONを取得。429/5xxを指数バックオフ（max5回）で再試行し、失敗時はダミーへフォールバック。
- [B-003] 辞書拡充: `config/script_master.json` の `positive`/`negative`/`date_terms`/`schedule_words` を増強。analyzer はマスタ連動で自動反映。
- [B-004-early] 可観測性: `scripts/watcher.py` に所要時間/試行回数を `logs/metrics.ndjson` へ記録。
 - [T-ANL] アナライザ精度微調整: 即NGの否定表現（「検討していません」等）を追加、タイミング系で「繁忙期で不可」優先の同点解消ロジック。
- [T-ANL] 評価ハーネス: `scripts/eval_analyzer.py` とフィクスチャ `data/fixtures/analyzer/*.json`、実行は `make eval-analyzer`。
- [T-ANL] データ取り込み: `scripts/import_fixtures.py` と `make import-fixtures CSV=...` でテキストCSVから評価用フィクスチャ生成。
 - [LLM] 分類オプション: `scripts/llm_classifier.py` 追加。`settings.features.llm_classify=true` でGemini分類を有効化（キー/ネット必須）。Analyzerで結果を上書き統合。
