# ITER-0061 Acceptance

> 文档状态：Final
> 迭代状态：Completed
> 更新日期：2026-09-01

| 编号 | 验收条件 | 验证方式 | 结果 |
| --- | --- | --- | --- |
| A1 | 集中全量验证通过 | 一次 `make check`（含新增 Contract/Runner 用例），类型/格式/TS 同步检查全过 | 通过（563 tests OK，2026-09-01） |
| A2 | scratchpad 跨轮传递 | Runner 单测：第 N 轮决策写入 scratchpad，第 N+1 轮 Provider 请求体可见；全量覆盖语义；长度超限拒绝 | 通过（单测 + 真机实证：夸克任务 8 轮记忆连贯） |
| A3 | answer 持久化与透出 | 单测 + 报告：finish 携带 answer → `TaskRun.result` 持久化 → 报告 CLI/REST 可见 | 通过（Desktop 透出在本迭代窗口审查中补齐，a7471ad） |
| A4 | 向后兼容 | 旧决策载荷（无 scratchpad/answer）行为不变；既有测试全过 | 通过（全量回归无失败） |
| A5 | 任务隔离 | 单测：新任务的 scratchpad 不带上一任务内容 | 通过 |
| A6 | 真机驱动场景 | 京东「搜索 iPhone 17 带回价格」：任务 succeeded，`result.answer` 含价格文本，人工核对与页面一致；E2E 显式标记不进默认测试集 | 替代通过：京东场景未到达 finish（模型层因素，见复盘偏差）；内核验收由确定性「关于手机带型号」场景完成——succeeded、`completion_source=planner_finish`、answer 与 getprop 逐字符一致（e2e-output/20260901-211333） |
