# ITER-0037 Async Diagnostic Task

> 状态：Completed
> 日期：2026-07-15

## 背景

ITER-0036 已验证有界日志 Skill，但同步调用缺少统一排队、取消、实时状态、幂等和重启恢复。现有
AsyncTaskExecutor 又只接受 `agent.run`，不能安全承载诊断任务。

## 目标

- 将异步执行器泛化为代码内显式允许的多任务类型，不开放任意 handler。
- 将 `device.logs.collect` 接入 TaskExecution、TaskRun、增量事件、Deadline、Session 和 Lease。
- 新增返回 202 的异步 REST 入口，保留同步 Skill 兼容端点。
- Web 默认异步提交日志任务，并在统一执行/报告视图显示进度与 Artifact 摘要。
- CLI 支持可选异步提交，返回 task_id 后可使用通用报告与状态 API。

## 非目标

- 不实现持续流式 logcat、后台常驻采集或多设备并行。
- 不允许客户端指定 task_type、Python handler、Tool allowlist 或任意 Skill ID。
- 不改变日志采集范围、脱敏、Artifact 上限和 Medium 确认要求。
- 不实现性能采样、安装/卸载包或 iOS/鸿蒙 Adapter。

## Contract 兼容性

- TaskExecution/TaskRun 新增 `device.logs.collect` 枚举，TaskRun Step 新增 diagnostic 类型和日志结果
  引用，属于兼容性新增；消费者必须对未知任务/步骤枚举实现 fallback。
- 新增异步 REST 端点，不修改同步日志 Skill 和 Agent 异步端点语义。
- SQLite 继续保存完整 execution/task JSON，表结构未变化，不需要数据库迁移。

## 架构说明

Task Handler 仍由 Runtime 代码显式构造。AsyncTaskExecutor 只负责生命周期和持久化，不解析 Skill
ID、不发现插件、不接收客户端 handler。DeviceLogsTaskRunner 调用既有 deterministic Skill，设备
访问仍经过 Capability、Policy、Gateway、Session 和 Lease。详见 ADR-0013。
