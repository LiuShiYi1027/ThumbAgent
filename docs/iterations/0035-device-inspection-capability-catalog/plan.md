# ITER-0035 Device Inspection & Capability Catalog

> 状态：Completed
> 日期：2026-07-15

## 背景

Readiness 能回答设备是否可执行任务，但不能解释单台设备当前有哪些能力、对应风险、确认要求、
幂等性和限制。Tool Registry 与 Capability 规范中的元数据也需要统一真源，避免长期漂移。

## 目标

- 建立 V1 Capability Catalog，统一风险、幂等、验证、要求和限制。
- Tool Registry 从 Capability Catalog 派生风险与幂等元数据。
- 定义 DeviceInspection Contract，组合设备可用性和 Capability Descriptor。
- 提供 `GET /v1/devices/{device_id}/inspection`，不触发 Observation 或设备动作。
- Web 可点击设备查看能力；CLI 提供设备详情命令。

## 非目标

- 不新增日志、性能、包管理 Capability 的实际实现。
- 不探测屏幕内容、前台 App、权限详情或敏感设备属性。
- 不修改 Tool/Skill 分层、Policy 信任边界或风险等级。
- 不实现 iOS、鸿蒙真实 Adapter。

## Contract 兼容性

- 新增 `device-inspection.schema.json` 和只读 inspection 端点，属于兼容性新增。
- DeviceInspection 引用 RuntimeReadiness 的 DeviceAvailability 和既有 Device Contract。
- RuntimeReadiness 仅将内联 DeviceAvailability 提取到 `$defs`，序列化结构与语义不变。
- 不修改持久化模型，不需要迁移。

## 架构说明

Capability Catalog 位于 Domain，保存平台无关能力语义，不包含 ADB 命令或产品流程。Tool Registry
仍负责 Tool→Capability 映射，Policy Engine 仍负责执行时授权；Inspection 只是只读展示，不参与
授权决策。因此未改变依赖方向或 Tool/Skill 边界，不新增 ADR。
