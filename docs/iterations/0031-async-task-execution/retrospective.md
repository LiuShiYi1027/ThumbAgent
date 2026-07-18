# ITER-0031 Retrospective

> 状态：Completed
> 更新日期：2026-07-14

## 实际交付

- 新增 `TaskExecution` Contract、异步任务资源 API 和 SQLite 0002 迁移。
- 新增单工作线程执行器、逐轮持久化事件、协作式取消和 Runtime 重启中断恢复。
- 新增 Idempotency-Key：同请求复用 task_id，不同请求明确冲突。
- Agent Runner 支持外部 task_id、步骤回调与取消检查，终态 TaskRun 仍由原 TaskStore 保存。
- Web 默认异步提交并轮询状态/事件，提供取消按钮，终态后自动切换到完整任务报告。

## 验证结果

- `make check` 通过：lint、类型检查和 165 个测试。
- 异步相关测试连续运行 5 次通过，覆盖提交、事件顺序、取消、幂等和 SQLite 重启恢复。
- 隔离 Runtime 冒烟验证返回 202，并产生完整 queued → completed 事件链。
- 幂等 HTTP 重试复用了 `task_3ea4e96d92744c268e838b121269c08d`。

## 偏差与后续

- 原计划中的“实时”采用 1.2 秒 REST 轮询，而不是 SSE/WebSocket；REST 仍是可重建状态的真源。
- 取消不会强杀正在进行的模型 HTTP 或 ADB 调用，因此可能短暂显示 `cancelling`，但不会派发下一步动作。
- 同步兼容端点尚未纳入异步执行器的设备租约；外部调用方不应与 Web 异步任务并发写同一设备。
- 本次没有再次消耗付费模型或执行真机写动作；上一迭代已验证 Agent 真机闭环，本迭代聚焦执行编排。
- 下一步优先建立统一设备租约与 deadline，再根据真实事件频率决定是否增加 SSE。
