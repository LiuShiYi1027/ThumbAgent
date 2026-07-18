# ITER-0038 Acceptance

> 状态：Completed
> 更新日期：2026-07-15

- [x] 性能数据使用版本化、平台无关 Contract 和明确单位。
- [x] Android 只执行五组固定只读参数数组，不接受自由格式命令。
- [x] Artifact/API/事件不包含 dumpsys 原文、进程名或应用明细。
- [x] `performance.snapshot@1` 登记 Low 风险、safe 幂等和验证要求。
- [x] Tool 经 Capability、Policy、Session、Lease 和 Device Gateway 执行。
- [x] 成功、输入拒绝、Capability 缺失、Policy 拒绝、解析失败、离线/取消得到测试。
- [x] 同步 Skill、异步 Task、Web、CLI 和任务报告消费同一 Result Contract。
- [x] 异步任务支持状态、事件、Idempotency-Key、取消、Deadline 和重启恢复。
- [x] 第二个诊断任务复用内部 DiagnosticTaskRunner，未开放动态 handler。
- [ ] 应用级指标、连续采样和时序比较不属于本迭代。
