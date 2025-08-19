# 実装マップ（設計 → コード）
- Transcribe: scripts/transcriber.py
- Analyze:    scripts/analyzer.py（script_master.json / ng_master.json を参照）
- Sheets:     scripts/sheets_writer.py
- Utils:      scripts/utils.py（ファイル名→電話番号、日付、正規化）
- Watcher:    scripts/watcher.py（将来のDriveトリガ/再試行）
- 設定:       config/settings.json（Geminiモデル、Sheets、Drive）
- マスタ:     config/script_master.json（分岐・E1〜E4・テンプレ）、config/ng_master.json（NG体系）
- ドキュメント: docs/ARCHITECTURE.md（設計）、docs/IMPLEMENTATION_MAP.md（この表）
- Codex文脈: codex/context/*.json / *.md（コード生成時の参照材料）
