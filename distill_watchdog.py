"""FuPeng Agent — 蒸馏看门狗：列出"转录完成但未蒸馏"的视频 + 投喂书籍。

用法: python distill_watchdog.py
输出（stdout，供 cron agent 读取并执行蒸馏）：
  - 每个待蒸馏视频的 key/标题/平台/转录路径/大小
  - books/pending/ 下的待蒸馏书籍
  - 蒸馏完成后 agent 调用: python distill_watchdog.py --mark-done <key>
  - 全部完成时输出 "NO_WORK"（watchdog 静默模式：cron 收到 NO_WORK 可不通知用户）

state.distilled 记录已蒸馏的 key，去重。
"""
import json, os, sys, datetime

HERE = os.path.dirname(os.path.abspath(__file__))

def main():
    state = json.load(open(os.path.join(HERE, "state.json"), encoding="utf-8")) if os.path.exists(os.path.join(HERE, "state.json")) else {"seen": {}, "asr_jobs": [], "distilled": {}}
    state.setdefault("distilled", {})

    if "--mark-done" in sys.argv:
        idx = sys.argv.index("--mark-done")
        key = sys.argv[idx + 1]
        state["distilled"][key] = {"at": datetime.datetime.now().isoformat()}
        p = os.path.join(HERE, "state.json")
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=1)
        os.replace(tmp, p)
        print(f"marked distilled: {key}")
        return

    # 1) 转录完成未蒸馏的视频
    pending = []
    for m in state.get("asr_jobs", []):
        key = m.get("key")
        tr = m.get("transcript", "")
        if m.get("status") == "done" and key not in state["distilled"]:
            exists = os.path.exists(tr) and os.path.getsize(tr) > 2000
            pending.append({**m, "transcript_ok": exists, "transcript_bytes": os.path.getsize(tr) if exists else 0})

    # 2) 投喂书籍（仅识别真实书籍扩展名，忽略 README/说明文件）
    BOOK_EXT = {".pdf", ".docx", ".doc", ".epub", ".mobi", ".azw3", ".txt"}
    books = []
    bp = os.path.join(HERE, "books", "pending")
    if os.path.isdir(bp):
        for fn in sorted(os.listdir(bp)):
            if os.path.splitext(fn)[1].lower() not in BOOK_EXT:
                continue
            fp = os.path.join(bp, fn)
            if not os.path.isfile(fp):
                continue
            books.append(fp)

    if not pending and not books:
        print("NO_WORK")
        return

    print("=== 待蒸馏清单 ===")
    for p in pending:
        print(f"VIDEO {p['key']} | {p.get('platform','?')} | {p.get('title','')[:60]}")
        print(f"  转录: {p['transcript']} ({p['transcript_bytes']}B, ok={p['transcript_ok']})")
        print(f"  蒸馏完成后执行: python {os.path.abspath(__file__)} --mark-done {p['key']}")
    for b in books:
        sz = os.path.getsize(b) if os.path.exists(b) else 0
        print(f"BOOK  {b} ({sz}B)  [pdf/docx/txt/epub — 先提取文本再蒸馏, 完成后删除该文件并记录 state.distilled]")

if __name__ == "__main__":
    main()
