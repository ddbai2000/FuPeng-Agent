# 付鹏 Agent 技能备份（可移植）

本目录备份 Agent 技能库中**本轮蒸馏产出**的 2 个新技能（含 SKILL.md + references/），
保证技能随仓库可移植。技能本体运行于 `C:\Users\BYY\AppData\Local\agent\skills\finance\`，
此处为只读副本。

## 清单

| 技能 | 来源 | 内容 |
|---|---|---|
| `emotion-value-cash-cow/` | 蒸馏自 `mEJVwHRb9iE`（泡泡玛特/段永平对谈）+ `ullqcN2K9Sc`（游戏→AI漫剧注意力迁移） | 情绪价值商品=现金奶牛×短周期；投效比/复购/客群画像三敏感数据 |
| `founder-ip-premium/` | 蒸馏自 `xcwBxeojxvM`（老板人设 IP） | 老板的嘴=带杠杆金融衍生工具；溢价与零容错代价 |

每个技能目录结构：
```
<skill>/
  SKILL.md                     # 心智模型 + 决策启发式 + 易混辨析 + ASR 错字还原
  references/source-*.txt     # 原视频转录节选（带 [MM:SS] 时间戳）
```

## 同步到 Agent 技能库（可移植安装）

技能本体存放于 `finance/` 分类目录（本机 `C:\Users\BYY\AppData\Local\agent\skills\finance\`）。
安装/回填命令（在 Agent Agent 环境，git-bash）：

```bash
SKILLS="C:/Users/BYY/AppData/Local/agent/skills/finance"
# 把本仓库副本覆盖回技能库（cp -r 整目录，含 references/）
cp -r docs/skills/emotion-value-cash-cow  "$SKILLS/"
cp -r docs/skills/founder-ip-premium      "$SKILLS/"
```

- **重新注册是自动的**：Agent 每个新会话自动扫描技能目录，放回即生效，无需手动命令。
- ⚠️ `agent skills audit` **只用于 hub-installed 技能的安全扫描**，对本地手建技能报
  `not a hub-installed skill`——**不要用它验证本地技能**；用 `skills_list`（看是否含该技能）或
  `skill_view(name)` 确认已加载即可。

> 分类（finance）仅为目录分组，不影响可加载性；`agent skills` 以目录名注册技能，
> 故须保持 `finance/<skill>/SKILL.md` 结构。

## 版本

- 备份时间：2026-09-30 10:15（蒸馏循环第 13 批产出）
- 上游来源：付鹏 2026 YouTube 系列（详见各 SKILL.md 头部"来源"行）
