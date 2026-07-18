# ITER-0024 Agent No-progress Recovery

> 状态：Completed
> 日期：2026-07-12

## 背景

真实模型与 Android 真机 E2E 暴露出 Agent 闭环缺陷：模型连续五轮输出相同的
`input.swipe(direction=up)`，页面没有产生可观察变化，但 Runtime 仅依据 ADB 命令返回值将每轮动作记为
`succeeded`。模型没有收到上一动作无效的结构化反馈，Web 报告也只显示 `Decision: -`，无法支持诊断。

## 目标

- 区分“Tool 命令执行成功”和“页面产生进展”。
- 将上一动作的确定性进展反馈传入下一轮 Planner Observation。
- 相同动作无进展后，禁止 Planner 原样重复触发设备动作。
- 明确 `input.swipe` 方向表示手指运动方向，帮助模型正确选择上下文方向。
- 在 Web 报告中展示 Tool、参数和页面进展。

## 实现

### Contract

新增 `agent-action-feedback.schema.json`，定义：

- `tool_id` 与执行参数；
- `effect`: `changed | unchanged | unknown`；
- 判断依据和安全、受限的用户消息。

`AgentObservationSummary` 向后兼容地增加可选 `last_action_feedback`；`AgentStepResult` 向后兼容地增加可选
`action_feedback`。已有字段及语义不变，因此不提升主版本。

### Runtime

- Tool 执行后比较前后 foreground app 和 UI tree 内容哈希。
- 页面或前台应用发生变化时标记 `changed`，均未变化时标记 `unchanged`。
- 下一轮 Observation 携带上一动作反馈。
- Planner 在收到 `unchanged` 后仍输出完全相同的 Tool 与参数时，以 `NO_PROGRESS` 在动作派发前停止。
- Rule Planner 在上下滑动无进展时切换相反方向。

Runtime 不替模型决定或改写动作参数，只提供确定性反馈与安全防循环约束。

### Model Prompt 与报告

- Prompt 明确：`up` 表示手指向上、显示列表更靠下内容；`down` 表示手指向下、显示更靠上内容。
- Prompt 要求收到 `unchanged` 后调整方向、参数或 Tool。
- Web 报告显示实际 `tool_id`、arguments、reason、confidence 和 action feedback。

## 验收

- 无变化的 Tool 产生 `action_feedback.effect=unchanged`。
- 相同无进展动作不会第二次派发到设备。
- 反馈进入真实模型请求，且不包含密钥。
- Rule Planner 能在向上滑动无进展后切换向下。
- Web 报告不再把 `run_tool` 显示为 `Decision: -`。
- `make check` 通过。

## 已知限制

- 当前进展检测基于前台应用和 UI tree，暂未引入视觉相似度；纯 Canvas 或 UI tree 不变化的动画页面可能返回
  `unchanged`。
- 本迭代只提供单步反馈和重复动作防循环，不实现长期轨迹记忆或复杂探索策略。
- 真机 E2E 需要 Runtime 重启后由用户显式运行，不进入默认测试集。
