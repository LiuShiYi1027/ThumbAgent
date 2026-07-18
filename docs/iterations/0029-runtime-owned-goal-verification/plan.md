# ITER-0029 Runtime-owned Goal Verification

> 状态：Completed
> 日期：2026-07-13

## 背景

ITER-0028 真机对照中，四项设备目标均已实际达成，但一次任务因模型生成的完成说明缺失而被
标记失败。修复说明字段后，任务仍然依赖模型临时生成 `finish.expected_selector`。模型可以选择
歧义、脆弱或与用户验收口径不一致的 Selector，导致设备已经完成目标但任务产生假阴性。

ITER-0027 已建立路径无关的 `AgentEvaluationScenario`，但它只能在任务结束后评分，不能约束
Runtime 当次任务的最终成功状态。

## 目标

- 定义可复用的 `AgentGoalAcceptance` 公共 Contract。
- `agent.run` 可选接收调用方提供的独立成功条件。
- 模型请求 `finish` 时，由 Runtime 对当前 Observation 验证调用方成功条件。
- 所有指定条件采用 all-of 语义，Selector 必须唯一匹配。
- TaskRun 持久化验收条件与完成来源，Web/CLI 可审计展示。
- 复用同一验收类型扩展在线评测的 Activity 判定。

## 范围

- 前台 app id、Activity 和一个最终 UI Selector。
- 现有 `POST /v1/tasks/agent.run` 的可选 `acceptance` 字段。
- `finish` 的外部验收失败继续作为无副作用 failed round 反馈模型。
- 未传 `acceptance` 时完全保留现有模型 `finish` 验证语义。

## 非目标

- 不从自然语言自动生成验收条件。
- 不生成或回放固定动作路径。
- 不实现 all-of/any-of 嵌套表达式、OCR 或视觉模型判定。
- 不实现业务 API、数据库或系统服务状态验证器。
- 不在本迭代强制 Web 自然语言输入自动附带设置页规则。
- 不扩展 iOS、鸿蒙、多设备或高风险能力。

## Contract 兼容性

- 新增 `AgentGoalAcceptance` Schema。
- `AgentEvaluationScenario.acceptance` 改为引用该 Schema，并向后兼容新增
  `foreground_activity`。
- TaskRun 新增可选 `goal_acceptance` 与 `completion_source`；旧任务与旧请求继续有效。
- `agent.run` 请求新增可选 `acceptance`，未提供时行为不变。
- 无数据库迁移；SQLite 继续存储完整 TaskRun JSON。

## 风险

- 调用方提供错误验收条件会使正确设备状态无法通过，报告必须明确展示条件来源。
- Activity 在部分 App 中不稳定，因此保持可选，不由 Runtime 自动猜测。
- 单个 Selector 无法表达复杂业务结果，后续需要组合验证器而不是放宽唯一匹配。

## 里程碑

1. Contract、ADR 和失败回归用例。
2. Runtime 权威验收与 TaskRun 审计字段。
3. API、Web/CLI 和在线评测复用。
4. 全量测试与真机验收。
