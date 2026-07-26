# ITER-0045 Scoped App Removal

> 文档状态：Active
> 迭代状态：Completed
> 更新日期：2026-07-26

## 目标

- 以独立两阶段 Approval 安全卸载一个明确的非系统应用。
- 在任何写动作前展示应用版本、系统应用判定和数据删除影响。
- 通过异步 Task、Lease、Session 和包管理器后置查询完成可审计验证。
- 同时提供 REST 与 MCP prepare/submit 入口，不暴露 Shell 或任意 ADB 参数。

## 非目标

- 不卸载系统应用，不批量卸载，不绕过设备管理策略。
- 不清除其他应用数据，不授予或撤销权限，不停止或禁用应用。
- 不自动重试失败或 unknown outcome 的卸载。
- 不持久化或跨 Runtime 复用 Approval。

## 兼容性

新增 Contract、Capability、异步任务类型、REST 和 MCP Tool，属于向后兼容变化。应用详情新增可选
`system_app` 字段；已有消费者可忽略。安全与可靠性决策由 ADR-0017 记录，无需数据库迁移。
