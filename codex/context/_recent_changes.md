# 最近の変更履歴

### 2025-08-19 初期設定
- Git運用ルールを整備
- workflow_rules.md を作成

---

### 2025-08-19 B-002/B-003 対応
- transcriber: Gemini API 本接続（指数バックオフ、JSON整形、キー未設定/失敗時のダミー）
- 辞書拡充: script_master.dictionaries（positive/negative/date_terms/schedule_words）を増補
- ROADMAP/BACKLOG/設計ドキュ/CHANGELOG を同期更新

次回TODO（提案）
- 可観測性: 監視ログへ所要時間/失敗統計を出力、日次集計下準備
- transcriber: 話者推定の精度向上（OP/CUSヒューリスティクス強化）
- analyzer: E/G の evidence をCSVにも要約列として追加するか検討

### 2025-08-19 アナライザ評価/微調整
- 評価ハーネス: `scripts/eval_analyzer.py` と `data/fixtures/analyzer/*.json` を追加（`make eval-analyzer`）
- 微調整: 「検討していません」等を即NG（過去検討済み・不要結論）に追加。タイミング系の同点を「繁忙期で不可」優先で解消。
