# ITER-0009 Retrospective

> 状态：Active
> 更新日期：2026-07-08

## 实际交付

- 新增版本化 SQLite migration：`0001_task_store.sql`。
- 新增 `migrate_database` 和 `SQLiteTaskStore`。
- RuntimeService 支持注入 Task Store。
- `build_default_runtime()` 默认使用 SQLite Task Store。
- 新增 SQLite 持久化测试，覆盖 migration 幂等、跨 Runtime 实例查询和缺失任务错误。

## 验收结果

- 定向测试 9 tests OK。
- 全量 `make check` 73 tests OK，lint/typecheck OK。
- `git diff --check` OK。

## 计划偏差

- 本迭代按计划没有拆复杂关系表，而是保存 TaskRun/Event JSON 快照。这样能更快稳定产品闭环，后续有查询需求时再细分索引。

## 有效做法

- 保留 Store 注入能力，使单元测试和未来特殊运行模式仍可使用内存 Store 或临时 SQLite。
- 通过 migration 文件创建表，避免应用代码里散落未记录 DDL。
- 只持久化摘要和 JSON 快照，不读取或复制 Artifact 内容。

## 问题与根因

- 当前只持久化已完成任务，不支持运行中任务恢复。
- 暂无历史任务列表、分页、保留策略和清理机制。
- JSON 快照对复杂筛选不友好，后续若要做任务列表筛选，需要增加索引字段或拆表。

## 长期文档回写

- README 已说明默认数据库位置。
- V1 技术方案已补充 ITER-0009 当前最小表结构和限制。
- 本迭代引入持久化但遵守既有数据迁移规范，不需要 ADR。

## 后续行动

- 下一步建议做任务历史列表 API/CLI，让用户可以先列出历史任务，再选择某个 task id 查看报告。
- 再之后可做桌面端任务报告卡片。
