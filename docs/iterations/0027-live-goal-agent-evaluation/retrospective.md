# ITER-0027 Retrospective

> 状态：Active
> 更新日期：2026-07-13

## 实际交付

- 新增 `AgentEvaluationScenario` 与 `AgentEvaluationResult` 公共 Contract。
- 实现只消费 TaskRun 的 `AgentEvaluator`，不访问设备或模型。
- 支持独立前台 App/UI Selector、禁用 Tool、轮次预算和 Policy 违规判定。
- 输出轮次、Tool、页面变化、无进展、模型修复、Policy 和耗时指标。
- 新增 `POST /v1/tasks/{task_id}/evaluate`、CLI 报告和场景 JSON 示例。

## 偏差与问题

原提议中的“轨迹回放”容易被理解为固定动作路径评测，这不适合京东、抖音等高频改版 App。
本迭代将正式评测语义改为“在线动态规划 + 路径无关验收”，历史轨迹只保留确定性工程回归价值。

## 验证结果

- Agent Evaluator/API/CLI 定向测试 10 项通过。
- `make check` 通过：lint、typecheck 和 132 项默认测试全部成功。
- 两份 Schema 和场景示例通过 JSON 语法校验，`git diff --check` 通过。
- 本迭代未对京东或抖音执行真机 E2E，也没有声称已获得这些 App 的泛化数据。

## 后续行动

- 将评测场景与 Agent 执行入口结合，让外部验收条件直接约束 Runtime 的最终成功状态。
- 增加多条件验证器、初始状态和 App/版本/登录态环境元数据。
- 在明确授权和低风险边界内，再建立设置、京东和抖音的小型在线场景集。
