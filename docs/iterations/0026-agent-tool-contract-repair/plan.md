# ITER-0026 Agent Tool Contract Repair & Failure Evidence

> 状态：Completed
> 日期：2026-07-13

## 背景

真机 E2E 中，模型已在 Observation 看到“显示和亮度”，但 `input.tap_element`
没有携带 `resolve_clickable_ancestor=true`。文本 `TextView` 本身不可点击，可点击目标在父节点，
因此任务以 `TARGET_NOT_CLICKABLE` 结束。同时，Runner 对动作失败只保存 Error，丢失了当轮
Observation 和 Decision，使报告无法直接说明模型实际决策。

## 目标

- 为 Agent 可调用 Tool 定义严格、版本化的参数 Contract。
- 在任何设备动作前拒绝缺失、多余或越界参数。
- 允许 Provider 对 `MODEL_OUTPUT_INVALID` 做一次有界、无副作用的输出修复。
- 在已验证决策的 Tool 执行失败时，保留当轮 Observation 和 Decision。

## 范围

- `app.launch`、`input.tap_element`、`input.swipe`、`navigation.back/home`。
- `input.tap_element.selector.resolve_clickable_ancestor` 必须显式为 `true`。
- OpenAI-compatible Planner 最多两次模型请求：原始请求加一次修复请求。
- 失败 `agent.round` 的稳定结果槽位。

## 非目标

- 不由 Runtime 猜测或静默改写模型动作。
- 不对设备动作做自动重试。
- 不增加新 Tool、新平台 Adapter 或视觉模型。
- 不扩展任务的六轮预算。

## Contract 兼容性

新增 `agent-tool-call.schema.json`，`AgentDecision` 向后兼容地增加可选 `repair_count`。
`run_tool` 的参数验证从宽松收紧为严格；这会拒绝以前可能被 Runtime 接受的不完整模型输出，
但不改变已有有效 ToolCall 的执行语义。Agent Preview 尚未作为稳定对外 API，因此保持
Schema `1.0.0`，并通过 Provider 的一次修复降低兼容影响。

## 风险

- 部分 OpenAI-compatible 供应商可能忽略修复指令；第二次仍无效时必须确定失败。
- 失败报告可能持久化模型参数；只对通过 allowlist 和参数 Contract 的决策保留完整证据。
- 额外修复请求会增加延迟和 token 消耗，严格限制为一次。

## 里程碑

1. Contract 和回归用例先行。
2. Runtime 参数校验与 Provider 有界修复。
3. 失败 step 证据保留。
4. 定向、全量验证与文档回写。
