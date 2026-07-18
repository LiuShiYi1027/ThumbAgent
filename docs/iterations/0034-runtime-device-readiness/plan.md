# ITER-0034 Runtime & Device Readiness

> 状态：Completed
> 日期：2026-07-15

## 背景

Runtime 过去在 ADB 缺失时直接启动失败；即使能够启动，用户也需要分别理解设备列表、授权、
Session 和 DEVICE_LOCKED，才能判断当前为何不能运行任务。

## 目标

- ADB 未安装或路径错误时，Runtime 仍能启动只读 Web/CLI 诊断面。
- 定义统一 RuntimeReadiness Contract，聚合 Gateway、设备连接、Session、Lease 和修复建议。
- 提供 `GET /v1/readiness`，blocked 状态也返回 HTTP 200 的可渲染快照。
- Web 只允许选择 ready 设备，并展示 blocked/attention 的明确原因和下一步。
- CLI 提供同一 Contract 的终端诊断视图。

## 非目标

- 不自动安装或下载 Android Platform Tools。
- 不自动修改开发者选项、USB 授权或系统权限。
- 不执行 Observation、截图、UI dump 或写动作作为健康检查。
- 不实现 iOS、鸿蒙真实 Adapter 或多设备调度。

## Contract 兼容性

- 新增 `runtime-readiness.schema.json` 和只读 `/v1/readiness`，属于兼容性新增。
- Readiness 内嵌引用现有 Device Contract，不复制 Device 字段定义。
- 不修改持久化模型，不需要数据库迁移。

## 架构说明

UnavailableDeviceAdapter 仍遵守 Device Adapter Port，只用于在本地传输依赖缺失时保持接口可用；
它拒绝所有设备访问。Readiness 由 Application 层组合 Device Gateway 和 DeviceLease 状态，Web/CLI
不直接访问 ADB 或租约注册表。该变化未修改 Adapter 依赖方向、安全信任模型或 Tool/Skill 分层，
因此不新增 ADR。
