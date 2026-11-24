#!/usr/bin/env python3
"""ESPN 完赛赛果回填 history.csv（云端独立数据闭环）。"""
import sys, os, csv
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
    from sports_pred.predict import is_predictable_league

    today = datetime.now(BJ)
    new_rows = 0
    path = "data/raw/history.csv"
    existing = set()
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for r in csv.reader(f):
                if len(r) >= 5:
                    existing.add((r[0], r[2], r[3], r[4]))
    else:
        with open(path, "w", encoding="utf-8", newline="") as f:
            csv.writer(f).writerow(["date","sport","league","home_team","away_team",
                                    "home_score","away_score","home_odds","draw_odds","away_odds"])
    with open(path, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        for off in range(0, 3):
            d = (today - timedelta(days=off)).strftime("%Y-%m-%d")
            for sport in ("football", "basketball"):
                for m in fetch_espn_matches(d, sport):
                    if not getattr(m, "finished", False):
                        continue
                    if m.home_score is None or m.away_score is None:
                        continue
                    if not is_predictable_league(m.league):
                        continue
                    h, a = to_zh(m.home_team), to_zh(m.away_team)
                    key = (d, m.sport, h, a)
                    if key in existing:
                        continue
                    existing.add(key)
                    w.writerow([d, m.sport, m.league, h, a, m.home_score, m.away_score, "", "", ""])
                    new_rows += 1
    print(f"回填完成: 新增 {new_rows} 场")


if __name__ == "__main__":
    main()