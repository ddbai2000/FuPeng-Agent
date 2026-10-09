# 付鹏 Agent 技能备份（可移植）

本目录备份 **agent 技能库**中**本轮蒸馏产出**的新技能（含 SKILL.md + references/），
保证技能随仓库可移植。技能本体运行于本机的 agent 技能库（`finance/` 分类目录下），
此处为只读副本。

## 清单

| 技能 | 来源 | 内容 |
|---|---|---|
| `emotion-value-cash-cow/` | 蒸馏自 `mEJVwHRb9iE`（泡泡玛特/段永平对谈）+ `ullqcN2K9Sc`（游戏→AI漫剧注意力迁移） | 情绪价值商品=现金奶牛×短周期；投效比/复购/客群画像三敏感数据 |
| `founder-ip-premium/` | 蒸馏自 `xcwBxeojxvM`（老板人设 IP） | 老板的嘴=带杠杆金融衍生工具；溢价与零容错代价 |
| `ai-frontier-governance-node/` | 蒸馏自 `YYDOruQriEM`（Anthropic 前沿 AI 警告） | 前沿 AI 治理临界点：BSL 分级+代码比病毒难防+智能 AI 会伪装+治理核武器化 |
| `au-property-housing-cycle/` | 蒸馏自 `v86YxyUYeYs`（双杀备忘录·澳新出清高潮） | 做空澳新 10 年复盘：影子监管真空+高房贷侵蚀居民+汇率化解债务+居民生产力底线 |
86YxyUYeYs（双杀备忘录·澳新出清高潮） | 做空澳新 10 年复盘：影子监管真空+高房贷侵蚀居民+汇率化解债务+居民生产力底线 |

每个技能目录结构：
```
<skill>/
  SKILL.md                     # 心智模型 + 决策启发式 + 易混辨析 + ASR 错字还原
  references/source-*.txt     # 原视频转录节选（带 [MM:SS] 时间戳）
```

## 同步到 agent 技能库（可移植安装）

技能本体存放于 agent 技能库的 `finance/` 分类目录。安装/回填命令（git-bash，
`SKILLS` 指向**你本机的 agent 技能库 finance 目录**，本机真实路径见
`FuPeng-Agent/config.local.json` / `FuPeng-Agent/local.env` 的本地 overlay，不上库）：

```bash
SKILLS="<本机 agent 技能库>/finance"
# 把本仓库副本覆盖回技能库（cp -r 整目录，含 references/）
cp -r docs/skills/emotion-value-cash-cow  "$SKILLS/"
cp -r docs/skills/founder-ip-premium      "$SKILLS/"
```

- **重新注册是自动的**：agent 每个新会话自动扫描技能目录，放回即生效，无需手动命令。
- ⚠️ 验证方式：用 agent 的 `skills_list`（看是否含该技能）或 `skill_view(name)` 确认已加载；
  **不要**用 hub 技能安全审计命令验证本地手建技能（会报 `not a hub-installed skill`）。

> 分类（finance）仅为目录分组，不影响可加载性；agent 以目录名注册技能，
> 故须保持 `finance/<skill>/SKILL.md` 结构。

## 版本

- 备份时间：2026-10-09（第 15 批：au-property-housing-cycle 澳新出清高潮；ai-frontier-governance-node 见 2026-10-04 第 14 批）
- 上游来源：付鹏 2026 YouTube 系列（详见各 SKILL.md 头部"来源"行）

