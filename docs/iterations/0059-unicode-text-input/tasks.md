# ITER-0059 Tasks

> 文档状态：Active
> 迭代状态：Active
> 更新日期：2026-08-24

| Task | 状态 | Owner | 交付 |
| --- | --- | --- | --- |
| TASK-0059-01 | in_progress | Kimi | ADR-0019（helper 分发信任模型、IME 切换/恢复语义、读回验证容差）+ Contract Schema（unicode 输入请求/结果）+ 新错误码登记 |
| TASK-0059-02 | pending | Kimi | Capability Catalog 登记 `input.unicode@1` + Android Adapter（ime 查询/切换/恢复、固定 argv 广播、读回验证）+ Adapter Contract 测试 |
| TASK-0059-03 | pending | Kimi | Tool 与确定性 Skill（`input.unicode_text`），敏感输入拦截复用，Policy/Session/Lease 接入，Skill 测试矩阵全覆盖 + Fake Adapter |
| TASK-0059-04 | pending | Kimi | REST 与 MCP 入口、Agent allowlist 集成（中文目标经模型循环完成输入步骤） |
| TASK-0059-05 | pending | Kimi | 集中全量验证（一次 `make check`）、真机 E2E（MagicOS 中文输入与 IME 恢复）、文档同步（capability-model.md、technical-design-v1.md §11.4、error-handling.md、迭代索引） |
