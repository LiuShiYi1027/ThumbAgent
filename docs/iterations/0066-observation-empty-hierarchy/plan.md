# ITER-0066 Observation Empty Hierarchy（空 UI 树检测、有界恢复与可解释失败）

> 文档状态：Active
> 迭代状态：Completed
> 创建日期：2026-09-21
> 完成日期：2026-09-21
> 关联：[ITER-0061 复盘](../0061-agent-working-memory-and-results/retrospective.md)（跟进项 5）· [可靠性模型](../../architecture/reliability-model.md) · [错误规范](../../engineering/error-handling.md)

## 背景

ITER-0061 真机「京东搜索结果页」上 `uiautomator dump` 持续返回可解析但无语义节点的
hierarchy（小米 2509FPN0BC 复现）。当前管线把这当成一次成功 Observation：

- Adapter 只在 **XML 抽取失败** 时重试 dump，骨架树会当成功写入 Artifact。
- Parser 对空 `<hierarchy>` 或仅有无文本 FrameLayout 的树返回空/无语义节点列表，不报错。
- Agent 把空 `ui_summary` 交给 Planner，模型在看不见控件的情况下猜点击，最终 `NO_PROGRESS`。

这与 dump 失败（`OBSERVATION_FAILED`）和 XML 损坏（`UI_TREE_INVALID`）都不同：设备在线、
截图成功、任务却在「瞎跑」。产品结果是真实 App 长链路无法交卷，也无法向用户说明原因。

本迭代是 0067（真实 App 带回答案基线）的前置底座，不上 OCR、不扩 Agent allowlist。

## 目标

- **空树成为一等失败**：dump 成功但语义候选数为 0 时，判定为 `UI_TREE_EMPTY`（device、
  `retryable=true`、`known_failure`），不再进入 Planner。
- **有界只读恢复**：与既有观察瞬时重试共用预算（最多 3 次 observe）。空树的 settle
  略长于 XML 损坏（约 0.5s），总额外等待有上限；取消与 Deadline 在每次重试前检查。
- **可解释终态**：重试耗尽后任务 `failed`，错误文案说明「当前页无法取得界面结构」；
  失败 step / error.details 携带 `observation_id`、截图 Artifact id、`node_count`、
  `semantic_candidate_count`（只含计数，不含 UI 文本）。
- **派发守卫**：即使观察层漏判，`input.tap_element` / `input.swipe` 在空树上于派发前拒绝；
  `navigation.back` / `home` / `app.launch` / `app.navigate` 不依赖当前树，不在本守卫范围。
- **回归**：系统设置等有语义树的页面行为不变。

## 非目标

- 不上 OCR、截图 grounding 或第二视觉真源。
- 不改 ADB 命令模板，不把 Parser 下沉进 Adapter（Adapter 继续只采集字节）。
- 不扩大 Agent Tool/Skill allowlist，不新增 Capability。
- 不把空树做成可恢复 Planner 轮次（不让模型在空摘要上继续猜）。
- 不把即时 `screen.observe` REST 改为失败——只读采集仍返回截图与原始 XML，供诊断。
- 不在本迭代验收京东比价交卷（ITER-0067）。
- 不做 Desktop 专用空树 UI；沿用既有失败 step / 错误展示。

## 关键决策（已锁定）

1. **判定位置**：Application 层（`AgentRunner._observe_with_retry` 在 Adapter 返回后
   parse）。Adapter 不解释任务成败，符合分层。
2. **空的定义**：解析后可见节点中，text / content_description / hint / resource_id
   皆空则视为空。与「模型摘要只发带文案的节点」略有差别：仅有 resource_id 的
   输入框仍可被 locator 寻址，不能当空树。京东类骨架 FrameLayout（无 id、无文案）
   仍判定为空。
3. **重试语义**：只读、幂等、`known_failure`。耗尽后终止任务，不是 `unknown_outcome`，
   也不是 `NO_PROGRESS`。
4. **不需要 ADR**：无新信任面、无新 Capability、无破坏性 Contract。新增稳定错误码 +
   执行策略，按错误规范登记。
5. **Contract**：不改 Observation Schema（快照仍合法）。新错误码 `UI_TREE_EMPTY` 登记到
   `error-handling.md`，并补序列化/Runner 测试。

## 兼容性

- 既有 `UI_TREE_INVALID` / `OBSERVATION_FAILED` 重试与设置页任务不得回归。
- 失败信封仍是七字段 `MobileAgentError`；`details` 只增加受控计数与 Artifact id。
- 无 SQLite 迁移。

## 风险与应对

- **加载中页面被误杀**：有界 settle + 最多 3 次全量重观察；设置页回归单测钉死。
- **WebView/游戏永久无树**：这是本迭代要暴露的真实能力边界，必须失败可解释，
  不得假装成功。
- **真机空树无法当场复现**：单元/Fake 必须覆盖瞬态恢复与持续失败；真机若无空树 App，
  在验收中记 deferred，不以 Fake 宣称真机空树通过。

## 测试与验收要点

- 空 hierarchy、仅无文本根节点、有语义节点：判定正负样本。
- Fake：空→有树则恢复成功；持续空则 `failed` + `UI_TREE_EMPTY`，observe ≤ 3，Planner 0 次。
- 设置页目标仍 succeeded。
- 取消/Deadline 在空树重试窗口内仍立即生效。
- 集中一次 `make check`；真机至少一条设置页回归，空树页能复现则加一条。
