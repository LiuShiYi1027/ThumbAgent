# ITER-0020 任务拆解

> 状态：Completed
> 日期：2026-07-10

## 任务

- [x] 新增 `UnavailablePlanner`，用于保留显式模型不可用失败。
- [x] `RuntimeService` 支持注入 Planner。
- [x] 新增 `build_runtime_planner`，将模型配置映射为 Planner 与运行状态。
- [x] 默认 Runtime 接入模型 Planner 工厂。
- [x] 扩展模型 Provider 状态，展示 `disabled/active/unavailable/configured`。
- [x] 增加 active、unavailable 和任务失败不触发动作的测试。
- [x] 更新 README、技术方案和迭代索引。

## 状态语义

- `disabled`：模型配置关闭，使用 `RuleBasedPlanner`。
- `active`：模型配置开启且密钥引用可解析，Runtime 使用 OpenAI-compatible Planner。
- `unavailable`：模型配置开启但不可用，Agent 任务返回 `MODEL_UNAVAILABLE`。
- `configured`：仅用于手动构造 Runtime 且未提供运行态时的中间状态。
