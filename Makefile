SHELL := /bin/bash

run-all:
	@set -e; \
	echo "== Transcribe =="; \
	python -m scripts.transcriber data/sample.mp3 > .cache/last_transcript.json; \
	echo "== Analyze =="; \
	python -m scripts.analyzer .cache/last_transcript.json > .cache/last_row.json; \
	echo "== Sheets append (fallback NDJSON) =="; \
	python -m scripts.sheets_writer .cache/last_row.json || (echo "Sheets timeout -> fallback"; cat .cache/last_row.json >> Outputs/csv/append_fallback.ndjson)

eval-analyzer:
	@echo "== Evaluating analyzer with fixtures =="; \
	python -m scripts.eval_analyzer

resend-fallback:
	@set -e; \
	[ -f Outputs/csv/append_fallback.ndjson ] || (echo "no fallback"; exit 0); \
	while read -r line; do \
	  echo "$$line" > .cache/one_row.json; \
	  python -m scripts.sheets_writer .cache/one_row.json || { echo "still failing"; exit 1; }; \
	done < Outputs/csv/append_fallback.ndjson; \
	rm -f Outputs/csv/append_fallback.ndjson

watch:
	@python -m scripts.watcher

# ----------------------
# Auto-runner (loop)
# ----------------------
auto-start:
	@mkdir -p .cache logs; \
	if [ -f .cache/auto_runner.pid ] && kill -0 $$(cat .cache/auto_runner.pid) 2>/dev/null; then \
	  echo "auto-runner already running with PID $$(cat .cache/auto_runner.pid)"; \
	else \
	  echo "starting auto-runner..."; \
	  nohup python -m scripts.auto_runner >> logs/auto_runner.log 2>&1 & echo $$! > .cache/auto_runner.pid; \
	  echo "started with PID $$(cat .cache/auto_runner.pid)"; \
	fi

auto-stop:
	@touch .cache/auto_runner.stop; \
	if [ -f .cache/auto_runner.pid ]; then \
	  pid=$$(cat .cache/auto_runner.pid); \
	  if kill -0 $$pid 2>/dev/null; then \
	    echo "stopping $$pid ..."; \
	    kill $$pid || true; \
	  fi; \
	else \
	  echo "no pid file"; \
	fi

auto-status:
	@if [ -f .cache/auto_runner.pid ] && kill -0 $$(cat .cache/auto_runner.pid) 2>/dev/null; then \
	  echo "auto-runner is running (PID $$(cat .cache/auto_runner.pid))"; \
	else \
	  echo "auto-runner is not running"; \
	fi
