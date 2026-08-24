# ITER-0058 Programmatic Navigation & Notification Read

> 文档状态：Active
> 迭代状态：Completed
> 创建日期：2026-08-24
> 关联：[价值主张讨论稿](../../product/value-proposition-v1.1-draft.md) · [Capability 模型](../../architecture/capability-model.md) · [ADR-0005](../../adr/0005-agent-decision-action-model.md)

## 背景

当前所有设备交互都通过模拟手指完成：点击、滑动、输入。这带来三个已验证的问题：

- 「进入 Wi-Fi 设置页」类目标需要多轮 GUI 探索，慢、脆、消耗模型预算。
- Agent 无法回答「通知/短信是否到达」这类只能看系统状态的验证问题。
- 行业共识（CoAct-1、StateAct、MAI-UI）已转向混合动作空间：能程序化到达的不点屏幕，
  视觉/GUI 操作作为兜底。StateAct 证明 GUI 子代理只需承担约 1% 的步骤。

现有启动应用仅支持 Launcher 类别（`monkey -p <pkg> -c LAUNCHER`），没有任何受控的
Intent/Settings 直达能力。本迭代交付混合动作空间的第一波：枚举制系统导航直达 +
有界脱敏的通知读取，两者共用「新 Capability 接入」模板，为后续 CJK 输入 helper
（ITER-0059 候选）和 Deep Link 能力铺路。

## 目标

- 新增 `app.navigate@1` Capability：枚举制 Android 系统 Settings Action 直达
  （如 `settings.wifi` → `android.settings.WIFI_SETTINGS`），Adapter 只从枚举 ID 映射
  固定 `am start -a <action>` 参数数组，不接受任意 Action、Component、URI 或 extras。
- 每个枚举 Action 在 Capability Catalog 登记预期前台包名/Activity 模式，
  执行后强制验证，验证不符返回 `ACTION_OUTCOME_UNKNOWN`，禁止自动重试。
- 新增 `notifications.read@1` Capability：有界 `dumpsys notification` 快照，
  Adapter 内解析并脱敏，公共输出只保留包名、标题（截断）与时间戳，正文默认丢弃；
  原始输出不离开 Adapter。
- 提供确定性 Skill（`app.navigate`、`device.notifications.read`）、REST 与 MCP 只读/受控入口。
- Agent 集成：Runtime 对已登记的安全捷径优先走确定性路径（不进模型决策循环），
  未命中时保持现有逐轮 `run_tool` 探索；`app.navigate` 同时进入 Agent allowlist。

## 非目标

- 不做任意 Deep Link / URI / Component 跳转（B 档），URI 白名单治理需独立迭代与 ADR。
- 不做 CJK 输入法 helper、剪贴板、文件传输（后续迭代）。
- 不修改 High 风险授权策略；本迭代不含 High 风险能力。
- 不改变现有 GUI 动作链路与 `run_tool` 决策模型（ADR-0005 语义不变，仅新增补充路径）。
- 不支持通知正文返回、通知点击或清除。

## 兼容性

新增 Contract Schema、Capability、Tool、Skill、REST 端点与 MCP Tool，均为向后兼容变化；
无数据库迁移。Agent 侧新增「Runtime 程序化捷径优先」路由行为，属于执行语义变化，
需新增一份 ADR 记录决策与边界（含禁止任意参数注入的约束）。

## 风险与应对

- **导航直达成为逃生口**：枚举制白名单 + 固定参数数组 + 禁 extras + 后置验证四层收紧；
  模型与客户端只能传枚举 ID，永远接触不到原始 `am` 参数。
- **通知内容 PII 泄露**：复用 `logs.collect@1` 模式（Adapter 内脱敏、原始输出丢弃、
  有界快照）；正文默认不返回，标题截断，需 Medium 风险确认。
- **厂商 ROM 差异导致 Action 行为不一致**：后置验证以实际前台 Activity 为准；
  验证不了就报 `ACTION_OUTCOME_UNKNOWN`，不猜、不重试。
- **dumpsys notification 输出格式厂商差异**：解析失败或为空使用专用错误码，
  不以空列表冒充「无通知」。

## 新错误码（实施时登记到 error-handling.md）

```text
NAVIGATION_ACTION_UNKNOWN      # 枚举 ID 未登记
NAVIGATION_NOT_VERIFIED        # am start 成功但前台未到达预期目标
NOTIFICATIONS_READ_FAILED      # dumpsys 解析失败
NOTIFICATIONS_READ_EMPTY       # 确认为零通知（区别于解析失败）
```

## 测试与验收要点

- Capability Contract 测试：unavailable / degraded / 状态变化路径。
- Adapter 测试：枚举映射、非法输入在进程调用前拒绝、固定参数数组快照、dumpsys 样本解析与脱敏。
- Skill 测试矩阵按 skill-development.md §10 全覆盖（成功、参数错误、Capability 缺失、
  Policy 拒绝、超时取消、验证失败、设备断连）。
- 真机 E2E：只读 + Low/Medium 场景集中一次执行，见 acceptance.md。
