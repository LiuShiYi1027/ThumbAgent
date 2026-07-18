# ITER-0008 Retrospective

> 状态：Active
> 更新日期：2026-07-08

## 实际交付

- 新增 `mobile_agent.cli.task_report` CLI 模块。
- 新增 `render_task_report(task, events)`，将 TaskRun/Event 渲染为终端报告。
- CLI 支持从本地 Runtime API 查询 `GET /v1/tasks/{task_id}` 和 `GET /v1/tasks/{task_id}/events`。
- README 增加 CLI 使用方式。
- 新增报告视图测试，覆盖成功任务和失败任务。

## 验收结果

- 定向测试 `runtime.tests.test_task_report_cli` 2 tests OK。
- 全量 `make check` 70 tests OK，lint/typecheck OK。
- `git diff --check` OK。

## 计划偏差

- 本迭代按计划没有实现桌面 GUI。CLI 先作为产品视图原型，后续桌面端可复用同样的信息结构。

## 有效做法

- 报告按“概要、步骤、证据、事件、失败”分组，适合后续映射到桌面端卡片。
- 报告只展示摘要证据，不展开完整 Observation、截图或 UI tree，降低信息噪音和敏感数据风险。

## 问题与根因

- CLI 查询依赖 Runtime 仍在运行，且任务仍在进程内 Store 中。
- 目前没有真实桌面端视图，用户仍需通过终端查看报告。

## 长期文档回写

- README 已记录 CLI 用法。
- 本迭代未改变 Contract、安全模型或持久化语义，不需要 ADR。

## 后续行动

- 下一步可做桌面端任务报告卡片，或先做 SQLite Task Store 持久化，让 CLI/桌面端能查看历史任务。
