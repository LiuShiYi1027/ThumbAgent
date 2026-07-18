# ITER-0036 Acceptance

> 状态：Completed
> 更新日期：2026-07-15

- [x] 输入只允许 1–2000 行和固定最低日志级别。
- [x] Android 使用无 Shell 的固定参数数组，不接受自由格式 logcat/ADB 参数。
- [x] `logs.collect@1` 风险为 Medium，未确认时在采集前拒绝。
- [x] Capability 缺失、设备离线和 Adapter 失败使用稳定领域错误。
- [x] 日志经过常见标识符/秘密脱敏，Artifact 最大 1 MiB。
- [x] REST、Web 和 CLI 不内联或打印日志原文。
- [x] Skill 经注册 Tool、Policy、Device Session 和 Lease 执行。
- [x] 通用 Action Tool 入口不能直接调用日志 Tool。
- [x] 超时和协作式取消沿 ADB Process Runner/asyncio 边界传播。
- [x] 默认测试不依赖真实设备、网络或模型。
- [ ] 持续流式日志、异步诊断 Task 和复现窗口不属于本迭代。
