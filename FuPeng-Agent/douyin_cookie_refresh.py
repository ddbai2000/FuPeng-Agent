"""抖音匿名 cookie 自动刷新器 —— 无需人工投喂，无需登录。

用系统 Chrome 无头模式访问抖音，让页面 JS 自动种下 ttwid / s_v_web_id / __ac_signature
等 httpOnly + 匿名设备 cookie，导出成 Netscape 格式喂给 yt-dlp。
关键：ttwid 是 httpOnly，浏览器 console 的 document.cookie 读不到；只有 Playwright 的
context.cookies() 才能拿到完整集，这正是 yt-dlp 报 "Fresh cookies needed" 的根因。

用法：
    python douyin_cookie_refresh.py            # 刷新并写 cookies/douyin_cookies.txt
    python douyin_cookie_refresh.py --probe    # 额外自校验：用 yt-dlp 试解析一条视频

cron / collect_and_transcribe.py 每次跑采集前调用一次即可，全程无人值守。
"""
import sys, os, re, json, time, datetime, platform, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(HERE, "config.json"), encoding="utf-8"))
OUT = os.path.join(HERE, "cookies", "douyin_cookies.txt")
YT = CFG["yt_dlp"]

# 系统 Chrome 路径（Windows 常见位置）
CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]


def _chrome_exec():
    for p in CHROME_CANDIDATES:
        if os.path.exists(p):
            return p
    return None


def refresh_cookies(probe_url: str = "https://www.douyin.com/", extra_wait_ms: int = 2500,
                   headless: bool = None) -> list:
    """访问抖音匿名页，返回全部 douyin 域 cookie（含 httpOnly）。

    headless=None 自动选择：有显示环境→headed（防 verify_ 风控），
    无显示/cron 环境→headless。可通过 DY_HEADLESS=1/0 强制。
    """
    if headless is None:
        force = os.environ.get("DY_HEADLESS")
        if force in ("1", "0"):
            headless = force == "1"
        else:
            # Windows 交互桌面环境用 headed 最小化，规避抖音 verify_ 风控；
            # 服务/无显示会话（SYSTEMSESSIONID 非空）回退 headless
            headless = os.environ.get("SYSTEMSESSIONID", "") != ""
    from playwright.sync_api import sync_playwright

    # 优先 channel=chrome（系统Chrome，免下载）；失败则回退 bundled headless
    launch_args = ["--no-sandbox", "--disable-blink-features=AutomationControlled"]
    if headless:
        launch_args.append("--headless=new")
    launched = {"headless": headless}
    cookies = []
    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(channel="chrome", headless=headless, args=launch_args)
        except Exception:
            browser = pw.chromium.launch(headless=headless, args=launch_args)
        if not headless:
            # 最小化窗口，不抢用户焦点
            try:
                ctx0 = browser.new_context(minimize_on_start=True)
                ctx0.close()
            except Exception:
                pass
        ctx = browser.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"),
            locale="zh-CN",
            viewport={"width": 1280, "height": 800},
        )
        # stealth: 去掉 navigator.webdriver
        ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
        page = ctx.new_page()
        page.goto(probe_url, wait_until="domcontentloaded", timeout=45000)
        # 等 cookie 稳定（ttwid 由页面 JS 异步种下）
        page.wait_for_timeout(extra_wait_ms)
        # 再访问一个视频页，逼出 s_v_web_id / __ac_signature 这类反爬标记
        try:
            page.goto("https://www.douyin.com/", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(800)
        except Exception:
            pass
        cookies = ctx.cookies()
        browser.close()

    # 只保留 douyin / iesdouyin 域
    keep = [c for c in cookies if any(d in c.get("domain", "") for d in ("douyin", "iesdouyin", "bytedance"))]
    return keep


def to_netscape(cookies: list) -> str:
    """导出 Netscape 格式。Python http.cookiejar._really_load 的断言：
    flag=TRUE ⟺ 域名以 '.' 开头；flag=FALSE ⟺ 不以 '.' 开头。
    所以域名必须原样照抄（Playwright 给的带点就带点），绝不可强加/去点。
    session cookie 的 expire 写 0。"""
    lines = ["# Netscape HTTP Cookie File (anonymous ttwid/s_v_web_id — 非登录凭证, auto-refreshed)"]
    for c in cookies:
        dom = c.get("domain", "")
        flag = "TRUE" if dom.startswith(".") else "FALSE"
        ex = c.get("expires")
        try:
            ex = int(ex) if (ex is not None and ex > 0) else 0
        except (TypeError, ValueError):
            ex = 0
        secure = "TRUE" if c.get("secure") else "FALSE"
        name, val = c.get("name", ""), c.get("value", "")
        lines.append(f"{dom}\t{flag}\t/\t{secure}\t{ex}\t{name}\t{val}")
    return "\n".join(lines) + "\n"


def discover(query: str = "付鹏", headless: bool = None, limit: int = 15,
             creator_only: bool = False, sec_uid: str = "") -> list:
    """自动发现抖音视频 —— 去掉'人工投喂 pending_links.txt'的核心。

    模式：
      creator_only=False : 抖音搜索页 https://www.douyin.com/search/{q}?type=video
      creator_only=True  : 直接进创作者主页 /user/{sec_uid}，只抓本人视频
    返回 [{'url','title','author'}, ...]，并顺带把本会话 cookie 写回文件。
    """
    from urllib.parse import quote_plus
    if headless is None:
        force = os.environ.get("DY_HEADLESS")
        headless = (force == "1") if force in ("1", "0") else os.environ.get("SYSTEMSESSIONID", "") != ""
    from playwright.sync_api import sync_playwright
    launch_args = ["--no-sandbox", "--disable-blink-features=AutomationControlled"]
    if headless:
        launch_args.append("--headless=new")
    results = []
    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(channel="chrome", headless=headless, args=launch_args)
        except Exception:
            browser = pw.chromium.launch(headless=headless, args=launch_args)
        ctx = browser.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"),
            locale="zh-CN", viewport={"width": 1280, "height": 800},
        )
        ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
        page = ctx.new_page()
        target = (f"https://www.douyin.com/user/{sec_uid}" if creator_only
                  else f"https://www.douyin.com/search/{quote_plus(query)}?type=video")
        try:
            print(f"[douyin-discover] mode={'creator' if creator_only else 'search'} target={target}")
            page.goto(target, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(4000)
            for _ in range(3):  # 滚动触发懒加载
                page.mouse.wheel(0, 3000)
                page.wait_for_timeout(1500)
            # 视频卡片：搜索页 <a href*="/video/">；主页卡片在 [data-e2e="user-post-list"] 内
            cards = page.eval_on_selector_all(
                "a[href*='/video/']",
                """els => els.map(e => {
                      const m = e.href.match(/\\/video\\/(\\d+)/);
                      const t = (e.getAttribute('title') || (e.querySelector('[data-e2e]')||{}).textContent || '').trim();
                      return m ? {id: m[1], href: m.input.split('?')[0], title: t.slice(0,80)} : null;
                    }).filter(Boolean)""")
            seen, urls = set(), []
            for c in cards:
                if c["id"] in seen:
                    continue
                seen.add(c["id"])
                urls.append({"url": c["href"], "title": c["title"], "author": ""})
            results = urls[:limit]
            # 顺带刷新 cookie（本会话比 refresh 流程更新鲜）
            cookies = ctx.cookies()
            keep = [c for c in cookies if any(d in c.get("domain", "") for d in ("douyin", "bytedance"))]
            os.makedirs(os.path.dirname(OUT), exist_ok=True)
            open(OUT, "w", encoding="utf-8").write(to_netscape(keep))
            print(f"[douyin-discover] videos_found={len(urls)} cookie_refreshed={len(keep)}")
            for r in results:
                print(f"  {r['url']} | {r['title'][:40]}")
        except Exception as e:
            print(f"[douyin-discover] ERROR: {e}")
        finally:
            browser.close()
    return results


def main():
    probe = "--probe" in sys.argv
    discover_mode = "--discover" in sys.argv
    if discover_mode:
        from urllib.parse import quote_plus  # noqa: F401
        q = os.environ.get("DY_DISCOVER_QUERY", "付鹏")
        sec = os.environ.get("DY_SEC_UID", "")
        res = discover(q, creator_only=bool(sec), sec_uid=sec)
        for r in res:
            print(r["url"])
        sys.exit(0 if res else 1)
    cookie_url = "https://www.douyin.com/"
    if probe:
        # probe 时直接访问一条真实视频页，逼出最全的 cookie 集
        probe_target = os.environ.get("DY_PROBE_VIDEO", "https://www.douyin.com/")
        cookie_url = probe_target
    cookies = refresh_cookies(probe_url=cookie_url)
    txt = to_netscape(cookies)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(txt)

    have_ttwid = any(c.get("name") == "ttwid" for c in cookies)
    have_svwebid = any(c.get("name") == "s_v_web_id" for c in cookies)
    print(f"[douyin-refresh] cookie_file={OUT}")
    print(f"[douyin-refresh] total={len(cookies)} ttwid={'YES' if have_ttwid else 'NO'} s_v_web_id={'YES' if have_svwebid else 'NO'}")

    if probe:
        _probe_with_ytdlp()


def _probe_with_ytdlp():
    """用刷新出的 cookie 让 yt-dlp 解析一条视频，验证 'Fresh cookies' 是否消失。"""
    probe_video = os.environ.get("DY_PROBE_VIDEO", "https://www.douyin.com/video/7423255598340295971")
    print(f"[douyin-probe] yt-dlp 解析 {probe_video}")
    r = subprocess.run(
        [YT, "--no-warnings", "--cookies", OUT, "--skip-download",
         "--print", "%(title)s | %(uploader)s | %(duration)s | %(view_count)s", probe_video],
        capture_output=True, text=True, timeout=120,
    )
    out = (r.stdout + r.stderr).strip()
    fresh_err = "Fresh cookies" in out
    print(f"[douyin-probe] rc={r.returncode} fresh_cookies_error={'YES' if fresh_err else 'NO'}")
    print(out[:500])
    # 退出码：成功=0；仍报 fresh cookies 或非0=1
    sys.exit(0 if (r.returncode == 0 and not fresh_err) else 1)


if __name__ == "__main__":
    main()
