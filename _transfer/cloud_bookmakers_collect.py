#!/usr/bin/env python3
"""6 源独立博彩/数据商采集（bet365/威廉/立博/fonbet/betboom/statsperform）。"""
import sys, os, json, traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from datetime import datetime, timezone, timedelta

BJ = timezone(timedelta(hours=8))
WORK = os.path.dirname(os.path.abspath(__file__))
os.chdir(WORK)
import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

SOURCES = ["bet365", "williamhill", "ladbrokes", "fonbet", "betboom", "statsperform"]


def collect_one(name, today):
    out_dir = f"reports/博彩采集_{today}"
    os.makedirs(out_dir, exist_ok=True)
    try:
        from sports_pred.data.odds import crosscheck
        mod = __import__(f"sports_pred.data.odds.b_{name}", fromlist=["*"])
        fn = getattr(mod, "collect", None) or getattr(mod, "fetch", None)
        data = fn(today) if fn else None
        with open(f"{out_dir}/{name}.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, default=str)
        return name, "OK", data if isinstance(data, int) else (len(data) if data else 0)
    except Exception as e:
        with open(f"{out_dir}/{name}.json", "w", encoding="utf-8") as f:
            json.dump({"error": str(e), "trace": traceback.format_exc()[-800:]}, f, ensure_ascii=False)
        return name, "FAIL", str(e)[:120]


def main():
    today = datetime.now(BJ).strftime("%Y-%m-%d")
    results = {}
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(collect_one, s, today): s for s in SOURCES}
        for fu in as_completed(futs):
            name, status, info = fu.result()
            results[name] = (status, info)
            logging.info("%s: %s %s", name, status, info)
    lines = [f"# 博彩 6 源采集汇总 · {today}", "", "| 源 | 状态 | 明细 |", "|---|---|---|"]
    for s in SOURCES:
        st, info = results.get(s, ("SKIP", ""))
        lines.append(f"| {s} | {st} | {info} |")
    with open(f"reports/博彩采集_{today}/_汇总.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("采集完成")


if __name__ == "__main__":
    main()