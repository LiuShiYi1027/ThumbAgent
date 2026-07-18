# ITER-0032 Acceptance

> 状态：Completed
> 更新日期：2026-07-14

- [x] 同一 device_id 的第二个写 Owner 在设备动作前收到 DEVICE_LOCKED。
- [x] 同步 Agent、异步 Agent、直接 Tool 和 Skill 共享同一租约边界。
- [x] 租约即使超过期限也不会自动抢占；原 Owner 释放后才能重新取得。
- [x] 异常、失败、取消和超时终态均释放租约。
- [x] deadline_seconds 在输入边界校验，范围为 1–1800 秒。
- [x] 异步 deadline 从 running 开始，TaskExecution 持久化 deadline_at。
- [x] deadline 在首轮前触发时不执行 Observation 或设备动作。
- [x] deadline 在已验证动作后触发时保留步骤证据，不派发下一动作。
- [x] Web/CLI 展示 deadline，Web 将 timed_out 作为终态。
- [x] `make check` 全量通过（173 tests）。
- [x] 隔离 Runtime HTTP 冒烟验证完成。

## 运行态证据

- 隔离 Runtime：`127.0.0.1:8877`，数据目录 `/tmp/mobile-agent-iter0032`。
- 合法请求携带 `deadline_seconds=5`，HTTP 202 返回
  `task_51e003d667d34b558f9756e0e4dde688`。
- TaskExecution 从 queued 进入 running 后生成 `deadline_at`，终态查询保留 5 秒预算。
- `deadline_seconds=0` 在排队和设备动作前返回 HTTP 400 / `INVALID_ARGUMENT`。
- Web 资源包含 deadline 展示和 timed_out 终态处理。
- 租约竞争、取消释放和 deadline 释放使用 Fake Adapter 确定性验证，未重复调用付费模型。
