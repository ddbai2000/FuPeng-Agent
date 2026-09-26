#!/usr/bin/env bash
# FuPeng Agent — Job1 采集+ASR 包装器（cron no_agent 脚本）
# 有动态才输出（配合 cron 静默 watchdog）；无新视频时 stdout 为空 → 不推送用户。
cd /h/Agent/FuPeng-Agent/FuPeng-Agent || exit 1
PY=python
exec "$PY" collect_and_transcribe.py
