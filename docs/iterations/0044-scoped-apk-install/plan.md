# ITER-0044 Scoped APK Install

> 状态：Completed
> 更新日期：2026-07-22

## 目标

- 以两阶段、单次、范围绑定的 Approval 放行 High 风险本地 APK 安装。
- 预检授权目录、文件类型、大小、SHA-256、Manifest package id 与替换影响。
- 异步安装持有 Lease/Session，安装后查询 package manager 验证并生成任务报告。
- 同时提供 REST 与 MCP prepare/submit 入口，不暴露任意 Shell、URL 下载或任意 ADB 参数。

## 非目标

- 不下载 APK，不安装 split APK/APKS/XAPK/APEX。
- 不卸载、清除数据、降级、授予权限或绕过系统安装策略。
- 不持久化或跨 Runtime 复用 Approval。

## 兼容性

新增 Contract、Capability、异步任务类型、REST 和 MCP Tool，属于向后兼容变化。High 风险信任模型
变化由 ADR-0016 记录；无需数据库迁移。
