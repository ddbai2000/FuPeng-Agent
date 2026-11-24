#!/usr/bin/env python3
"""对照复盘：最近预测快照 vs ESPN 真实赛果，算各模型命中率。"""
import sys, os, json, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from datetime import datetime, timezone, timedelta

BJ = timezone(timedelta(hours=8))
WORK = os.path.dirname(os.path.abspath(__file__))
os.chdir(WORK)
import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def main():
    from sports_pred.data.live import fetch_espn_matches
    from sports_pred.data.odds.teams import to_zh

    snaps = sorted(glob.glob("reports/predictions/pred_*.json"))
    if not snaps:
        print("无预测快照，跳过复盘")
        return
    with open(snaps[-1], encoding="utf-8") as f:
        snap = json.load(f)
    pred_date = snap.get("date", "")

    # 取预测日±1 的 ESPN 完赛
    results = {}
    base = datetime.strptime(pred_date, "%Y-%m-%d")
    for off in (-1, 0, 1):
        d = (base + timedelta(days=off)).strftime("%Y-%m-%d")
        for sport in ("football", "basketball"):
            for m in fetch_espn_matches(d, sport):
                if not getattr(m, "finished", False):
                    continue  # 未开赛/进行中，0-0 是占位不是赛果
                if m.home_score is None or m.away_score is None:
                    continue
                h, a = to_zh(m.home_team), to_zh(m.away_team)
                key = f"{d}|{m.sport}|{h}|{a}"
                if m.home_score > m.away_score:
                    res = "home"
                elif m.home_score < m.away_score:
                    res = "away"
                else:
                    res = "draw"
                results[key] = (res, m.home_score, m.away_score, m.league)

    stats = {name: {"hit": 0, "total": 0} for name in ("elo", "poisson", "classifier")}
    detail_rows = []
    for key, pred in snap.get("items", {}).items():
        if key not in results:
            continue
        res, hs, as_, lg = results[key]
        tops = pred.get("tops", {})
        probs = pred.get("probs", {})
        verdicts = {}
        for name in stats:
            t = tops.get(name)
            stats[name]["total"] += 1
            ok = (t == res)
            if ok:
                stats[name]["hit"] += 1
            verdicts[name] = t
        detail_rows.append((lg, f"{pred['home']} vs {pred['away']}",
                            f"{hs}-{as_}", res, verdicts, probs))

    today = datetime.now(BJ).strftime("%Y-%m-%d")
    lines = ["# 对照复盘报告", "",
             f"> 预测时间：{snap.get('generated_at','')}",
             "> 对照来源：ESPN 完赛赛果", "",
             "## 模型命中率", "",
             "| 模型 | 命中/已匹配 | 命中率 |", "|---|---:|---:|"]
    for name in ("elo", "poisson", "classifier"):
        s = stats[name]
        rate = s["hit"] / s["total"] * 100 if s["total"] else 0
        lines.append(f"| {name} | {s['hit']}/{s['total']} | {rate:.1f}% |")
    lines += ["", "## 逐场对照", "",
              "| 联赛 | 对阵 | 赛果 | 实际 | elo | poisson | classifier |", "|---|---|---|---|---|---|---|"]
    for lg, pair, sc, res, v, p in detail_rows:
        lines.append(f"| {lg} | {pair} | {sc} | {res} | {v.get('elo','')} "
                     f"| {v.get('poisson','')} | {v.get('classifier','')} |")
    report = "\n".join(lines) + "\n"
    out = f"reports/对照复盘_{today}.md"
    with open(out, "w", encoding="utf-8") as f:
        f.write(report)
    hits = "/".join(f"{stats[n]['hit']}/{stats[n]['total']}" for n in ("elo","poisson","classifier"))
    print(f"复盘完成: {out}")
    print(f"命中: {hits}")


if __name__ == "__main__":
    main()