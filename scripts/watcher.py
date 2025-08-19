from __future__ import annotations
import subprocess, json, time, shutil, datetime
from pathlib import Path

INBOX = Path("Audio/inbox")
PROCESSED = Path("Audio/processed")
ERROR = Path("Audio/error")
CACHE = Path(".cache")
LOGS = Path("logs")
LOG_FILE = LOGS / "watcher.log"

def log(msg: str) -> None:
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}\n"
    LOGS.mkdir(parents=True, exist_ok=True)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line)
    print(line, end="")

def run_with_retry(cmd: list[str], name: str, attempts: int = 3) -> tuple[subprocess.CompletedProcess, int, float]:
    delay = 1.0
    last_err: Exception | None = None
    start = time.time()
    for i in range(1, attempts + 1):
        try:
            log(f"RUN[{name}] attempt {i}: {' '.join(cmd)}")
            ret = subprocess.run(cmd, check=True, capture_output=True, text=True)
            if ret.stdout:
                log(f"OK[{name}] {len(ret.stdout)} bytes stdout")
            dur = time.time() - start
            return ret, i, dur
        except subprocess.CalledProcessError as e:
            last_err = e
            log(f"ERR[{name}] code={e.returncode} stderr={e.stderr.strip() if e.stderr else ''}")
        except Exception as e:
            last_err = e
            log(f"ERR[{name}] {repr(e)}")
        if i < attempts:
            time.sleep(delay)
            delay = min(delay * 2, 8.0)
    assert last_err is not None
    dur = time.time() - start
    # 失敗時も所要時間を返したいが、既存呼び出しは例外を期待しているため投げる
    raise last_err  # type: ignore

def main():
    for p in (INBOX, PROCESSED, ERROR, CACHE, LOGS):
        p.mkdir(parents=True, exist_ok=True)

    audio_files = sorted([p for p in INBOX.glob("*.*") if p.suffix.lower() in (".mp3",".m4a",".wav")])
    if not audio_files:
        log("No new audio files in Audio/inbox")
        return

    for f in audio_files:
        log(f"START processing: {f.name}")
        try:
            # 1) transcribe
            t_ret, t_tries, t_dur = run_with_retry(["python","-m","scripts.transcriber", str(f)], name="transcribe")
            (CACHE/"last_transcript.json").write_text(t_ret.stdout, encoding="utf-8")

            # 2) analyze
            a_ret, a_tries, a_dur = run_with_retry(["python","-m","scripts.analyzer", str(CACHE/"last_transcript.json")], name="analyze")
            (CACHE/"last_row.json").write_text(a_ret.stdout, encoding="utf-8")

            # 3) sheets
            s_ret, s_tries, s_dur = run_with_retry(["python","-m","scripts.sheets_writer", str(CACHE/"last_row.json")], name="sheets")

            # 成功したら移動
            shutil.move(str(f), str(PROCESSED/f.name))
            log(f"DONE: {f.name}")
            # メトリクスを出力（NDJSON）
            metrics = {
                "ts": datetime.datetime.now().isoformat(timespec="seconds"),
                "file": f.name,
                "outcome": "success",
                "timings_sec": {"transcribe": round(t_dur,3), "analyze": round(a_dur,3), "sheets": round(s_dur,3)},
                "attempts": {"transcribe": t_tries, "analyze": a_tries, "sheets": s_tries},
            }
            (LOGS/"metrics.ndjson").parent.mkdir(parents=True, exist_ok=True)
            with (LOGS/"metrics.ndjson").open("a", encoding="utf-8") as mf:
                mf.write(json.dumps(metrics, ensure_ascii=False) + "\n")

        except Exception as e:
            log(f"FAIL: {f.name} -> {repr(e)}")
            # 失敗音源を退避し、理由メモを残す
            dest = ERROR/f.name
            try:
                shutil.move(str(f), str(dest))
            except Exception:
                pass
            (ERROR/f"{f.stem}.err.txt").write_text(repr(e), encoding="utf-8")
            # 失敗メトリクス（どこで落ちたか分からないので所要時間は省略）
            metrics = {
                "ts": datetime.datetime.now().isoformat(timespec="seconds"),
                "file": f.name,
                "outcome": "fail",
                "error": repr(e),
            }
            (LOGS/"metrics.ndjson").parent.mkdir(parents=True, exist_ok=True)
            with (LOGS/"metrics.ndjson").open("a", encoding="utf-8") as mf:
                mf.write(json.dumps(metrics, ensure_ascii=False) + "\n")
            time.sleep(0.5)

if __name__ == "__main__":
    main()
