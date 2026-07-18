# ITER-0007 Tasks

> 状态：Completed
> 更新日期：2026-07-08

| ID | 状态 | Owner | 任务 |
| --- | --- | --- | --- |
| TASK-0007-01 | done | Codex | 定义 `TaskEvent` Contract 和兼容性结论 |
| TASK-0007-02 | done | Codex | 实现进程内 `InMemoryTaskStore` |
| TASK-0007-03 | done | Codex | RuntimeService 增加任务和事件查询方法 |
| TASK-0007-04 | done | Codex | HTTP API 增加任务和事件查询端点，并共享 Runtime 实例 |
| TASK-0007-05 | done | Codex | 补齐成功查询、事件序列、缺失任务和 Contract 测试 |
| TASK-0007-06 | done | Codex | 更新 README、技术方案、错误码、迭代索引和复盘 |

## 协作备注

- 本迭代不做 SQLite 持久化，因此不需要迁移文件。
- Store 生命周期等于 Runtime 进程生命周期。
- 不新增真实设备动作，不扩大 V1 安全边界。

## 进展记录

- 2026-07-08：新增 `contracts/schemas/task-event.schema.json`。
- 2026-07-08：新增 `InMemoryTaskStore`，保存 `TaskRun` 并生成 `task.started`、`task.step_completed`、`task.completed` 三类事件。
- 2026-07-08：RuntimeService 增加 `get_task` 和 `list_task_events`；HTTP API 增加 `GET /v1/tasks/{task_id}` 和 `GET /v1/tasks/{task_id}/events`。
- 2026-07-08：HTTP Server 改为进程生命周期内共享 RuntimeService，支持任务创建后查询。
