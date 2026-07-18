# ADR-0009: 持久化异步任务执行与协作式取消

- Status: Accepted
- Date: 2026-07-14
- Deciders: Mobile Agent Team

## Context

Agent 任务包含多轮设备 Observation 和模型请求，真机链路可能持续数分钟。同步 HTTP 请求让 Web
页面长时间没有反馈，也无法可靠表达排队、运行、取消中和 Runtime 重启等状态。已有 TaskStore
只在任务结束后一次性保存 TaskRun 和派生事件，不能作为实时状态源。

## Decision

- 保留现有同步 `POST /v1/tasks/agent.run`，新增返回 `202 Accepted` 的
  `POST /v1/tasks/agent.run/async`，避免静默改变已有 API 语义。
- 新增独立 `TaskExecution` Contract，表达 `queued → running → succeeded/failed`，以及
  `queued/running → cancelling/cancelled` 状态。
- V1 使用 Runtime 内单工作线程串行消费异步队列，符合单台 Android 设备边界，并避免异步任务
  互相争用设备和 Planner。
- Runner 在每轮安全边界检查取消标记；取消只能阻止后续工作，不能撤销已经发送的设备动作。
- 执行状态与增量 TaskEvent 写入 SQLite；终态 TaskRun 继续写入原 TaskStore，报告 Contract 保持
  单一真源。
- Runtime 重启时，排队任务转为确定失败；已运行或取消中的任务转为 `TASK_INTERRUPTED` 且
  `unknown_outcome`，不自动重放 ToolCall。
- 异步创建支持 `Idempotency-Key`。同键同请求返回原 task_id，同键不同请求返回冲突。
- Web V1 使用 REST 轮询读取执行状态和事件；事件历史足以重建当前状态，不要求页面保持长连接。

## Consequences

- 用户提交后立即看到 task_id、状态和逐轮事件，并可请求取消。
- SQLite 增加 `task_executions` 与 `task_execution_events`，通过迁移 0002 创建。
- 当前运行中的模型 HTTP 或 ADB 调用不会被强制中断，取消状态可能短暂保持 `cancelling`；这样可
  避免把已经发生的设备副作用误报为未发生。
- 同步兼容端点仍可被外部调用方直接使用，它不参与异步队列调度；V1 Web 只使用异步端点。
- REST 轮询存在固定查询开销，但实现简单、可恢复，后续可在不改变执行语义的前提下增加 SSE 或
  WebSocket 传输。

## Alternatives Considered

- 仅把同步调用放入 HTTP 后台线程：不能产生真实增量事件，也无法持久化取消和重启状态。
- 直接把原端点改为 202：属于破坏性 API 变化，会影响现有 CLI 和调用方。
- 强制取消线程或底层进程：设备动作结果可能未知，容易造成重复副作用或错误审计。
- 首版引入外部消息队列：超出本地单设备 V1 的复杂度和部署边界。

## Follow-up

- 将同步兼容端点也纳入统一设备租约，彻底避免跨入口并发写设备。
- 根据实际事件频率评估 SSE/WebSocket，保留 REST 作为状态重建入口。
- 增加任务 deadline、模型请求级可取消 transport 和更细粒度 unknown-outcome 证据。
