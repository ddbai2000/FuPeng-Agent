#!/usr/bin/env python3
"""云端预测：ESPN 赛程 + 三模型预测 → 人读报告 + 机器可读快照。"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from datetime import datetime, timezone, timedelta

BJ = timezone(timedelta(hours=8))
WORK = os.path.dirname(os.path.abspath(__file__))
os.chdir(WORK)
os.makedirs("reports/predictions", exist_ok=True)
os.makedirs("cloud_logs", exist_ok=True)

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("cloud_predict")


def main():
    from sports_pred.config import load_config
    from sports_pred.predict import _fit_all, predict_match_detail, is_predictable_league
    from sports_pred.data.live import fetch_espn_matches
    from sports_pred.data.odds.teams import to_zh

    today = datetime.now(BJ).strftime("%Y-%m-%d")
    cfg = load_config()
    logger.info("拟合模型 ...")
    fitted = _fit_all(cfg)

    rows = []
    from datetime import timedelta
    tomorrow = (datetime.now(BJ) + timedelta(days=1)).strftime("%Y-%m-%d")
    for sport in ("football", "basketball"):
        matches = fetch_espn_matches(today, sport) + fetch_espn_matches(tomorrow, sport)
        for m in matches:
            if not is_predictable_league(m.league):
                continue
            h, a = to_zh(m.home_team), to_zh(m.away_team)
            try:
                det = predict_match_detail(h, a, sport, cfg=cfg, fitted=fitted,
                                           league=m.league)
            except Exception as e:
                logger.warning("predict fail %s vs %s: %s", h, a, e)
                continue
            if not det.get("valid"):
                continue
            probs = {mn: {k: float(v) for k, v in pv.items()}
                     for mn, pv in det["probs"].items()}
            tops = {}
            for name, p in probs.items():
                order = ["home", "draw", "away"] if sport == "football" else ["home", "away"]
                tops[name] = max(order, key=lambda k: p.get(k, 0))
            agree = len(set(tops.values())) == 1
            rows.append({
                "date": today, "sport": sport, "league": m.league,
                "home": h, "away": a, "start": m.date,
                "probs": probs, "tops": tops, "agree": agree,
            })

    stamp = datetime.now(BJ).strftime("%Y%m%d_%H%M")
    # 机器可读快照
    snap = {"generated_at": datetime.now(BJ).isoformat(), "date": today, "items": {}}
    for r in rows:
        key = f"{r['date']}|{r['sport']}|{r['home']}|{r['away']}"
        snap["items"][key] = r
    with open(f"reports/predictions/pred_{stamp}.json", "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False, indent=1, default=float)

    # 人读报告
    def pct(x): return f"{x*100:.0f}%"
    lines = [f"# 云端当日赛事预测 · {today} {datetime.now(BJ).strftime('%H:%M')}",
             "", "> 数据源：ESPN 公开赛程；模型：Elo / Poisson / Classifier", ""]
    for sport, title in (("football", "足球"), ("basketball", "篮球")):
        rs = [r for r in rows if r["sport"] == sport]
        lines += [f"## {title}（{len(rs)} 场）", "",
                  "| 时间 | 联赛 | 对阵 | Elo | Poisson | Classifier | 一致性 |",
                  "|---|---|---|---|---|---|---|"]
        for r in rs:
            p = r["probs"]
            def cell(name):
                d = p.get(name, {})
                if r["sport"] == "football":
                    return "/".join(pct(d.get(k, 0)) for k in ("home", "draw", "away"))
                return "/".join(pct(d.get(k, 0)) for k in ("home", "away"))
            lines.append(f"| {r['start'][11:16] if len(r['start'])>16 else r['start']} "
                         f"| {r['league']} | {r['home']} vs {r['away']} "
                         f"| {cell('elo')} | {cell('poisson')} | {cell('classifier')} "
                         f"| {'✓' if r['agree'] else '分歧'} |")
        lines.append("")
    lines += ["---", f"共 {len(rows)} 场有效预测。"]
    report = "\n".join(lines)
    with open(f"reports/云端预测_{today}_{stamp}.md", "w", encoding="utf-8") as f:
        f.write(report)
    with open(f"reports/云端预测_{today}.md", "w", encoding="utf-8") as f:
        f.write(report)
    print(f"预测完成: reports/云端预测_{today}_{stamp}.md")
    print(f"预测快照: reports/predictions/pred_{stamp}.json  ({len(rows)} 场)")


if __name__ == "__main__":
    main()