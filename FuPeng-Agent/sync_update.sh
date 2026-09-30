#!/usr/bin/env bash
# FuPeng Agent — 周期结束钩子：更新 GitHub 显示时间戳 + commit + push。
# 用法: bash sync_update.sh "<本周期说明>"
# 无变化时 NO_UPDATE 跳过；推送经 FuPeng-Agent/deploy_push.sh（GCM token + 本地代理，代理可经 local.env 的 PROXY 覆盖）。
set -u
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)" || exit 1
[ -f FuPeng-Agent/local.env ] && . FuPeng-Agent/local.env
PY="${PY:-python}"
MSG="${1:-采集/蒸馏周期}"

"$PY" FuPeng-Agent/sync_update.py "$MSG" || exit 1

git add -A
if git diff --cached --quiet; then
  echo "NO_UPDATE（工作区无变化，跳过提交）"
  exit 0
fi
git commit -m "chore: 管线周期 $MSG ($(date '+%Y-%m-%d %H:%M'))" >/dev/null || exit 2
bash FuPeng-Agent/deploy_push.sh
RC=$?
if [ "$RC" -eq 0 ]; then
  echo "SYNC_DONE 已推送 FuPeng-Agent@main，README 顶部「最后更新」已刷新"
else
  echo "PUSH_FAILED rc=$RC（token 失效或代理不可用，检查 FuPeng-Agent/deploy_push.sh 日志）"
fi
exit "$RC"
