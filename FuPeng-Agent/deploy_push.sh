#!/usr/bin/env bash
# FuPeng Agent — 推送包装器：GCM token + 本地代理（代理可用 local.env 的 PROXY 覆盖）。
# 用法: bash FuPeng-Agent/deploy_push.sh   （由 sync_update.sh 调用，也可独立跑）
set -u
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)" || { echo "cd fail"; exit 1; }
[ -f FuPeng-Agent/local.env ] && . FuPeng-Agent/local.env
PROXY="${PROXY:-http://127.0.0.1:10808}"
PY="${PY:-python}"
REPO="ddbai2000/FuPeng-Agent"

ORIG=$(git config --global --get url.git@github.com:.insteadOf || echo "__NONE__")

# --- GCM 凭据落到临时文件（token 可能含 # 等特殊字符，绝不能走 shell 变量展开）---
mkdir -p "$HOME/.cache"
CREDF="$HOME/.cache/fupeng_github_creds"
TOKF="$HOME/.cache/fupeng_github_token"
USEF="$HOME/.cache/fupeng_github_user"
printf 'protocol=https\nhost=github.com\n\n' | GIT_TERMINAL_PROMPT=0 git credential fill > "$CREDF" 2>/dev/null
[ -s "$CREDF" ] || { echo "CRED_FILL_FAILED"; exit 4; }

"$PY" - "$CREDF" "$TOKF" "$USEF" <<'PYEOF'
import sys
cred_file, tok_file, user_file = sys.argv[1], sys.argv[2], sys.argv[3]
token, user = "", "ddbai2000"
with open(cred_file, encoding="utf-8") as f:
    for line in f:
        if line.startswith("password="):
            token = line[len("password="):].strip()
        elif line.startswith("username="):
            user = line[len("username="):].strip()
with open(tok_file, "w", encoding="utf-8") as f:
    f.write(token)
with open(user_file, "w", encoding="utf-8") as f:
    f.write(user)
print("token_len=%d user=%s" % (len(token), user))
PYEOF

[ -s "$TOKF" ] || { echo "NO_TOKEN"; rm -f "$CREDF" "$TOKF" "$USEF"; exit 2; }

# --- token URL（shell 内联，仅用于本次命令；token 不出现在输出里）---
TOKEN_URL="https://$(cat "$USEF"):$(cat "$TOKF")@github.com"
AUTH="Authorization: Bearer ***"

EXIST=$(curl -s -o /dev/null -w '%{http_code}' -x "$PROXY" -H "$AUTH" "https://api.github.com/repos/$REPO")
echo "repo_exists_http=$EXIST"

if [ "$EXIST" = "404" ]; then
  BODY=$(printf '{"name":"FuPeng-Agent","description":"付鹏宏观思维 Agent：三平台采集→本地ASR→自动蒸馏的可持续管线","private":false}')
  C=$(curl -s -w '\nHTTP=%{http_code}' -x "$PROXY" -X POST -H "$AUTH" -H 'Content-Type: application/json' -d "$BODY" "https://api.github.com/user/repos")
  CODE=$(echo "$C" | grep 'HTTP=' | sed 's/HTTP=//')
  echo "create_http=$CODE"
  echo "$C" | grep -oE '"full_name":"[^"]+"' | head -1
  [ "$CODE" = "201" ] || { echo "CREATE_FAILED"; rm -f "$CREDF" "$TOKF" "$USEF"; exit 3; }
fi

# --- push（git 必须经本地代理连 github.com:443；临时解除 HTTPS->SSH 重写）---
# DEPLOY_FORCE=1 时追加 --force（仅用于历史改写后的强制同步）
git config --global --unset-all "url.git@github.com:.insteadOf" 2>/dev/null
echo "=== pushing ==="
FORCE_ARGS=()
[ -n "${DEPLOY_FORCE:-}" ] && FORCE_ARGS=(--force)
GIT_TERMINAL_PROMPT=0 timeout 90 git -c http.proxy="$PROXY" -c https.proxy="$PROXY" \
  push "${TOKEN_URL}/${REPO}.git" main:main "${FORCE_ARGS[@]}"
PUSH_RC=$?

# --- 恢复原状 + 清理含 token 的临时文件 ---
if [ "$ORIG" != "__NONE__" ]; then git config --global url.git@github.com:.insteadOf "$ORIG"; fi
git remote set-url origin "git@github.com:${REPO}.git"
rm -f "$CREDF" "$TOKF" "$USEF"
echo "=== push_rc=$PUSH_RC  insteadOf_now=$(git config --global --get url.git@github.com:.insteadOf || echo NONE)  token_files_cleaned ==="
exit $PUSH_RC
