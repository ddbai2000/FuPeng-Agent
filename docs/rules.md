# FuPeng Agent — 跨 Agent 共享铁律（Codex / Hermes / WorkBuddy 等）

> 任何 clone 本仓库、跑这条管线的 agent，**开工前必须读这一页**。
> 本文件与 `state.json` 共同构成管线的"已做过什么"单一事实源。

## 铁律（硬性，违反即返工）

### 1. 每次采集前，先复查"已蒸馏 / 已转录"清单（省算力）
**跑 `collect_and_transcribe.py` 之前，必须先跑一次 `preflight.py`**（或等价复查），确认：
- `state.json` 的 `seen` / `distilled` 里已经有什么视频
- `transcripts/*.txt` 里已经转录了哪些
- `docs/skills/` 里已经蒸馏了哪些技能

只有"**尚未 seen**"的视频才值得下载 + ASR；已转录的绝不重转；已蒸馏的绝不重复提炼。
目的：避免重复采集、重复转录、重复蒸馏，**省算力**（用户明确要求）。

### 2. 付鹏宏观框架是"共享资产"，蒸馏要贴既有边界
- 新提炼的技能必须写进 `docs/skills/<skill>/SKILL.md`，含 **易混辨析**（对照现有技能边界），避免同义覆盖。
- 来源视频 ID 必须写进 `references/source-<VID>.txt`，带 `[MM:SS]` 时间戳。
- 蒸馏完一条视频，立刻 `python distill_watchdog.py --mark-done <key>` 写进 `state.distilled`。

### 3. 省算力取向（用户长期偏好）
- 能用 Python 一把梭的，不铺一堆 bash 管道 / 不起多个大模型 agent。
- ASR 用本地 `transcribe.py`（faster-whisper），不上传 LLM 转写。
- 长任务（ASR 推理）放后台 `run_in_background`，不阻塞前台。

### 4. 仓库是"去标识化公开仓"，本地真实路径走 overlay
- 真实路径 / token / cookie **不入库**，放 `config.local.json` / `local.env`（git 忽略）。
- 推回上游需仓库作者（ddbai2000）的 GCM token，agent 不得自行 push 别人的凭据。

## 标准作业流程（采集 → 蒸馏 → 标记）

```
① preflight.py               # 先复查已做过什么（铁律 1）
② collect_and_transcribe.py   # 只发现/下载【未 seen】的新视频 + 起 ASR
③ asr_feeder.py               # 接力排空 ASR，直到全 done
④ distill_watchdog.py         # 列出"已转录未蒸馏"的
⑤ 逐个蒸馏成 docs/skills/     # 贴边界 + 带来源
⑥ distill_watchdog.py --mark-done <key>
```

## 各 agent 职责约定
- **WorkBuddy / Codex / Hermes**：都能独立跑全流程；跑之前先读本页 + `state.json`。
- 若 agent 已做过某步，**必须**在 `state.json` 留痕（seen/distilled），让下一个 agent 看到、不重做。
- 新增技能默认进 `docs/skills/`，由各自宿主拷进本地技能库（WorkBuddy→`~/.workbuddy/skills/finance/`）。
