# ITER-0007 Retrospective

> 状态：Active
> 更新日期：2026-07-08

## 实际交付

- 新增 `TaskEvent` 领域对象和版本化 Contract。
- 新增进程内 `InMemoryTaskStore`，保存已完成 `TaskRun` 并生成紧凑事件序列。
- RuntimeService 支持 `get_task` 和 `list_task_events`。
- HTTP API 支持 `GET /v1/tasks/{task_id}` 和 `GET /v1/tasks/{task_id}/events`。
- HTTP Server 改为在进程生命周期内共享 RuntimeService，使任务运行后的查询可用。

## 验收结果

- 定向测试 11 tests OK。
- 全量 `make check` 68 tests OK，lint/typecheck OK。
- `git diff --check` OK。

## 计划偏差

- 本迭代刻意没有实现 SQLite 持久化和 Runtime 重启恢复，以避免在没有迁移设计的情况下引入隐式持久化。

## 有效做法

- 先做进程内 Store，验证 Task/Event 的 API 形态，再进入持久化，降低了设计反悔成本。
- Event payload 保持紧凑，只记录状态、步骤和错误码，没有复制完整 Observation 或 UI 内容。
- 查询缺失任务使用 `TASK_NOT_FOUND`，让客户端能明确区分“任务失败”和“记录不存在”。

## 问题与根因

- Store 仍然是进程内状态，Runtime 重启后任务记录会消失。
- 当前事件是在任务完成后由 Store 派生生成，不是实时流式事件；桌面端暂时无法展示执行中进度。

## 长期文档回写

- README 和 V1 技术方案已标注进程内 Store 限制。
- 错误规范已登记 `TASK_NOT_FOUND`。
- 未引入持久化，因此不需要数据迁移或 ADR。

## 后续行动

- 下一步建议进入 ITER-0008：正式 Task Store 持久化与迁移，或先做桌面端任务报告视图。若选择持久化，必须按数据与迁移规范新增 SQLite migration。
