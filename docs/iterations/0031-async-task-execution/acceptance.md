# ITER-0031 Acceptance

> 状态：Completed
> 更新日期：2026-07-14

- [x] 异步提交返回 HTTP 202 和稳定 task_id，不等待完整 Agent 任务。
- [x] 同步 `agent.run` 端点行为保持兼容。
- [x] 执行状态至少覆盖 queued、running、cancelling、succeeded、failed、cancelled。
- [x] 每个已完成 Agent round 立即生成有序 `task.step_completed` 事件。
- [x] 排队任务取消后不调用 Planner、Adapter 或 Tool，并生成 cancelled TaskRun。
- [x] 运行任务在安全边界停止，已完成动作不被伪装成已撤销。
- [x] 同一 Idempotency-Key + 同一请求复用 task_id；不同请求返回 409。
- [x] SQLite 保存执行状态和实时事件，迁移可重复执行。
- [x] Runtime 重启将非终态任务标记为中断，不自动重放设备动作。
- [x] Web 展示执行状态、实时事件和取消按钮。
- [x] `make check` 全量通过（165 tests）。
- [x] 本地 Runtime API/Web 运行态验证完成。

## 运行态证据

- 隔离数据目录：`/tmp/mobile-agent-iter0031`，Runtime 监听 `127.0.0.1:8876`。
- 异步提交立即返回 HTTP 202 和 `task_3ea4e96d92744c268e838b121269c08d`。
- 使用不存在的测试 device_id，执行随后确定性失败为 `DEVICE_NOT_FOUND`，证明提交请求未被同步阻塞。
- 持久化事件顺序为 queued → started → step_completed → completed，sequence 为 1–4。
- 使用同一 Idempotency-Key 重试后返回相同 task_id，没有产生第二条执行。
- `/ui` 已包含异步提交、实时事件和取消入口。本次未重复调用付费模型或执行真机写动作。
