#!/usr/bin/env bash
# FuPeng Agent — Job1 采集+ASR 包装器（cron no_agent 脚本）
# 铁律 1：每次采集前先跑 preflight.py 复查"已做过什么"（省算力）。
# 有动态才输出（配合 cron 静默 watchdog）；无新视频时 stdout 为空 → 不推送用户。
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)" || exit 1
[ -f local.env ] && . ./local.env
PY="${PY:-python}"

# ① 前置复查（铁律 1）：全空(NO_WORK, exit=3) 就跳过采集，省算力
"$PY" preflight.py
PRE="${?}"
if [ "$PRE" -eq 3 ]; then
  echo "PREFLIGHT_NO_WORK 全空，跳过采集（省算力）"
  exit 0
fi

# ② 有活 → 正常采集
exec "$PY" collect_and_transcribe.py
