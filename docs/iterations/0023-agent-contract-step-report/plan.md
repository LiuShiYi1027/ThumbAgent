# ITER-0023 Agent Contract & Step Report Formalization

> 状态：Completed
> 日期：2026-07-12

## 背景

ITER-0022 已将 Agent Preview 升级为多轮 `run_tool` / `finish` 决策，但 `AgentDecision`、Observation 摘要和每轮 Agent step result 仍主要是 Python 内部约定；`TaskRun` 公共 Schema 也仍停留在 `settings.scroll_navigate` 单步 Skill 阶段。

这会让桌面端、CLI、未来 MCP/Skill 形态难以稳定消费任务报告，也不符合 Contract-first 规范。

## 目标

- 将 Agent 每轮报告中的关键对象提升为 JSON Schema：
  - `AgentObservationSummary`
  - `AgentDecision`
  - `AgentStepResult`
- 更新 `TaskRun` Schema，使其正式支持 `agent.run`、`agent_round` 和 `agent.round`。
- 让 Runtime 输出带版本的稳定 Agent step result，避免客户端依赖隐式字段是否存在。
- 增加 Contract 回归测试，保证 Agent 契约不会从公共协议中消失。

## 非目标

- 不改变 Planner 的智能程度。
- 不扩大 V1 支持目标，仍只覆盖单台 Android 本地闭环。
- 不新增 iOS、鸿蒙真实 Adapter。
- 不实现异步任务队列、流式事件或外部 MCP 接口。

## 实现

### Contract

新增：

- `contracts/schemas/agent-observation-summary.schema.json`
- `contracts/schemas/agent-decision.schema.json`
- `contracts/schemas/agent-step-result.schema.json`

更新：

- `contracts/schemas/task-run.schema.json`
  - `task_type` 支持 `agent.run`
  - step `kind` 支持 `agent_round`
  - step `name` 支持 `agent.round`
  - step `result` 支持 `agent-step-result`
  - `goal` 长度放宽到 500，与 Web/Agent 输入保持一致

### Runtime 输出

Agent 每轮 step result 固定包含：

- `schema_version`
- `round`
- `observation`
- `decision`
- `action_result`
- `skill_result`
- `verified_node`

其中 `action_result`、`skill_result`、`verified_node` 未命中当前决策路径时显式为 `null`。

### 测试

- Agent 任务报告断言 step result、observation summary、decision 均包含 `schema_version=1.0.0`。
- Contract 测试断言 Agent schema `$id`、版本、关键 enum 和 TaskRun 对 `agent.run` 的支持。

## 验收

- `agent.run` 任务报告可以被公共 Contract 描述。
- 桌面端/CLI 后续可以基于 `AgentStepResult` 稳定渲染每轮 Observe–Plan–Act。
- 旧 `settings.scroll_navigate` TaskRun 仍被 Schema 支持。

## 后续

- 将前端任务报告视图升级为 Agent step timeline。
- 引入更细的 `AgentDecision.arguments` 子 schema 或 ToolCall schema。
- 正式生成 TypeScript/Python 类型，减少手写近似定义。
