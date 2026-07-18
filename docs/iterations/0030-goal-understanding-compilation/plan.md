# ITER-0030 Goal Understanding & Compilation

> 状态：Completed
> 日期：2026-07-14

## 背景

真机任务表明，短目标的成功率明显低于包含中间意图的目标。我们需要提升目标表达，而不是把
某个 App 的固定动作路径写死。ITER-0029 已建立 Runtime-owned acceptance，本迭代在其上增加
可确认的目标编译阶段。

## 目标

- 定义公共 `AgentGoalSpec` Contract。
- 提供无设备副作用的目标编译 API。
- 使用可替换 GoalCompiler；真实 Provider 可生成结构化草案。
- Web 展示执行目标、假设、置信度与成功条件，并要求显式确认后运行。
- TaskRun 保存原始目标和已确认 GoalSpec。

## 非目标

- 不生成、保存或回放固定 ToolCall 路径。
- 不让模型草案未经确认成为 Runtime 权威成功条件。
- 不实现 GoalSpec 草稿数据库、多人审批或版本历史。
- 不扩展新的设备动作、iOS、鸿蒙或多设备能力。

## Contract 兼容性

- 新增 `AgentGoalSpec` Schema 和 `POST /v1/goals/compile`。
- `agent.run` 新增可选 `goal_spec` 与 `goal_spec_confirmed`。
- TaskRun 新增可选 `goal_spec`；旧请求和旧任务保持有效。
- SQLite 保存完整 TaskRun JSON，无数据库迁移。

## 里程碑

1. Contract、ADR 与编译器边界。
2. Provider、Runtime 和 API 两阶段闭环。
3. Web 草案审阅与确认执行。
4. 全量测试与真机短目标 E2E。
