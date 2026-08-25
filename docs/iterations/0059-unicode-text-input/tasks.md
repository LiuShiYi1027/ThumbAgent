# ITER-0059 Tasks

> 文档状态：Final
> 迭代状态：Completed
> 更新日期：2026-08-25

| Task | 状态 | Owner | 交付 |
| --- | --- | --- | --- |
| TASK-0059-01 | done | Kimi | ADR-0019（helper 分发信任模型、IME 切换/恢复语义、读回验证容差）+ Contract Schema（unicode 输入请求/结果）+ 新错误码登记（e9c20b9） |
| TASK-0059-02 | done | Kimi | Capability Catalog 登记 `input.unicode@1` + Android Adapter（ime 查询/切换/恢复、固定 argv、读回验证）+ helper 源码/可复现构建/登记 APK + Adapter Contract 测试（35bb76a） |
| TASK-0059-03 | done | Kimi | Tool 与确定性 Skill（`input.unicode_text`），敏感输入拦截复用，Policy/Session/Lease 接入，Skill 测试矩阵全覆盖 + Fake Adapter（4af46d3） |
| TASK-0059-04 | done | Kimi | REST 与 MCP 入口、Agent allowlist 集成（中文目标经模型循环完成输入步骤）（06d6be8） |
| TASK-0059-05 | done | Kimi | 集中全量验证（`make check` 480 tests OK）、真机 E2E 六场景全 PASS、三处真机发现修复（追加语义/远端 shell 引用/包扫描竞态，6bd2016）、文档同步 |
