"""FuPeng Agent — ASR 子进程 worker（start_new_session 独立存活）。

由 collect_and_transcribe.py 以 Popen(start_new_session=True) 启动。
用法: python asr_worker.py <meta_json>
  meta: {key,title,platform,url,audio,transcript,status,...}

职责：
- 调 H:\\Agent\\ft-distill\\transcribe.py (faster-whisper small int8 cpu, 6线程)
- 完成后把 state.json 里该 job status: running -> done（带文件锁，防 collect 并发写）
- 失败 -> status: failed（保留可重试）
"""
import json, os, sys, subprocess, time, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import stateio

def main():
    meta = json.loads(sys.argv[1])
    cfg = json.load(open(os.path.join(HERE, "config.json"), encoding="utf-8"))
    audio = meta["audio"]
    out = meta["transcript"]

    if not os.path.exists(audio):
        finish(meta, "failed", f"audio not found: {audio}")
        return 1
    # 已有完整转录则直接标记
    if os.path.exists(out) and os.path.getsize(out) > 2000:
        finish(meta, "done", "transcript already exists")
        return 0

    cmd = [cfg["venv_python"], cfg["asr_script"],
           cfg.get("whisper_model", "small"), audio, out,
           str(cfg.get("whisper_threads", 6))]
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV")}
    env["PYTHONPATH"] = ""  # 清空，避免污染 venv
    logpath = out + ".log"
    with open(logpath, "w", encoding="utf-8") as log:
        log.write(f"started {datetime.datetime.now().isoformat()} key={meta['key']}\n")
        log.flush()
        r = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, env=env, timeout=21600)
    ok = r.returncode == 0 and os.path.exists(out) and os.path.getsize(out) > 2000
    finish(meta, "done" if ok else "failed", f"exit={r.returncode}")
    return 0 if ok else 1

def finish(meta, status, note):
    """通过 stateio.atomic_update 统一锁改状态（与 collect 互斥）。"""
    def _mutate(d):
        for m in d.get("asr_jobs", []):
            if m.get("key") == meta["key"]:
                m["status"] = status
                m["finished"] = datetime.datetime.now().isoformat()
                m["note"] = note
                m.setdefault("transcript", meta["transcript"])
    try:
        stateio.atomic_update(_mutate)
    except Exception as e:
        print(f"state write failed: {e}", file=sys.stderr)

if __name__ == "__main__":
    sys.exit(main())
