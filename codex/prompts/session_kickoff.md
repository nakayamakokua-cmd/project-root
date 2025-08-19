目的: 「音源分析 基本設計（拡張MVP版）」に完全準拠し、解析〜スプシ反映までを安定化。
現在の課題:
- Sheets APIでのタイムアウトが散発。CSVフォールバックの追加が必要。
- NG理由: 大分類・中分類は日本語で、発話順にカンマ連結（ng_reason_chain）で出力必須。
- スクリプト更新時は設計文脈も同時更新し、履歴スナップショットを残す。

最初のタスク:
- sheets_writerにCSVフォールバック(Outputs/csv/yyyymmdd.csv)を実装。
- analyzer出力に ng_reason_chain（日本語, 発話順）を確実に含めるリグレッションテスト追加。
- codex/context/_recent_changes.md に変更履歴を自動追記する仕組み（bin/snap.sh）を使う想定でパッチを提示。
