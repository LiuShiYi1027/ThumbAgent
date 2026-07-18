# ITER-0008: Task Report View

> 状态：Completed
> 更新日期：2026-07-08
> Owner：Codex

## 目标

在已有 `TaskRun` 和 `TaskEvent` 基础上，提供第一版用户可见的任务报告视图，让任务执行结果不只停留在 JSON Contract，而能被人直接阅读。

本迭代要证明：

> Mobile Agent 的一次任务执行可以被展示为清晰的目标、状态、步骤、证据和失败原因。

## 背景

ITER-0006 和 ITER-0007 建立了任务报告、任务查询和事件日志，但返回内容仍偏机器接口。产品要更像 AI-native Skills 平台，需要有一层“给用户看的执行解释”。

桌面端最终会是核心形态，但当前仓库还没有桌面 UI 工程。为避免过早引入前端依赖，本迭代先实现 CLI 报告视图，作为桌面端任务报告卡片的字段原型。

## 范围

- 新增 CLI 报告渲染器：
  - 输入 `TaskRun` 和 `TaskEvent`。
  - 输出终端友好的文本报告。
- 新增 CLI 命令：
  - `python -m mobile_agent.cli.task_report <task_id>`
  - 从本地 Runtime API 拉取 task 和 events。
- 报告包含：
  - task id、类型、状态、设备、目标、时间。
  - 步骤列表。
  - 证据摘要。
  - 事件时间线。
  - 失败原因和建议动作。
- 报告避免输出完整 Observation、截图、UI tree 或敏感输入。
- 补齐单元测试和质量门禁。

## 非目标

- 桌面 GUI。
- 交互式 TUI。
- 实时流式进度。
- 任务创建向导。
- 持久化任务历史。
- 新增真实设备动作。

## 安全边界

- 报告视图只渲染 TaskRun 的摘要字段和紧凑事件。
- 不读取 Artifact 文件内容。
- 不展开完整 UI hierarchy、截图路径之外的文件内容或敏感输入。
- CLI 不绕过 Runtime API 的本地访问边界。

## 依赖

- ITER-0006 的 `TaskRun`。
- ITER-0007 的 `TaskEvent` 和任务查询 API。
- 现有 Python 标准库 HTTP client。

## 风险

- 报告如果过度展开 JSON，会让用户淹没在机器细节里。
- 报告如果太抽象，又无法作为诊断依据。
- CLI 从 API 查询时依赖当前 Runtime 仍在运行且任务仍在进程内 Store 中。

## 里程碑

1. 实现报告渲染函数。
2. 实现 CLI 查询命令。
3. 覆盖成功报告和失败报告测试。
4. 更新 README、迭代索引和复盘。
5. 全量质量门禁通过。

## 完成条件

以 [acceptance.md](./acceptance.md) 的必选验收全部通过为准。
