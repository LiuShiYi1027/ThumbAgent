# ITER-0035 Acceptance

> 状态：Completed
> 更新日期：2026-07-15

- [x] DeviceInspection 使用版本化 Contract，并复用 DeviceAvailability 与 Device Contract。
- [x] V1 八项能力均有风险、幂等、验证、要求和限制元数据。
- [x] Tool Registry 的风险与幂等性从 Capability Catalog 派生。
- [x] ready、busy、offline/unauthorized 能力分别映射为 available、temporarily_unavailable、unknown。
- [x] Medium 风险能力明确展示 confirmation_required。
- [x] Inspection 不执行 Observation、模型调用或设备写动作。
- [x] 未发现设备使用 DEVICE_NOT_FOUND，Gateway 不可用保持既有领域错误。
- [x] Web/CLI 消费同一 Inspection Contract。
- [x] 全量质量检查和真机只读验收通过。
