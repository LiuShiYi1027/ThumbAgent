# ITER-0050 Acceptance

> 文档状态：Active
> 迭代状态：Completed
> 更新日期：2026-08-02

- [x] 桌面端可输入自然语言目标并选择设备；只有 readiness 为 `ready` 的设备可以提交。
- [x] 提交前确认面板展示目标、目标设备和 Medium 风险动作说明；用户显式确认后才提交
      `confirmed=true`，取消确认不产生任何请求。
- [x] 提交成功后立即获得 task_id 并进入执行视图；双击或重试不产生重复任务
      （Idempotency-Key 由 Rust 生成并复用）。
- [x] 执行中时间线展示 queued/running/cancelling 状态与逐轮 `agent.round` 进展，失败轮次
      展示错误码；轮询间隔有界，离开视图后停止轮询。
- [x] 取消按钮触发 `POST /v1/task-executions/{id}/cancel`，任务在安全边界停止并展示
      `cancelled` 终态。
- [x] 终态后报告展示目标、状态、`completion_source`、每轮 observation 摘要、decision
      （tool 与参数）、action_result 与错误信息。
- [x] 设备被其他任务占用（DEVICE_LOCKED）、模型不可用（MODEL_UNAVAILABLE）等失败有明确
      错误展示，不静默成功。
- [x] POST 桥仅允许白名单路径，其他路径与方法被拒绝（Rust 测试覆盖）；token 不出 Rust 层。
- [x] `contracts/generated` 新增类型由脚本生成；`make check` 与 `make check-desktop`
      全部通过。
- [x] 设备 E2E：在一台已授权 Android 设备上完成一次自然语言 Agent 任务（确认 → 执行 →
      时间线 → 报告），并完成一次中途取消。
