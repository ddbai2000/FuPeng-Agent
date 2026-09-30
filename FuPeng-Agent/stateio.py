"""FuPeng Agent — 共享状态 IO：跨平台文件锁 + 原子 读-改-写。

collect_and_transcribe.py 与 asr_worker.py 并发写 state.json 时必须走这里。

锁模型（sidecar lock）：
- 锁 state.json.lock（独立 1 字节侧车文件），而非 state.json 本身。
  Windows msvcrt.locking 基于"第 N 字节"，若锁在会被 truncate 的文件上，
  解锁时该字节可能已超出文件长度 → PermissionError。用 sidecar 彻底规避。
- load_state()    只读快照：不加锁（安全读取；真正变更在 atomic_update 锁内
                  基于磁盘最新状态重读，保证不丢并发修改）。
- atomic_update(f) 读-改-写：锁 sidecar；read-modify-write 全程持锁。
"""
import json, os, time

HERE = os.path.dirname(os.path.abspath(__file__))
STATE_PATH = os.path.join(HERE, "state.json")
LOCK_PATH = STATE_PATH + ".lock"

try:
    import msvcrt
    def _lock(fh): msvcrt.locking(fh.fileno(), msvcrt.LK_LOCK, 1)
    def _unlock(fh): msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
    _FLAVOR = "msvrt"
except ImportError:
    import fcntl
    def _lock(fh): fcntl.flock(fh, fcntl.LOCK_EX)
    def _unlock(fh): fcntl.flock(fh, fcntl.LOCK_UN)
    _FLAVOR = "fcntl"

DEFAULT = {"seen": {}, "asr_jobs": [], "distilled": {}}

def _norm(data):
    data.setdefault("seen", {}); data.setdefault("asr_jobs", []); data.setdefault("distilled", {})
    return data

def _open_lock():
    # sidecar 必须 ≥1 字节才能被 msvcrt.locking 锁住；用 r+b 保证可锁
    if not os.path.exists(LOCK_PATH) or os.path.getsize(LOCK_PATH) < 1:
        with open(LOCK_PATH, "wb") as g:
            g.write(b"\0")
    return open(LOCK_PATH, "r+b")

def load_state():
    """只读快照。文件不存在/损坏返回 default。"""
    if not os.path.exists(STATE_PATH):
        return _norm(json.loads(json.dumps(DEFAULT)))
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            return _norm(json.load(f))
    except Exception:
        return _norm(json.loads(json.dumps(DEFAULT)))

def load_cfg():
    """config.json（公开占位）+ config.local.json（本地 git-ignored 真实路径）合并，overlay 优先。"""
    with open(os.path.join(HERE, "config.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    lp = os.path.join(HERE, "config.local.json")
    if os.path.exists(lp):
        with open(lp, encoding="utf-8") as f:
            cfg.update(json.load(f))
    return cfg

def atomic_update(mutate_fn):
    """锁内 读-改-写。mutate_fn(d)->None 原地改 d（基于磁盘最新状态）。"""
    lh = _open_lock()
    _lock(lh)  # 阻塞直到拿到锁
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            try:
                data = json.load(f)
            except Exception:
                data = json.loads(json.dumps(DEFAULT))
        data = _norm(data)
        mutate_fn(data)
        tmp = STATE_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, STATE_PATH)  # 原子替换
    finally:
        _unlock(lh)
        lh.close()
    return data
