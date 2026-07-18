# ITER-0006 Tasks

> 状态：Completed
> 更新日期：2026-07-08

| ID | 状态 | Owner | 任务 |
| --- | --- | --- | --- |
| TASK-0006-01 | done | Codex | 定义 `TaskRun` Contract、状态和兼容性结论 |
| TASK-0006-02 | done | Codex | 实现 `TaskRun` / `TaskStep` 领域对象 |
| TASK-0006-03 | done | Codex | 实现 `TaskRunner.run_settings_scroll_navigation` |
| TASK-0006-04 | done | Codex | 接入 RuntimeService 和本地 HTTP API |
| TASK-0006-05 | done | Codex | 覆盖成功报告、策略拒绝报告和 Contract 测试 |
| TASK-0006-06 | done | Codex | 更新 README、迭代索引、验收记录和复盘 |

## 协作备注

- 本迭代只允许包装已有 `settings.scroll_navigate`，不得扩张到通用 Agent Loop。
- 不新增持久化，不修改数据库迁移。
- 不改变现有 Skill 的安全策略和确认语义。
- 若要引入异步 `/v1/tasks`、事件流或任务恢复，需要新迭代和 ADR。

## 进展记录

- 2026-07-08：新增 `contracts/schemas/task-run.schema.json`，作为新增兼容 Contract，不破坏既有 API。
- 2026-07-08：新增 `TaskRun`、`TaskStep` 和 `TaskRunner`，第一条任务类型为 `settings.scroll_navigate`。
- 2026-07-08：RuntimeService 增加同步任务运行包装，本地 API 增加 `POST /v1/tasks/settings.scroll_navigate/run` 预览端点。
- 2026-07-08：新增 `runtime/tests/test_task_runner.py`，覆盖成功报告、确认缺失导致的策略失败报告、Contract 版本和同步包装。
- 2026-07-08：全量质量门禁通过（66 tests、lint、typecheck），`git diff --check` 通过。
