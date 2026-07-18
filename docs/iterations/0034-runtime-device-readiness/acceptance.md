# ITER-0034 Acceptance

> 状态：Completed
> 更新日期：2026-07-15

- [x] ADB 缺失或配置路径错误时 Runtime 可以启动，不输出 traceback。
- [x] `/v1/readiness` 在 ready、attention、blocked 状态均返回 HTTP 200 和版本化快照。
- [x] Readiness 区分 Gateway unavailable、无设备、offline、unauthorized、busy 和 ready。
- [x] 每个不可用状态提供稳定错误码、用户消息和 suggested_action。
- [x] Device 数据复用 Device Contract，在线设备携带 Session。
- [x] Busy 设备包含安全 Lease 诊断，且 Web 不允许发起新任务。
- [x] Readiness 检查不执行 Observation、模型调用或设备写动作。
- [x] Web 与 CLI 消费同一 Contract。
- [x] 全量质量检查与隔离 Runtime 验收通过。
