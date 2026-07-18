# ITER-0035 Retrospective

> 状态：Completed
> 更新日期：2026-07-15

## 实际交付

- 新增 Capability Catalog 作为 V1 能力风险、幂等性、验证要求和限制的单一元数据真源。
- Tool Registry 保留 Tool 映射职责，但不再重复声明 Capability 风险和幂等性。
- 新增 DeviceInspection API、Web 设备能力详情和 CLI 设备检查命令。
- Inspection 复用实时 Device Session 与 Lease 状态，并区分 available、temporarily_unavailable、
  unsupported 和 unknown。

## 验证结果

- `make check` 通过：lint、类型检查和 197 个测试。
- 覆盖 Contract 引用、八项能力、Medium 确认、Tool 元数据一致、busy 与缺失设备。
- 真机只读 API 与 CLI 验收通过，返回 8 项 available Capability；没有执行 Observation、模型调用
  或设备动作。
- 隔离 Runtime 在 8882 完成验收后正常关闭，临时 runtime-token 已清理。

## 偏差与后续

- Capability Catalog 当前描述 Runtime V1 已知能力，尚不包含日志、性能和包管理能力。
- offline/unauthorized 时无法可靠确认当前 Adapter 能力，统一展示 unknown，不根据平台名称猜测支持。
- 下一迭代可选择首个工程诊断能力：建议从 Android Logcat 有界采集开始，将长耗时输出、取消、
  Artifact、脱敏和 Task 报告链路一次跑通。
