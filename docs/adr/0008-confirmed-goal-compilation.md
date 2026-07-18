# ADR-0008: 两阶段目标编译与显式确认

- Status: Accepted
- Date: 2026-07-14
- Deciders: Mobile Agent Team

## Context

真机对照显示，“进入蓝牙设置页面”这类短目标比带有明确中间意图的描述更容易让 Planner
遗漏导航步骤。ITER-0029 已允许调用方独立提供成功条件，但如果 Runtime 直接把另一次模型调用
生成的条件视为权威，只是把同一个信任问题前移。

## Decision

- 新增无设备副作用的 `GoalCompiler`，将原始自然语言编译为 `AgentGoalSpec` 草案。
- GoalSpec 包含原始目标、增强后的执行目标、可选成功条件、假设、置信度和编译来源。
- 模型生成的 GoalSpec 一律要求显式确认；未确认不能进入 Agent Runner。
- 确认后，Planner 使用 `execution_goal` 动态规划，TaskRun 仍以 `source_goal` 作为用户目标并保存
  完整 GoalSpec 供审计。
- 编译只描述意图和最终状态，不生成或回放固定 ToolCall 路径。
- 旧 `agent.run` 请求保持兼容，可继续直接传 `goal` 和调用方成功条件。

## Consequences

- 短目标可以在执行前补全为更清晰的任务语义，同时用户能看到模型做出的假设。
- 编译会增加一次模型调用；用户可以选择跳过编译直接运行。
- 成功条件可能为空：Compiler 不确定时必须暴露不确定性，不能编造脆弱的 Activity 或 Selector。
- Web 和外部调用方必须将“模型草案”和“已确认条件”清楚区分。

## Alternatives Considered

- 直接把原始目标交给 Planner：兼容保留，但短目标稳定性不足。
- 编译后自动执行：缺少用户确认，模型可能改变目标含义或生成错误验收条件。
- 输出固定动作计划：对京东、抖音等高频改版 App 缺乏泛化能力，与目标驱动路线冲突。

## Follow-up

- 为 Skill、企业策略和版本化场景提供非模型 GoalSpec 来源。
- 增加组合验证器和平台结构化状态验证器。
- 评估 GoalSpec 的持久化草稿与修改历史。
