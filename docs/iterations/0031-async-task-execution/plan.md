# ITER-0031 Async Task Execution & Live Events

> 状态：Completed
> 日期：2026-07-14

## 背景

ITER-0030 真机任务从目标编译到完成需要数分钟。同步 `agent.run` 让 Web 在整个执行期间只能显示
“运行中”，无法逐轮展示进展，也没有取消入口。

## 目标

- 新增不破坏同步 API 的异步 Agent 任务提交入口。
- 持久化 queued、running、cancelling 与终态执行状态。
- 每轮结束后立即产生可查询的增量事件。
- 支持排队任务立即取消、运行任务在安全边界协作式取消。
- Web 展示实时状态、事件与取消动作。
- Runtime 重启不自动重放未完成设备动作。

## 范围

- 单台 Android 设备、单 Runtime 工作线程。
- REST 轮询状态和事件。
- SQLite 迁移、Idempotency-Key 与同步端点兼容。

## 非目标

- 不实现多设备并行调度、优先级队列或分布式任务系统。
- 不通过强杀线程假装撤销已发出的设备动作。
- 不在本迭代增加 SSE、WebSocket 或桌面系统通知。
- 不扩展新的 Tool、Skill、iOS 或鸿蒙 Adapter。

## 风险

- 模型或 ADB 阻塞期间取消只能等待安全边界。
- 同步兼容端点暂未纳入异步执行器的统一设备租约。
- 事件写入失败必须使执行明确失败，不能只在 UI 丢失进度。

## Contract 与迁移

- 新增 `TaskExecution` Schema 和三个异步执行资源端点。
- TaskEvent 增加 queued、cancel_requested 事件。
- TaskRun 增加 cancelled 终态并允许零步骤排队取消报告。
- SQLite 迁移 0002 新增执行状态与事件表；旧 TaskRun 数据不改写。
- 同步 `POST /v1/tasks/agent.run` 保持原返回结构和状态码。

## 里程碑

1. Contract、ADR、状态机和 SQLite 迁移。
2. 串行执行器、增量事件、幂等提交与协作式取消。
3. API 与 Web 实时视图。
4. 回归测试、真机验证与复盘。
