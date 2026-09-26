"""FuPeng Agent — 采集脚本：三平台发现新视频 → 去重 → 下载音频 → 启动后台 ASR。

设计原则：
- 确定性逻辑全在脚本（采集/去重/下载/调度），LLM 只负责后续"蒸馏"判断
- 断点续传：state.json 记录 seen/downloaded/transcribed 全量状态
- ASR 子进程独立存活（双队列上限由 max_concurrent_asr 控制）

用法：
  python collect_and_transcribe.py [--dry-run] [--no-asr]

退出码：0=正常(无论有无新视频)，非0=致命错误
输出（stdout）：人类可读摘要，供 cron 看门狗读取
"""
import json, os, re, subprocess, sys, datetime, platform
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import stateio

LOG = []  # 默认静默(cron)：只缓冲；FP_VERBOSE=1 交互实时打印
def log(msg):
    line = f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}"
    LOG.append(line)
    if os.environ.get("FP_VERBOSE"):  # 交互实时
        print(line, flush=True)

def pid_alive(pid):
    """判断 pid 是否存活（Windows: OpenProcess；POSIX: kill 0）。"""
    if not pid:
        return False
    try:
        if platform.system() == "Windows":
            import ctypes
            k32 = ctypes.WinDLL("kernel32", use_last_error=True)
            h = k32.OpenProcess(0x1000, False, int(pid))  # PROCESS_QUERY_LIMITED_INFORMATION
            if not h:
                return False
            k32.CloseHandle(h)
            return True
        else:
            os.kill(int(pid), 0)
            return True
    except Exception:
        return False

def _hours_since(iso):
    try:
        return (datetime.datetime.now() - datetime.datetime.fromisoformat(iso)).total_seconds() / 3600.0
    except Exception:
        return 9999

def load_cfg():
    with open(os.path.join(HERE, "config.json"), encoding="utf-8") as f:
        return json.load(f)

def run_ytdlp(args, cfg, proxy=False, timeout=300):
    cmd = [cfg["yt_dlp"]] + args
    if proxy:
        cmd += ["--proxy", cfg["proxy"]]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stdout, r.stderr

def discover_youtube(cfg, state):
    """返回 [{key, url, title, platform}]；flat-playlist 发现（不下载）。"""
    f, s = cfg["sources"]["youtube"], []
    for cid in f.get("channel_ids", []):
        rc, out, err = run_ytdlp(["--flat-playlist", "--print", "%(id)s|%(title)s",
                                  f.get("channel_url_tpl", "").format(cid=cid)], cfg, proxy=True, timeout=180)
        if rc != 0:
            log(f"  youtube channel {cid} 拉取失败: {err.strip().splitlines()[-1] if err else '?'}")
            continue
        for line in out.splitlines():
            if "|" not in line:
                continue
            vid, title = line.split("|", 1)
            key = f"youtube:{vid}"
            if key not in state["seen"]:
                s.append({"key": key, "url": f"https://www.youtube.com/watch?v={vid}", "title": title.strip(), "platform": "youtube"})
    for q in f.get("search_queries", []):
        tpl = f.get("search_url_tpl", "").replace("{q}", urllib.parse.quote_plus(q))
        rc, out, err = run_ytdlp(["--flat-playlist", "--print", "%(id)s|%(title)s", tpl], cfg, proxy=True, timeout=180)
        if rc != 0:
            log(f"  youtube search '{q}' 失败: {err.strip().splitlines()[-1] if err else '?'}")
            continue
        for i, line in enumerate(out.splitlines()):
            if i >= int(f.get("search_limit_per_query", 12)) or "|" not in line:
                continue
            vid, title = line.split("|", 1)
            key = f"youtube:{vid}"
            if key not in state["seen"]:
                s.append({"key": key, "url": f"https://www.youtube.com/watch?v={vid}", "title": title.strip(), "platform": "youtube"})
    return s

def discover_bilibili(cfg, state, cookies_file):
    """B站：UP主空间页（yt-dlp）+ 搜索页 HTML 解析（免cookie，拿 BV 号再走 yt-dlp 验证）。"""
    b, found = cfg["sources"]["bilibili"], []
    for uid in b.get("uids", []):
        space = f"https://space.bilibili.com/{uid}/video"
        args = ["--flat-playlist", "--print", "%(id)s|%(title)s", space]
        if os.path.exists(cookies_file):
            args += ["--cookies", cookies_file]
        rc, out, err = run_ytdlp(args, cfg, timeout=120)
        if rc == 0:
            for line in out.splitlines():
                if "|" not in line:
                    continue
                vid, title = line.split("|", 1)
                key = f"bilibili:{vid}"
                if key not in state["seen"]:
                    found.append({"key": key, "url": b.get("video_url_tpl", "").format(bvid=vid), "title": title.strip(), "platform": "bilibili"})
        else:
            log(f"  bilibili space {uid} 拉取失败(412/风控): {err.strip().splitlines()[-1] if err else '?'}")
    # 搜索页兜底（HTML 里藏 BV 号）
    for q in b.get("search_queries", []):
        url = b.get("search_url_tpl", "").replace("{q}", urllib.parse.quote_plus(q))
        try:
            r = subprocess.run(["curl", "-sL", url, "-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0"],
                               capture_output=True, text=True, timeout=45)
            bvids = re.findall(r'"bvid":"(BV[0-9A-Za-z]{10})"', r.stdout)
            seen_bv = set()
            for bv in bvids:
                if bv in seen_bv:
                    continue
                seen_bv.add(bv)
                key = f"bilibili:{bv}"
                if key not in state["seen"] and key not in [x["key"] for x in found]:
                    found.append({"key": key, "url": b.get("video_url_tpl", "").format(bvid=bv), "title": f"(b站搜索:{q})", "platform": "bilibili"})
        except Exception as e:
            log(f"  bilibili search '{q}' 失败: {e}")
    return found

def collect_pending_links(cfg):
    """抖音/手动投喂：pending_links.txt 一行一个链接。"""
    p = os.path.join(HERE, cfg.get("pending_links_file", "pending_links.txt"))
    out = []
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                m = re.search(r'(douyin\.com/[^\s?#]+|v\.douyin\.com/\S+|youtube\.com/watch\?\S+|bilibili\.com/video/\S+)', line)
                ident = m.group(1) if m else line
                key = f"manual:{re.sub(r'[^0-9A-Za-z]', '', ident)[-24:]}"
                out.append({"key": key, "url": ident, "title": line[:80], "platform": "manual", "line_no": i})
        # 读后标记已处理（避免重复投喂）
        with open(p, "a", encoding="utf-8") as f:
            f.write(f"\n# processed at {datetime.datetime.now().isoformat()}\n")
    return out

def discover_douyin(cfg, state, dry_run=False):
    """抖音：自动发现付鹏最新短视频，自动刷新 cookie，不再依赖人工投喂。

    1) 自动 cookie 刷新：douyin_cookie_refresh.refresh_cookies()（Playwright，匿名 ttwid/s_v_web_id）
    2) 发现：优先创作者主页（sec_uid）；风控/验证码时记录日志并返回空，不阻塞管线
    pending_links.txt 降级为兜底（留给人工/第三方链接）
    提示：抖音对匿名访问风控较严，若 yt-dlp 下载仍报 "Fresh cookies"，
    把一份登录态 cookie（含 sessionid）导出到 cookies/douyin_cookies.txt 即可解锁下载。
    """
    d = cfg["sources"].get("douyin", {})
    found = []
    sec = d.get("sec_uid", "")
    try:
        import douyin_cookie_refresh as dcr
    except Exception as e:
        log(f"  douyin_cookie_refresh 导入失败: {e}")
        return found
    # 1) 自动刷新 cookie（浏览器，dry-run 跳过以省时）
    if not dry_run and d.get("auto_cookie_refresh", True):
        try:
            dcr.refresh_cookies()
        except Exception as e:
            log(f"  抖音 cookie 自动刷新失败(沿用现有文件): {e}")
    # 2) 发现新视频
    try:
        limit = int(d.get("limit", 15))
        items = []
        if sec:
            items = dcr.discover(creator_only=True, sec_uid=sec, limit=limit)
        if not items:
            for q in d.get("search_queries", ["付鹏"]):
                items += dcr.discover(q, limit=8)
        for it in items:
            m = re.search(r"/video/(\d+)", it.get("url", ""))
            if not m:
                continue
            vid = m.group(1)
            key = f"douyin:{vid}"
            if key not in state["seen"] and key not in [x["key"] for x in found]:
                found.append({"key": key, "url": it["url"], "title": it.get("title", "") or "(抖音短视频)", "platform": "douyin"})
    except Exception as e:
        log(f"  抖音发现异常(风控/验证码/无网络，不阻塞管线): {e}")
    return found


def download(cfg, item, dry_run=False):
    """下载 bestaudio → audio/<key>.webm，返回本地路径或 None。"""
    key = item["key"]
    local = os.path.join(HERE, cfg["audio_dir"], key.replace(":", "_") + ".webm")
    if os.path.exists(local) and os.path.getsize(local) > 50000:
        log(f"  [cache] {key} 已有音频 {os.path.getsize(local)//1024//1024}MB")
        return local
    if dry_run:
        log(f"  [dry-run] 将下载 {key} <- {item['url']}")
        return local
    args = ["-f", "bestaudio[ext=webm]/bestaudio", "--merge-output-format", "webm",
            "--max-filesize", "200M", "-o", local, "--no-playlist", item["url"]]
    proxy = ("youtube" in item.get("url", "")) or item["platform"] == "youtube"
    bcookies = cfg["sources"]["bilibili"].get("cookie_file")
    if item["platform"] == "bilibili" and os.path.exists(os.path.join(HERE, bcookies)):
        args += ["--cookies", os.path.join(HERE, bcookies)]
    dc = cfg["sources"]["douyin"].get("cookie_file")
    if ("douyin" in item.get("url", "") or item["platform"] == "douyin") and os.path.exists(os.path.join(HERE, dc)):
        args += ["--cookies", os.path.join(HERE, dc)]
    rc, out, err = run_ytdlp(args, cfg, proxy=proxy, timeout=900)
    if rc != 0:
        log(f"  [FAIL] 下载 {key}: {err.strip().splitlines()[-1] if err else '?'}")
        return None
    log(f"  [OK] 下载 {key} -> {os.path.basename(local)} ({os.path.getsize(local)//1024//1024}MB)")
    return local

def start_asr(cfg, item, local, dry_run=False):
    """启动 asr_worker.py 子进程（start_new_session=True 独立存活），登记到 state.asr_jobs。"""
    out = os.path.join(HERE, cfg["transcript_dir"], item["key"].replace(":", "_") + ".txt")
    meta = {"key": item["key"], "title": item.get("title", ""), "platform": item["platform"],
            "url": item["url"], "audio": local, "transcript": out, "status": "running",
            "started": datetime.datetime.now().isoformat()}
    if dry_run:
        meta["status"] = "skipped(dry-run)"
        log(f"  [dry-run] ASR {item['key']}")
        return meta
    cmd = [cfg["venv_python"], os.path.join(HERE, "asr_worker.py"), json.dumps(meta, ensure_ascii=False)]
    p = subprocess.Popen(cmd, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    meta["pid"] = p.pid
    log(f"  [ASR] {item['key']} pid={p.pid} -> {os.path.basename(out)}")
    return meta

def main():
    dry_run = "--dry-run" in sys.argv
    no_asr = "--no-asr" in sys.argv
    cfg = load_cfg()
    state = stateio.load_state()          # 快照（锁内读，读后释放）
    os.makedirs(os.path.join(HERE, cfg["audio_dir"]), exist_ok=True)
    os.makedirs(os.path.join(HERE, cfg["transcript_dir"]), exist_ok=True)

    max_run_hours = int(cfg.get("max_run_hours", 48))
    slots = int(cfg.get("max_concurrent_asr", 2))
    now_iso = datetime.datetime.now().isoformat

    # 0) 对账 running（锁外：读磁盘文件 + pid_alive，只计算不落盘）
    reconciled = {}   # key -> {"status","note"}
    for m in state["asr_jobs"]:
        if m.get("status") != "running":
            continue
        tr = m.get("transcript", "")
        tr_ok = bool(tr) and os.path.exists(tr) and os.path.getsize(tr) > 2000
        alive = pid_alive(m.get("pid"))
        age_h = _hours_since(m.get("started", ""))
        if tr_ok and not alive:
            reconciled[m["key"]] = {"status": "done", "note": "reconciled: transcript exists, worker exited"}
            log(f"[reconcile] {m['key']} 转录已存在 -> done")
        elif not alive:
            reconciled[m["key"]] = {"status": "queued", "note": "worker died, requeued"}
            log(f"[reconcile] {m['key']} worker 死 -> queued")
        elif age_h > max_run_hours:
            reconciled[m["key"]] = {"status": "queued", "note": f"stuck running >{max_run_hours}h, requeued"}
            log(f"[reconcile] {m['key']} 卡死超 {max_run_hours}h -> queued")

    # 1) 发现新视频
    new_items = []
    log("发现新视频...")
    try:
        new_items += discover_youtube(cfg, state)
    except Exception as e:
        log(f"youtube 发现异常: {e}")
    try:
        bili_cookies = os.path.join(HERE, cfg["sources"]["bilibili"].get("cookie_file", ""))
        new_items += discover_bilibili(cfg, state, bili_cookies)
    except Exception as e:
        log(f"bilibili 发现异常: {e}")
    try:
        # 抖音自动化：Playwright 自动刷新匿名 cookie + 创作者主页自动发现（无人工投喂）
        # 风控/验证码/无登录态时返回 0 条并记录日志，不阻塞管线
        dy_items = discover_douyin(cfg, state, dry_run=dry_run)
        new_items += dy_items
        log(f"douyin 自动发现 {len(dy_items)} 条（风控触发时为 0，属正常降级）")
    except Exception as e:
        log(f"douyin 发现异常: {e}")
    try:
        # pending_links 降级为兜底（第三方链接/登录态解锁前的手工补充）
        new_items += collect_pending_links(cfg)
    except Exception as e:
        log(f"pending_links 异常: {e}")

    active_keys = {m["key"] for m in state["asr_jobs"] if m.get("status") in ("running", "queued")}
    for k in list(active_keys):
        if reconciled.get(k, {}).get("status") == "done":
            active_keys.discard(k)
    todo = [i for i in new_items if i["key"] not in state["seen"] and i["key"] not in active_keys]
    todo = todo[: int(cfg.get("max_new_per_run", 5))]

    running_now = len([m for m in state["asr_jobs"] if m.get("status") == "running"])
    for ch in reconciled.values():
        if ch["status"] != "running":
            running_now -= 1
    queued_jobs = [m for m in state["asr_jobs"] if m.get("status") == "queued"]
    log(f"  发现 {len(new_items)} 新 key；在途 {len(active_keys)}；待接力 {len(queued_jobs)}")

    new_jobs, relayed, seen_add = [], [], {}
    started_new = started_queued = 0

    if not dry_run:
        # 2) 接力 queued（音频已下，Popen 起 worker；锁外）
        for q in queued_jobs:
            if running_now >= slots:
                break
            aud = q.get("audio", "")
            if not (os.path.exists(aud) and os.path.getsize(aud) > 50000):
                continue
            out = q.get("transcript") or os.path.join(HERE, cfg["transcript_dir"], q["key"].replace(":", "_") + ".txt")
            wmeta = dict(q); wmeta["transcript"] = out
            cmd = [cfg["venv_python"], os.path.join(HERE, "asr_worker.py"), json.dumps(wmeta, ensure_ascii=False)]
            p = subprocess.Popen(cmd, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            relayed.append({"key": q["key"], "status": "running", "pid": p.pid, "started": now_iso(), "transcript": out, "note": "relayed"})
            running_now += 1; started_queued += 1
            log(f"[relay] {q['key']} 接力 pid={p.pid}")

        # 3) 下载新 + 起 worker（锁外耗时）
        for i in todo:
            log(f"处理 {i['key']} [{i['platform']}] {i.get('title','')[:50]}")
            local = download(cfg, i, dry_run=False)
            if not local:
                continue
            seen_add[i["key"]] = {"first_seen": now_iso(), "title": i.get("title", ""), "platform": i["platform"]}
            started_new += 1
            if no_asr:
                new_jobs.append({"key": i["key"], "title": i.get("title", ""), "url": i["url"], "audio": local,
                                 "status": "queued", "transcript": os.path.join(HERE, cfg["transcript_dir"], i["key"].replace(":", "_") + ".txt"),
                                 "started": now_iso()})
                continue
            if running_now < slots:
                meta = start_asr(cfg, i, local, dry_run=False)
                new_jobs.append(meta)
                running_now += 1
            else:
                log(f"  [queue] 槽满 {i['key']} 入队")
                new_jobs.append({"key": i["key"], "title": i.get("title", ""), "url": i["url"], "audio": local,
                                 "status": "queued", "transcript": os.path.join(HERE, cfg["transcript_dir"], i["key"].replace(":", "_") + ".txt"),
                                 "started": now_iso()})

        # 4) 一次锁内原子应用（基于磁盘 data，保留 worker 并发修改）
        def apply(d):
            jobs = d["asr_jobs"]
            for m in jobs:                      # 4a 对账
                ch = reconciled.get(m["key"])
                if ch:
                    m["status"] = ch["status"]; m["note"] = ch["note"]; m["finished"] = now_iso()
            for m in jobs:                      # 4b relay
                r = next((x for x in relayed if x["key"] == m["key"]), None)
                if r:
                    m.update({k: v for k, v in r.items() if k != "key"})
            for j in new_jobs:                  # 4c 新 job
                if not any(x["key"] == j["key"] for x in jobs):
                    jobs.append(j)
            for k, v in seen_add.items():       # 4d seen
                d["seen"].setdefault(k, v)
        stateio.atomic_update(apply)

    done = [m for m in stateio.load_state()["asr_jobs"] if m.get("status") == "done"]
    activity = started_new > 0 or started_queued > 0
    err_lines = [l for l in LOG if ("FAIL" in l or "失败" in l or "异常" in l)]
    log(f"完成: 新 {started_new} | 接力 {started_queued} | 在途 {running_now} | 已转录 {len(done)}")
    if not activity:
        log("无新动态，本批次结束。")
    # 默认静默(cron)：仅有新动态或报错才输出；否则 stdout 空 → 不推送
    if activity or err_lines:
        for l in LOG:
            print(l)
        if activity:
            print(f"\n### 本批: 新 {started_new} | 接力 {started_queued} | 在途 {running_now} | 已转录 {len(done)}")

if __name__ == "__main__":
    main()
