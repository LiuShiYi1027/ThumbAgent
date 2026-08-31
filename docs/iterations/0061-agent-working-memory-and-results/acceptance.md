# ITER-0061 Acceptance

> 文档状态：Draft
> 迭代状态：Active
> 更新日期：2026-08-31

| 编号 | 验收条件 | 验证方式 | 结果 |
| --- | --- | --- | --- |
| A1 | 集中全量验证通过 | 一次 `make check`（含新增 Contract/Runner 用例），类型/格式/TS 同步检查全过 | 待验证 |
| A2 | scratchpad 跨轮传递 | Runner 单测：第 N 轮决策写入 scratchpad，第 N+1 轮 Provider 请求体可见；全量覆盖语义；长度超限拒绝 | 待验证 |
| A3 | answer 持久化与透出 | 单测 + 报告：finish 携带 answer → `TaskRun.result` 持久化 → 报告 CLI/REST 可见 | 待验证 |
| A4 | 向后兼容 | 旧决策载荷（无 scratchpad/answer）行为不变；既有 497+ 测试全过 | 待验证 |
| A5 | 任务隔离 | 单测：新任务的 scratchpad 不带上一任务内容 | 待验证 |
| A6 | 真机驱动场景 | 京东「搜索 iPhone 17 带回价格」：任务 succeeded，`result.answer` 含价格文本，人工核对与页面一致；E2E 显式标记不进默认测试集 | 待验证 |
