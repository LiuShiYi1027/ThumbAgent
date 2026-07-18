# ITER-0007: Task Store & Event Log

> 状态：Completed
> 更新日期：2026-07-08
> Owner：Codex

## 目标

在 ITER-0006 的 `TaskRun` 报告基础上，增加进程内 Task Store 和紧凑 Event Log，让客户端能在同一个 Runtime 生命周期内查询已完成任务和任务事件。

本迭代要证明：

> 任务不只是一次 HTTP 响应，也可以成为桌面端或 AI-native Client 可查询、可展示、可追踪的本地执行记录。

## 背景

ITER-0006 已经将 `settings.scroll_navigate` 包装为结构化 `TaskRun`。但报告只存在于当次返回值中，无法通过 `task_id` 再查询，也没有适合 UI 展示进度和结果的事件序列。

正式异步任务系统需要持久化、恢复、取消、确认回调和设备锁；这会显著扩大范围。因此本迭代先落进程内 Store/Event Log，验证查询形态和事件 Contract。

## 范围

- 定义 `TaskEvent` Contract。
- 实现进程内 `InMemoryTaskStore`：
  - 保存已完成 `TaskRun`。
  - 为每个任务生成紧凑事件序列。
  - 缺失任务返回结构化 `TASK_NOT_FOUND`。
- RuntimeService 增加：
  - `get_task`
  - `list_task_events`
- 本地 HTTP API 增加：
  - `GET /v1/tasks/{task_id}`
  - `GET /v1/tasks/{task_id}/events`
- HTTP Server 在进程生命周期内共享同一个 RuntimeService，避免每次请求新建 Runtime 导致任务状态丢失。
- 补齐单元测试、Contract 测试和质量门禁。

## 非目标

- SQLite 持久化和迁移。
- Runtime 重启后恢复任务。
- 异步队列、任务取消、暂停、恢复和确认回调。
- WebSocket/SSE 事件推送。
- 多设备并行调度和设备锁。
- 新增真实设备动作。

## 安全边界

- Store 只保存结构化 TaskRun 和紧凑事件，不保存密钥、验证码、密码或完整敏感 UI 文本。
- Event payload 只包含任务类型、目标摘要、步骤状态、错误码等最小信息。
- 查询接口只暴露本地 Runtime 已授权 API 内的任务记录。
- Store 不改变 Skill/Tool/Policy 执行语义。

## 依赖

- ITER-0006 的 `TaskRun` 和同步任务运行端点。
- 现有 RuntimeService 和本地 HTTP API 认证机制。

## 风险

- 进程内 Store 容易被误解为持久化能力，因此必须在 README 和技术方案里明确限制。
- Event payload 若放入完整 Skill 结果，会造成 UI 内容和 Artifact 引用重复扩散，因此只保留紧凑摘要。
- Runtime 单例化需要避免破坏现有测试和本地 API 行为。

## 里程碑

1. 定义 `TaskEvent` Contract。
2. 实现 `InMemoryTaskStore`。
3. 接入 RuntimeService 查询方法。
4. 接入 HTTP GET 查询端点并共享 Runtime 实例。
5. 覆盖成功查询、事件序列、缺失任务和 Contract 测试。
6. 更新 README、技术方案、错误码和迭代索引。

## 完成条件

以 [acceptance.md](./acceptance.md) 的必选验收全部通过为准。
