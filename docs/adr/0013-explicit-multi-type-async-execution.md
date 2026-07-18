# ADR-0013: 异步执行器支持显式注册的多任务类型

- Status: Accepted
- Date: 2026-07-15
- Deciders: Mobile Agent Team

## Context

异步执行器最初只服务 `agent.run`，内部将 `task_type` 硬编码为该值。日志采集已经具备稳定 Skill、
Artifact 和验证语义，但同步请求不能提供排队、取消、Deadline、增量事件和 Runtime 重启恢复状态。
复制一套日志专用队列会造成执行状态、幂等、Session 和 Lease 语义漂移；开放任意 task type/handler
又会形成新的执行逃生口。

## Decision

- 保留单一 `AsyncTaskExecutor`、TaskExecution Store 和串行工作线程。
- `submit` 接受由 Application 层指定的 `task_type`，但执行器只允许代码内显式登记的
  `agent.run` 与 `device.logs.collect`，拒绝客户端或调用方构造的任意类型。
- `TaskExecution` 与 `TaskRun` Contract 兼容性新增 `device.logs.collect`；日志步骤使用
  `kind=diagnostic`、`name=device.logs.collect`，结果引用既有 DeviceLogCaptureResult Contract。
- 新增 `POST /v1/tasks/device.logs.collect/async`，返回 202 并复用 Idempotency-Key、状态/事件查询和
  取消端点。原同步 Skill 端点保持兼容。
- 日志 TaskRunner 在采集前后安全边界检查取消与 Deadline。若取消发生在 ADB 调用中，不强杀
  子进程；调用返回后任务进入 cancelled/timed_out，并保留已经生成的步骤和 Artifact 证据。
- Web 默认使用异步日志任务；CLI 可通过 `--async-task` 显式选择异步提交。

## Consequences

- Agent 与诊断任务共享相同持久化生命周期、重启恢复、幂等、事件、Session 和 Lease 语义。
- Task 报告可展示日志 Artifact、采集大小、截断和脱敏计数，不展示正文。
- 新增 Task 类型仍需同步更新白名单、Contract、TaskRunner、测试和接口映射，不能动态加载 handler。
- 当前单工作线程意味着日志任务与 Agent 任务串行；符合单设备 V1，但不适合后台持续观测。

## Alternatives Considered

- 为日志复制独立队列与表：实现快，但会产生两套取消、恢复和幂等语义。
- 把任意 Skill 自动包装为异步任务：发现方便，但风险、报告和验证结构无法自动保证。
- 直接实现持续 logcat 流：尚未解决并发读取、轮转、长租约和中途 Artifact 一致性。

## Follow-up

- 为后续性能采样评估显式 Task Handler Registry，仍保持代码注册和 Contract-first。
- 设计持续诊断采集时明确只读并发策略、Artifact 分片/轮转和强制停止后的 outcome。
- 评估是否将同步诊断端点标记为兼容入口，并让桌面端统一采用异步任务。
