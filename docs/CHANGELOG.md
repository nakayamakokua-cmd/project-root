# CHANGELOG

## 2025-08-19
- [B-002] Gemini本接続: `scripts/transcriber.py` にAPI呼出しを実装。`google-generativeai` を用い、`response_mime_type=application/json` でJSONを取得。429/5xxを指数バックオフ（max5回）で再試行し、失敗時はダミーへフォールバック。
- [B-003] 辞書拡充: `config/script_master.json` の `positive`/`negative`/`date_terms`/`schedule_words` を増強。analyzer はマスタ連動で自動反映。

