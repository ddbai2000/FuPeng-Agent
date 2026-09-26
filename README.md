# 付鹏经济 Agent（FuPeng Agent）

把财经博主付鹏的公开视频/书籍，自动"采集 → 本地 ASR → 蒸馏成可执行技能"，并**持续定时更新**。

## 数据源
| 平台 | 方式 | 状态 |
|---|---|---|
| YouTube | 官方频道「付鹏的财经世界」`UCb_4xq1KgaYkGtxpjkoZrtQ` + 关键词搜索（代理 10808） | ✅ 自动 |
| B站 | UP主 UID `662660667` 空间页 + 搜索页解析 BV（直连，无cookie） | ✅ 自动（412风控时降级搜索兜底） |
| 抖音 | 网页版 JS 防护需 cookies；**人工投喂**：把链接写入 `pending_links.txt` | ⚠️ 半自动 |

## 目录结构
```
H:\Agent\fu-peng-agent\
├─ config.json               # 平台源/代理/线程/路径
├─ state.json                # 全量状态: seen / asr_jobs(running→done) / distilled
├─ collect_and_transcribe.py # 采集+下载+启动ASR（cron Job1 每日跑）
├─ asr_worker.py             # ASR 子进程（faster-whisper small int8，独立存活）
├─ distill_watchdog.py       # 蒸馏看门狗（cron Job2，列出待蒸馏+标记完成）
├─ pending_links.txt         # 抖音/手动投喂链接（一行一个，#注释）
├─ cookies/                  # douyin_cookies.txt / bili_cookies.txt（可选）
├─ books/pending/            # 投喂书籍（pdf/docx/txt/epub）
├─ audio/                    # 下载的 .webm
└─ transcripts/              # ASR 转录 .txt
```

## 两阶段 cron
- **Job1（采集+ASR）**：每日 `FP_QUIET=1 python collect_and_transcribe.py`。发现新视频→下载→启动 ASR（最多 2 并发，超额入队下次转）。**无新视频时 stdout 为空 = 不推送用户**（watchdog 静默）。
- **Job2（蒸馏看门狗）**：`python distill_watchdog.py` 列出"转录完成未蒸馏"的视频 + `books/pending/` 的书籍；agent 逐个蒸馏成技能后，调 `--mark-done <key>` 标记。全部完成输出 `NO_WORK`。

## 手动命令
```bat
REM 交互跑采集（实时日志）
H:\Agent\ft-distill\.venv\Scripts\python.exe H:\Agent\fu-peng-agent\collect_and_transcribe.py --dry-run

REM 看当前待蒸馏清单
H:\Agent\ft-distill\.venv\Scripts\python.exe H:\Agent\fu-peng-agent\distill_watchdog.py
```

## 蒸馏规范
沿用 book-to-skill 结构：`SKILL.md`（frontmatter + 心智模型 M1..Mn + 决策启发式 + 易混辨析）+ `references/source-*.txt`（关键论点带时间戳）。新书/新视频先读完全文再动手，避免与已有技能重复（现有技能清单见下）。

## 现有技能（去重基准）
super-cycle-gears / liquidity-shrink-circle / deglobal-mirror-cycle / debt-tax-demographic-cycle / china-numerator-us-denominator / tech-cycle-credit-shock / cash-cow-spread-flip / realty-k-shrink-core / crypto-major-asset / fed-era-shift / witness-countercurrent / ai-capex-proof-period

**综合总纲（对齐目标）**：`fupeng-perspective`（lianyanshe-ai 仓库版，入口总纲 + 模型6 情景证伪方法论）。新蒸馏的视频/书籍若与其路由表某主题重合 → 并入对应单主题 skill（见该 skill 路由总表），并把增量同步进 `fupeng-perspective` 对应模型的指针行，保持仓库版与自蒸馏版逐步对齐。

## 书籍投喂
把书（pdf/docx/txt/epub）丢进 `books/pending/`，Job2 看门狗会列出；agent 用 ocr-and-documents / pdf 技能提取文本后蒸馏。
