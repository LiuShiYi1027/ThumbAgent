# ITER-0043 App Inventory

> 状态：Completed
> 更新日期：2026-07-21

## 背景

Runtime 已能发现和检查设备，但外部 Agent 无法在不读取 UI 的情况下确认某个应用是否安装、版本为何。
安装 APK 属于 High 风险动作，而当前 Policy Engine 对 High 风险采取拒绝策略，即使 `confirmed=true`
也不放行。为避免以实现便利绕过安全边界，本迭代先交付只读应用清单，安装能力进入后续独立迭代。

## 目标

- 新增平台无关的已安装应用 Contract 与 `app.inspect@1` Capability。
- Android Adapter 使用固定 ADB 参数读取应用标识和单应用的最小必要元数据。
- 提供有界列表、前缀过滤与单应用详情的 Runtime REST 和 MCP 入口。
- 不暴露原始 `dumpsys`、APK 路径、签名、权限明细或任意命令参数。

## 非目标

- 不安装、升级、卸载、停用或启动应用。
- 不下载 APK，不读取 APK 文件，不修改 High 风险授权策略。
- 不提供完整权限、组件、签名或应用数据目录。

## 兼容性

新增 Contract、Capability、REST 端点与 MCP Tools，属于向后兼容变化；无需数据库迁移或 ADR。
后续 APK 安装将改变安全信任模型和异步任务类型，需要独立 ADR 与主线评审。
