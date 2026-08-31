# ITER-0061 Tasks

> 文档状态：Draft
> 迭代状态：Planned
> 更新日期：2026-08-31

| Task | 状态 | Owner | 交付 |
| --- | --- | --- | --- |
| TASK-0061-01 | pending | Kimi | Contract：AgentDecision +`scratchpad`（可选、有界）、finish 携带 `answer`（可选、有界）、TaskRun +`result`；兼容性说明；Contract 测试；TS 类型再生成 |
| TASK-0061-02 | pending | Kimi | Runner：scratchpad 状态机（任务级初始化 → 每轮决策可覆盖更新 → 注入下轮）、finish answer 提取与 TaskRun.result 持久化、报告 CLI/REST 透出 |
| TASK-0061-03 | pending | Kimi | Provider：system prompt 说明 scratchpad 语义（全量覆盖、长度上限、不存敏感原文）与 answer 产出契约；request body 携带 scratchpad |
| TASK-0061-04 | pending | Kimi | 测试矩阵：Contract 测试 + Runner 单测（跨轮传递、answer 持久化、任务隔离、上限拒绝）+ Fake Provider 集成 |
| TASK-0061-05 | pending | Kimi | 集中全量验证（一次 `make check`）+ 真机 E2E：京东搜索 iPhone 17 带回价格（显式标记）+ 复盘 |
