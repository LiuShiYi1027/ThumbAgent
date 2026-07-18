# ITER-0013 Retrospective

> 状态：Active
> 更新日期：2026-07-09

## 实际交付

- 新增 Agent Planner 抽象、`AgentDecision` 和 `AgentObservationSummary`。
- 新增 deterministic `RuleBasedPlanner`，只支持进入显示/亮度页面的安全目标族。
- 新增 `AgentRunner`，完成一轮 Observe–Plan–Act，并输出 `agent.run` TaskRun。
- 新增 Runtime/API 入口：`POST /v1/tasks/agent.run`。
- CLI/Web 报告展示 agent round 的决策摘要。
- README 与技术方案记录 Agent Loop Preview 边界。

## 验收结果

- 定向测试 19 tests OK。
- 全量 `make check` 86 tests OK，lint/typecheck OK。

## 计划偏差

- 未实现真实 LLM Provider，符合本迭代范围。
- 未新增独立 Agent Contract；当前 preview 决策只作为 `TaskRun.steps[].result` 内部结构保存，待语义稳定后再提升为公共 Schema。

## 有效做法

- 先用 deterministic Planner 固定边界，避免把不稳定模型行为引入设备动作链路。
- Runner 对 Planner 输出再次做 allowlist 校验，保持“模型输出不可信”的安全模型。
- 复用现有 `settings.scroll_navigate` Skill、Task Store、CLI/Web 报告，减少跨模块变更。

## 问题与根因

- Preview 目前只有一轮，且只支持显示/亮度目标；这是刻意范围控制，不代表最终 Agent 能力。
- 中文真实设备仍可能因厂商设置页差异失败；后续应由多候选 selector 和 LLM Planner 处理，而不是继续硬编码 demo。

## 长期文档回写

- README 已记录 `agent.run` 入口。
- 技术方案已记录 Agent Loop Preview 与未来 LLM Planner 的替换边界。
- 本迭代未改变存储 Schema、安全信任模型或平台 Adapter 边界，不需要 ADR。

## 后续行动

- 下一迭代可以引入 LLM Planner Provider 接口和 mock structured-output 校验。
- 也可以先把 Web UI 增加自然语言任务输入框，让用户从产品上发起 `agent.run`。
