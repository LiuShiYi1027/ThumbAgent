# ITER-0029 Retrospective

> 状态：Completed
> 更新日期：2026-07-14

## 实际交付

- 新增公共 `AgentGoalAcceptance` Contract，并由在线评测场景复用。
- `agent.run` 支持调用方可选成功条件；模型请求 `finish` 后由 Runtime 权威验证。
- TaskRun 保存成功条件和完成来源，Web/CLI 可审计展示。
- 外部验证失败作为无副作用 failed round 反馈模型继续规划。
- 增加 API 请求示例，未提供成功条件时保持兼容。

## 验证结果

- `make check`：通过，包含 lint、类型检查和 149 个单元/集成测试。
- 真机 Runtime-owned acceptance：通过。任务
  `task_1ae4f92ae76b423d8202c29bcfebae2e` 从荣耀桌面开始，模型用 3 rounds 动态完成
  “点击设置 → 点击显示和亮度 → finish”，最终由 Runtime 使用
  `com.android.settings` 和 `.Settings$DisplaySettingsActivity` 判定成功。
- Web 报告确认展示 `completion_source=runtime_acceptance` 和完整 `goal_acceptance` 摘要。

## 偏差与后续

- 当前成功条件由调用方结构化提供，尚不从自然语言自动编译。
- Runtime 仍等待模型发出 `finish`；外部条件已满足时的自动完成留作后续评估。
- 第一版仅支持一个唯一 UI Selector，复杂业务状态需要扩展版本化验证器。
- Activity 在不同厂商和 App 版本之间可能变化，调用方应仅在稳定时使用。
- 真机前置检查发现文档示例曾写入超出 API 上限的 `max_rounds=8`；请求在模型和设备动作前
  被 `INVALID_ARGUMENT` 拒绝，示例已修正为 6。
