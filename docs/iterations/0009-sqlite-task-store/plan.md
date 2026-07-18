# ITER-0009: SQLite Task Store

> 状态：Completed
> 更新日期：2026-07-08
> Owner：Codex

## 目标

将 ITER-0007 的进程内 Task Store 升级为默认 SQLite 持久化，让任务报告和事件在 Runtime 重启后仍可查询。

本迭代要证明：

> 任务报告不再只是当前进程里的临时状态，而是本地可保留、可查询、可服务 CLI/桌面端的产品资产。

## 背景

ITER-0008 已经提供 CLI 任务报告视图，但任务记录依赖 Runtime 进程内 Store。用户一旦重启 Runtime，CLI 和未来桌面端就无法查看历史任务。

按照数据与迁移规范，持久化必须通过版本化 migration 落地，不能在启动时偷偷执行临时 DDL。

## 范围

- 新增 SQLite migration：
  - `schema_migrations`
  - `tasks`
  - `task_events`
- 新增 SQLite Task Store：
  - 保存 `TaskRun` JSON 快照。
  - 保存紧凑 `TaskEvent` JSON 快照。
  - 按 `task_id` 查询任务。
  - 按 sequence 查询事件。
- RuntimeService 支持注入 Store；默认 Runtime 使用 SQLite Store。
- 补齐 migration 幂等、跨 Runtime 实例查询和缺失任务测试。
- 更新 README、技术方案、迭代索引和复盘。

## 非目标

- 复杂关系型拆表查询。
- 分页、保留策略和清理任务。
- Runtime 崩溃恢复非终态任务。
- 实时事件流。
- 多设备锁和租约。
- 桌面 GUI。

## 安全边界

- SQLite 只保存 TaskRun/Event 的结构化 JSON 快照，不保存密钥、验证码、密码。
- 不读取或复制 Artifact 文件内容。
- 失败时返回 `STORAGE_ERROR` 或既有 `TASK_NOT_FOUND`，不暴露本机敏感路径。
- Store 不改变 Skill/Tool/Policy 执行语义。

## 依赖

- ITER-0006 的 `TaskRun`。
- ITER-0007 的 `TaskEvent`。
- ITER-0008 的 CLI 报告视图。
- Python 标准库 `sqlite3`。

## 风险

- JSON 快照便于快速落地，但不适合复杂筛选和聚合。
- 当前只持久化已完成任务，不处理运行中任务的崩溃恢复。
- 后续若要清理历史任务，需要补保留策略和清理任务。

## 里程碑

1. 新增 migration 文件。
2. 实现 migration runner。
3. 实现 SQLiteTaskStore。
4. Runtime 默认切换到 SQLiteTaskStore。
5. 覆盖迁移、持久化和查询测试。
6. 更新文档并通过质量门禁。

## 完成条件

以 [acceptance.md](./acceptance.md) 的必选验收全部通过为准。
