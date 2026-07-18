# ITER-0032 Retrospective

> 状态：Completed
> 更新日期：2026-07-14

## 实际交付

- 新增进程内 DeviceLeaseManager，统一同步/异步 Agent、Tool、Skill 与确定性任务的设备写所有权。
- Agent 请求增加默认 600 秒、范围 1–1800 秒的 deadline_seconds。
- TaskExecution 持久化 deadline_seconds/deadline_at，并增加 timed_out 终态。
- TaskRun 保存 deadline 和 TASK_DEADLINE_EXCEEDED，Web/CLI 同步展示。
- Deadline 与租约使用可注入 monotonic clock，普通测试不依赖真实等待。

## 验证结果

- `make check` 通过：lint、类型检查和 173 个测试。
- 覆盖同步/异步/直接 Tool 租约冲突、过期不抢占、释放后重入和运行中取消释放。
- 覆盖 deadline 在动作前触发、动作验证后触发、timed_out 证据和无效预算前置拒绝。
- 隔离 HTTP Runtime 验证 202 提交、deadline_at 持久化、400 参数拒绝及 Web 终态展示。

## 偏差与后续

- 租约当前是单 Runtime 进程内能力，尚不能协调两个同时启动的 Runtime 进程。
- 租约冲突的异步任务当前明确失败，不进行可能掩盖设备状态的自动等待或重试。
- Deadline 不强杀进行中的模型或 ADB 调用，因此调用超时返回前 UI 仍可能显示 running。
- 下一步应增加 Runtime 单实例锁和 Device Session，将进程级协调扩展到启动与重连边界。
