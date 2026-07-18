# ITER-0017 Tasks

> 状态：Active
> 更新日期：2026-07-09

| ID | 状态 | Owner | 任务 |
| --- | --- | --- | --- |
| TASK-0017-01 | done | Codex | 新增 `ModelProviderSettings` |
| TASK-0017-02 | done | Codex | 新增 `SecretResolver` 端口 |
| TASK-0017-03 | done | Codex | 实现 `build_planner_from_settings` |
| TASK-0017-04 | done | Codex | 补齐配置门测试 |
| TASK-0017-05 | done | Codex | 更新 README、技术方案和验收记录 |

## 进展记录

- 2026-07-09：启动 Model Provider Configuration Gate 迭代。
- 2026-07-09：新增 `ModelProviderSettings`、`SecretResolver` 和 `build_planner_from_settings`。
- 2026-07-09：默认配置返回 `RuleBasedPlanner`，显式启用才构造 OpenAI-compatible Planner。
- 2026-07-09：补齐 fake secret resolver 测试，确认错误不泄露原始 API key。
