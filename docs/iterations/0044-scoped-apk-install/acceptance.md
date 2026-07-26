# ITER-0044 Acceptance

> 状态：Completed
> 更新日期：2026-07-26

- [x] APK 路径越界、符号链接、非 APK、超限文件和 package 不匹配在设备动作前拒绝。
- [x] Approval 绑定设备、SHA-256、包名和替换语义，过期或跨请求复用被拒绝。
- [x] 未经 Approval 的 High 风险动作仍被 Policy Engine 拒绝。
- [x] 安装异步执行并持有 Lease/Session；不自动重试未知结果。
- [x] 安装后查询 package manager 验证并报告 SHA-256、版本和替换状态。
- [x] REST/MCP 不暴露任意 ADB 参数、Shell 或 URL 下载。
- [x] 默认测试不依赖真机、网络或付费模型，`make check` 通过。
- [x] 真机预检返回文件名、大小、SHA-256 和 Manifest 包名，且在用户确认前没有提交安装任务。
- [x] 真机在独立明确确认后完成安装，后置验证确认包名、版本、SHA-256 和未替换语义。
