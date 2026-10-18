# 付鹏 Agent 技能备份（可移植）

本目录备份 **agent 技能库**中**本轮蒸馏产出**的新技能（含 SKILL.md + references/），
保证技能随仓库可移植。技能本体运行于本机的 agent 技能库（`finance/` 分类目录下），
此处为只读副本。
保证技能随仓库可移植。技能本体运行于本机的 agent 技能库（早期批次于 `finance/` 分类目录，
新批次与既有付鹏技能同列于技能库根目录），此处为只读副本。

## 清单

| 技能 | 来源 | 内容 |
|---|---|---|
| `emotion-value-cash-cow/` | 蒸馏自 `mEJVwHRb9iE`（泡泡玛特/段永平对谈）+ `ullqcN2K9Sc`（游戏→AI漫剧注意力迁移） | 情绪价值商品=现金奶牛×短周期；投效比/复购/客群画像三敏感数据 |
| `founder-ip-premium/` | 蒸馏自 `xcwBxeojxvM`（老板人设 IP） | 老板的嘴=带杠杆金融衍生工具；溢价与零容错代价 |
| `ai-frontier-governance-node/` | 蒸馏自 `YYDOruQriEM`（Anthropic 前沿 AI 警告） | 前沿 AI 治理临界点：BSL 分级+代码比病毒难防+智能 AI 会伪装+治理核武器化 |
| `au-property-housing-cycle/` | 蒸馏自 `v86YxyUYeYs`（双杀备忘录·澳新出清高潮） | 做空澳新 10 年复盘：影子监管真空+高房贷侵蚀居民+汇率化解债务+居民生产力底线 |
86YxyUYeYs（双杀备忘录·澳新出清高潮） | 做空澳新 10 年复盘：影子监管真空+高房贷侵蚀居民+汇率化解债务+居民生产力底线 |
| `ai-safety-nuclear-moment/` | 蒸馏自 `youtube:YYDOruQriEM`（Anthropic 警告） | 「AI 核时刻」：RSP 1-4 级≈BSL 生物实验室分级；数字围堵失效；评估欺骗；开源 vs 监管=核争论模板 |
| `nobel-expectations-real-money/` | 蒸馏自 `youtube:k7HE_rLAX9M` + `youtube:3Fm8lLXnB0U`（2026 诺奖 Hall & Woodford 两场次） | "信心比黄金重要"只对一半：预期管理必须掏真金白银、改变居民部门长期约束；小甜头进预期内即衰减 |

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
SKILLS="<本机 agent 技能库>"
# 早期批次（finance/ 分类）
cp -r docs/skills/emotion-value-cash-cow  "$SKILLS/finance/"
cp -r docs/skills/founder-ip-premium      "$SKILLS/finance/"
# 新批次（与既有付鹏技能同列技能库根目录）
cp -r docs/skills/ai-safety-nuclear-moment "$SKILLS/"
cp -r docs/skills/nobel-expectations-real-money "$SKILLS/"
```

- **重新注册是自动的**：agent 每个新会话自动扫描技能目录，放回即生效，无需手动命令。
- ⚠️ 验证方式：用 agent 的 `skills_list`（看是否含该技能）或 `skill_view(name)` 确认已加载；
  **不要**用 hub 技能安全审计命令验证本地手建技能（会报 `not a hub-installed skill`）。

> 分类（finance）仅为目录分组，不影响可加载性；agent 以目录名注册技能，
> 故须保持 `finance/<skill>/SKILL.md` 结构。

## 版本

- 备份时间：2026-10-09（第 15 批：au-property-housing-cycle 澳新出清高潮；ai-frontier-governance-node 见 2026-10-04 第 14 批）
- 备份时间：2026-10-18（蒸馏循环第 14 批产出：ai-safety-nuclear-moment + nobel-expectations-real-money；第 13 批 2026-09-30）
- 上游来源：付鹏 2026 YouTube 系列（详见各 SKILL.md 头部"来源"行）

