"""FuPeng Agent — 采集/蒸馏周期结束：写 GitHub 显示更新时间戳。

用法: python sync_update.py "<本周期说明>"
- 更新仓库根 README.md 顶部「最后更新」行（无则插入 H1 后）
- 追加 UPDATE_LOG.md（更新日志）
- 写 state.json last_sync
git commit/push 由 sync_update.sh 负责（调用 FuPeng-Agent/deploy_push.sh）。
"""
import datetime, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                      # 仓库根目录
sys.path.insert(0, HERE)

msg = sys.argv[1] if len(sys.argv) > 1 else "采集/蒸馏周期"
now = datetime.datetime.now()
ts = now.strftime("%Y-%m-%d %H:%M")

# 1) README 顶部「最后更新」行
readme = os.path.join(ROOT, "README.md")
text = open(readme, encoding="utf-8").read()
line = f"> ⏱ **最后更新：{ts}**（管线自动同步 · {msg}）"
pat = re.compile(r"^> ⏱.*$", re.M)
if pat.search(text):
    text = pat.sub(lambda m: line, text, count=1)
else:
    m = re.search(r"^# .*$", text, re.M)
    if m:
        text = text[:m.end()] + "\n\n" + line + text[m.end():]
    else:
        text = line + "\n\n" + text
with open(readme, "w", encoding="utf-8", newline="\n") as f:
    f.write(text)

# 2) UPDATE_LOG.md 追加
logp = os.path.join(ROOT, "UPDATE_LOG.md")
if os.path.exists(logp):
    existing = open(logp, encoding="utf-8").read()
else:
    existing = ("# 付鹏 Agent 更新日志\n\n"
                "每次采集/蒸馏周期结束时自动追加（GitHub 上可查看完整更新历史；"
                "最新时间戳同时显示在 README 顶部）。\n\n"
                "---\n\n")
    with open(logp, "w", encoding="utf-8", newline="\n") as f:
        f.write(existing)
with open(logp, "a", encoding="utf-8", newline="\n") as f:
    f.write(f"- **{ts}** — {msg}\n")

# 3) state.json last_sync（原子写，保留 worker 并发修改）
import stateio
def apply(d):
    d["last_sync"] = {"at": now.isoformat(), "msg": msg}
stateio.atomic_update(apply)

print(f"TIMESTAMP_UPDATED {ts} | {msg}")
