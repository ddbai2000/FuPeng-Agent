#!/usr/bin/env bash
# FuPeng Agent — Job2 蒸馏看门狗包装器（cron 脚本预跑，输出待蒸馏清单给 agent）
# 输出 NO_WORK → agent 判定无活可干，静默结束；有清单 → agent 逐个蒸馏。
cd /h/Agent/FuPeng-Agent/FuPeng-Agent || exit 1
PY=python
exec "$PY" distill_watchdog.py
