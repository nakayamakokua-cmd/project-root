from __future__ import annotations
import os
import time
import subprocess
from pathlib import Path

INBOX = Path("Audio/inbox")
LOGS = Path("logs")
CACHE = Path(".cache")
PID_FILE = CACHE / "auto_runner.pid"
STOP_FILE = CACHE / "auto_runner.stop"
LOG_FILE = LOGS / "auto_runner.log"

def log(msg: str) -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}\n"
    LOGS.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line)
    print(line, end="")

def has_audio_files() -> bool:
    if not INBOX.exists():
        return False
    return any(p.suffix.lower() in (".mp3",".m4a",".wav") for p in INBOX.glob("*.*"))

def main():
    for p in (INBOX, LOGS, CACHE):
        p.mkdir(parents=True, exist_ok=True)
    # 記録用PID
    try:
        PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
    except Exception:
        pass

    interval_env = os.environ.get("POLL_INTERVAL", "30")
    try:
        interval = max(5, int(interval_env))
    except Exception:
        interval = 30

    log(f"auto_runner started (interval={interval}s)")
    backoff = 5

    try:
        while True:
            if STOP_FILE.exists():
                log("stop file detected; exiting")
                STOP_FILE.unlink(missing_ok=True)
                break

            if has_audio_files():
                log("found audio files; running watcher")
                try:
                    ret = subprocess.run(["python","-m","scripts.watcher"], check=True, capture_output=True, text=True)
                    if ret.stdout:
                        log(f"watcher stdout: {ret.stdout.strip()[:4000]}")
                    if ret.stderr:
                        log(f"watcher stderr: {ret.stderr.strip()[:4000]}")
                    backoff = 5  # reset backoff after success
                except subprocess.CalledProcessError as e:
                    log(f"watcher failed: code={e.returncode} err={e.stderr.strip() if e.stderr else ''}")
                    time.sleep(backoff)
                    backoff = min(backoff * 2, 60)
            else:
                time.sleep(interval)
    finally:
        try:
            PID_FILE.unlink(missing_ok=True)
        except Exception:
            pass
        log("auto_runner stopped")

if __name__ == "__main__":
    main()

