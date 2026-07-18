# ITER-0010: Task History List

> 状态：Completed
> 更新日期：2026-07-08
> Owner：Codex

## 目标

在 SQLite Task Store 之上提供最近任务列表，让用户可以先看到历史任务，再选择某个 `task_id` 查看详细报告。

本迭代要证明：

> 用户不需要记住 task id，也能发现最近完成的任务并进入报告。

## 背景

ITER-0009 已经完成任务持久化，ITER-0008 已经完成单任务 CLI 报告。但当前使用链路仍要求用户提前知道 `task_id`。真实产品里，无论 CLI 还是桌面端，都需要一个任务历史列表作为入口。

## 范围

- Store 增加最近任务摘要列表。
- RuntimeService 增加 `list_tasks`。
- HTTP API 增加 `GET /v1/tasks?limit=N`。
- CLI 增加：
  - `python -m mobile_agent.cli.task_list`
- 列表只展示摘要字段，不展开完整 TaskRun。
- 补齐内存 Store、SQLite Store、CLI 和 query 参数测试。

## 非目标

- Cursor 分页。
- 复杂筛选和搜索。
- 删除任务或清理策略。
- 桌面 GUI。
- 实时任务进度。

## 安全边界

- 列表只展示 `task_id`、类型、设备、目标、状态、开始/完成时间等摘要。
- 不展示完整 Observation、UI tree、截图或敏感输入。
- 列表不改变任务执行语义。

## 依赖

- ITER-0009 SQLite Task Store。
- ITER-0008 CLI 报告视图。

## 风险

- 无分页列表不适合大量历史任务，因此 limit 暂时限制在 1 到 100。
- JSON 快照查询只适合最近列表，复杂筛选需后续增加索引字段或拆表。

## 里程碑

1. Store 增加任务摘要列表。
2. Runtime 和 HTTP API 接入列表。
3. CLI 渲染最近任务。
4. 补齐测试和文档。
5. 全量质量门禁通过。

## 完成条件

以 [acceptance.md](./acceptance.md) 的必选验收全部通过为准。
