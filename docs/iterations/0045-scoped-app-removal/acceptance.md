# ITER-0045 Acceptance

> 文档状态：Active
> 迭代状态：Completed
> 更新日期：2026-07-26

- [x] Prepare 只读返回应用元数据、`keep_data`、数据删除影响、Approval ID 和过期时间。
- [x] 系统应用和系统属性未知的应用在设备写动作前拒绝。
- [x] Approval 绑定设备、包名、版本和数据保留语义，过期或跨请求复用被拒绝。
- [x] 未经 Approval 的 High 风险卸载仍被 Policy Engine 拒绝。
- [x] Android Adapter 只使用固定 `adb uninstall [ -k ] <app-id>` 参数数组。
- [x] 卸载异步执行并持有 Lease/Session；失败或 unknown outcome 不自动重试。
- [x] 成功必须由 package manager 确认目标包不存在。
- [x] REST/MCP 不暴露 Shell、任意 ADB 参数、批量卸载或系统应用绕过。
- [x] 默认测试不依赖真机、网络或付费模型。
- [x] 真机完成 prepare → 独立明确确认 → async uninstall → report 全链路验收。
