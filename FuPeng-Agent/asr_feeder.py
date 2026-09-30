"""FuPeng Agent — ASR 喂满器：连续保持 max_slots 个槽忙碌，排空 queued 积压。

设计（确定性核心 + 薄 IO 壳，便于沙箱验证）：
- decide()   纯函数：给定 jobs + max_slots + 依赖(pid_alive/audio_ok/transcript_ok)，
             算出 5 个桶(requeue/mark_done/to_launch/to_skip/still_running)，无副作用。
- one_pass() 应用 decide 结果到 state（走 stateio 锁）+ Popen 起 worker，返回是否排空。
- main()     循环 one_pass 直到排空。

用法: python asr_feeder.py [max_slots]   （默认 2；8GB 硬件上限，勿超 2）
退出码: 0=全部排空, 1=存在 failed
"""
import json, os, sys, time, subprocess, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import stateio

def log(msg):
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def _pid_alive(pid):
    """Windows tasklist 判活（无 pid / 查询失败一律 False）。"""
    if not pid:
        return False
    try:
        out = subprocess.run(["tasklist", "/FO", "CSV", "/NH", "/FI", f"PID eq {pid}"],
                             capture_output=True, text=True, timeout=10).stdout
        return str(pid) in out
    except Exception:
        return False

def _transcript_ok(path):
    return bool(path) and os.path.exists(path) and os.path.getsize(path) > 2000

def _audio_ok(cfg, path):
    return bool(path) and os.path.exists(path) and os.path.getsize(path) > 50000

def decide(jobs, max_slots, pid_alive, audio_ok, transcript_ok):
    """确定性调度决策（纯函数，无副作用）。
    返回 (to_launch, to_skip, requeue, mark_done, still_running)，各桶是 jobs 里的 dict 引用。
      - running + pid 活        -> still_running（占槽）
      - running + pid 死 + 有转录 -> mark_done（worker 写完转录即崩）
      - running + pid 死 + 无转录 -> requeue（回队列重跑）
      - queued 前 open_slots 条: 有音频 -> to_launch，无音频 -> to_skip
    """
    still_running, requeue, mark_done = [], [], []
    for m in jobs:
        if m.get("status") != "running":
            continue
        if pid_alive(m.get("pid")):
            still_running.append(m)
        elif transcript_ok(m.get("transcript")):
            mark_done.append(m)
        else:
            requeue.append(m)
    open_slots = max(0, max_slots - len(still_running))
    queued = [m for m in jobs if m.get("status") == "queued"]
    to_launch, to_skip = [], []
    for q in queued[:open_slots]:
        (to_launch if audio_ok(q.get("audio")) else to_skip).append(q)
    return to_launch, to_skip, requeue, mark_done, still_running

def _launch(cfg, job):
    """Popen 起 asr_worker（start_new_session 独立存活），返回 pid。"""
    key = job["key"]
    out = job.get("transcript") or os.path.join(HERE, cfg["transcript_dir"], key.replace(":", "_") + ".txt")
    wmeta = dict(job); wmeta["transcript"] = out; wmeta["status"] = "running"
    p = subprocess.Popen([cfg["venv_python"], os.path.join(HERE, "asr_worker.py"),
                         json.dumps(wmeta, ensure_ascii=False)],
                        start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return p.pid

def one_pass(cfg, max_slots, pid_alive, audio_ok, transcript_ok, launch, load_state, atomic_update):
    """跑一轮：读 state -> decide -> 锁内改 status -> 起 worker -> 返回 (should_stop, stats)。
    全部依赖可注入（默认用真实 stateio/subprocess），便于沙箱确定性测试。"""
    jobs = load_state()["asr_jobs"]
    to_launch, to_skip, requeue, mark_done, _still = decide(jobs, max_slots, pid_alive, audio_ok, transcript_ok)

    def _mutate(d):
        jm = {m["key"]: m for m in d["asr_jobs"]}
        for m in requeue:
            jm[m["key"]]["status"] = "queued"
        for m in mark_done:
            jm[m["key"]]["status"] = "done"
        for m in to_skip:
            jm[m["key"]]["status"] = "failed"
        for m in to_launch:
            jm[m["key"]]["status"] = "running"
    if requeue or mark_done or to_skip or to_launch:
        atomic_update(_mutate)

    pids = {}
    for m in to_launch:
        pids[m["key"]] = launch(cfg, m)
    if pids:
        def _setpids(d):
            jm = {m["key"]: m for m in d["asr_jobs"]}
            for k, pid in pids.items():
                jm[k]["pid"] = pid
        atomic_update(_setpids)

    s2 = load_state()["asr_jobs"]
    c = lambda st: sum(1 for m in s2 if m.get("status") == st)
    stats = {"launched": len(to_launch), "requeued": len(requeue), "skipped": len(to_skip),
             "running": c("running"), "queued": c("queued"), "done": c("done"), "failed": c("failed")}
    return not stats["queued"] and not stats["running"], stats

def main():
    max_slots = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    cfg = json.load(open(os.path.join(HERE, "config.json"), encoding="utf-8"))
    audio_ok = lambda path: _audio_ok(cfg, path)
    idle_poll = 15
    while True:
        stop, st = one_pass(cfg, max_slots, _pid_alive, audio_ok, _transcript_ok,
                            _launch, stateio.load_state, stateio.atomic_update)
        if stop:
            log(f"排空完成：done={st['done']} failed={st['failed']}（末轮 launched={st['launched']}）")
            sys.exit(1 if st["failed"] else 0)
        log(f"launched={st['launched']} requeued={st['requeued']} | running={st['running']} "
            f"queued={st['queued']} done={st['done']} failed={st['failed']}")
        time.sleep(idle_poll)

if __name__ == "__main__":
    main()
