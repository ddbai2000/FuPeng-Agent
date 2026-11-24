#!/usr/bin/env python3
"""云端调度入口：predict（12:00/0:00） / retrain（12:30/0:30）。"""
import sys, os, subprocess, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from datetime import datetime, timezone, timedelta

BJ = timezone(timedelta(hours=8))
WORK = os.path.dirname(os.path.abspath(__file__))
os.chdir(WORK)
os.makedirs("cloud_logs", exist_ok=True)
import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                    handlers=[logging.FileHandler("cloud_logs/scheduler.log", encoding="utf-8"),
                              logging.StreamHandler()])
PY = os.path.join(WORK, ".venv", "bin", "python")


def run(name, args, timeout=3600):
    logging.info("[START] %s", name)
    t0 = datetime.now()
    try:
        r = subprocess.run(args, capture_output=True, text=True, cwd=WORK, timeout=timeout)
        ok = r.returncode == 0
        logging.info("[END] %s %s %.1fs", name, "OK" if ok else f"rc={r.returncode}",
                     (datetime.now()-t0).total_seconds())
        if not ok:
            logging.warning("[FAIL] %s: %s", name, (r.stderr or r.stdout or "")[-400:])
        return ok
    except subprocess.TimeoutExpired:
        logging.warning("[TIMEOUT] %s", name)
        return False
    except Exception as e:
        logging.warning("[ERR] %s: %s", name, e)
        return False


def phase_predict():
    today = datetime.now(BJ).strftime("%Y-%m-%d")
    logging.info("=== PHASE predict %s ===", today)
    run("predict_report", [PY, "cloud_predict.py"], timeout=900)


def phase_retrain():
    today = datetime.now(BJ).strftime("%Y-%m-%d")
    logging.info("=== PHASE retrain %s ===", today)
    run("collect_backfill", [PY, "cloud_backfill.py"], timeout=900)
    run("bookmakers_collect", [PY, "cloud_bookmakers_collect.py"], timeout=300)
    run("contrast_review", [PY, "cloud_review.py"], timeout=900)
    run("daily_review", [PY, "daily_review.py", today], timeout=1800)
    run("train", [PY, "-m", "sports_pred.cli", "train", "--train-only", "--folds", "5"],
        timeout=7200)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=["predict", "retrain", "all"])
    a = ap.parse_args()
    logging.info("云端调度启动 phase=%s 北京=%s", a.phase,
                 datetime.now(BJ).strftime("%Y-%m-%d %H:%M:%S"))
    if a.phase in ("predict", "all"):
        phase_predict()
    if a.phase in ("retrain", "all"):
        phase_retrain()
    logging.info("云端调度完成 phase=%s", a.phase)


if __name__ == "__main__":
    main()