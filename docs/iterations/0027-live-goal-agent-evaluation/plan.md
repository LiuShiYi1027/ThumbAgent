# ITER-0027 Live Goal-driven Agent Evaluation

> 状态：Completed
> 日期：2026-07-13

## 背景

固定坐标或固定 ToolCall 序列不能衡量 Agent 在京东、抖音等高频改版 App 中的真实泛化能力。
同一目标可以有多条正确路径，页面结构、文案、弹窗和入口位置也会变化。评测必须让真实模型每次基于
当前 Observation 重新决策，并由模型之外的判定器验证最终结果和过程约束。

## 目标

- 定义版本化、路径无关的 Agent 在线评测场景 Contract。
- 用独立的前台 App 和 UI Selector 验证结果，不只依赖模型 `finish` 自证。
- 评估禁用 Tool、轮次预算和 Policy 违规。
- 统计轮次、Tool 数、页面进展、模型修复次数和耗时。
- 提供 Runtime API 和 CLI 报告边界。

## 核心语义

在线评测是：

```text
版本化目标与约束
  + 真实设备当前状态
  + 待评真实模型逐轮规划
  → TaskRun
  → 独立结果与约束判定
```

不是：

```text
历史动作 1 → 历史动作 2 → 历史动作 3
```

## 范围

- 评测已完成并持久化的 `agent.run` TaskRun。
- 前台 App、单个最终 UI Selector、禁用 Tool 和轮次预算。
- `POST /v1/tasks/{task_id}/evaluate` 和本地 CLI 输出。
- 评测本身不调用设备、不调用模型、不产生副作用。

## 非目标

- 不回放历史设备动作。
- 不用离线轨迹代替真实模型 E2E。
- 本迭代不建立京东、抖音的完整测试集，不扩展高风险操作。
- 不做跨设备、跨模型的批量调度和排行榜。

## Contract 兼容性

新增 `AgentEvaluationScenario` 和 `AgentEvaluationResult` Schema，以及新 API；不修改已有 TaskRun、
ToolCall 或设备动作语义，属于向后兼容增量。无需数据迁移和 ADR。

## 风险

- 单一 UI Selector 可能无法表达复杂业务成功条件，后续需要多条件和平台状态验证器。
- App 的个性化、地区、登录态和 A/B 实验会影响评测可比性，场景后续需记录环境元数据。
- 仅用成功率会掩盖低效或危险路径，必须同时查看预算、无进展和违规指标。
