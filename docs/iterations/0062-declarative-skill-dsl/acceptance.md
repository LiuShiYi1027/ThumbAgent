# ITER-0062 Acceptance

> 文档状态：Final
> 迭代状态：Completed
> 更新日期：2026-09-02

| 编号 | 验收条件 | 验证方式 | 结果 |
| --- | --- | --- | --- |
| A1 | ADR-0021 方向经负责人确认 | ADR 状态转 Accepted | 通过（2026-09-01 确认） |
| A2 | DSL Contract 完备 | 正负样本契约测试；生成类型与 Schema 同步 | 通过（14 条契约测试；`skill-dsl.ts` 生成并同步） |
| A3 | 解释器执行边界 | 负向矩阵：未知工具/越界参数/超上限循环/嵌套调用/风险降级声明全部拒绝；每步 Policy+Capability 强制有断言 | 通过（14 条解释器测试，每条负向断言零设备动作；HIGH/PROHIBITED 派生风险即使 confirmed 也拒绝） |
| A4 | Registry 持久化与管理面 | 迁移测试；版本不可变；重启恢复；审计事件含 DSL 哈希；内置 Skill 覆盖/禁用被拒 | 通过（12 条 Registry 测试 + 37 条管理面/任务测试；真机 Runtime 重启后 rest 来源技能保留、builtin-dsl 自动加载、启停状态不丢） |
| A5 | 集中全量验证 | 一次 `make check` 全绿；既有内置 Skill 回归无失败 | 通过（646→651 tests OK，契约/类型/格式同步） |
| A6 | 真机驱动场景 | `app.stability_test` 对第三方应用 2 分钟时间盒：报告含动作计数、性能采样序列、崩溃/ANR 判定；E2E 显式标记不进默认测试集 | 替代通过（2026-09-02，BKQ-AN10）：短变体 `app.stability_smoke`（4 迭代）真机 succeeded，12 步记录完整、设备回到目标应用前台；官方文档 75s deadline 有界运行 → timed_out 干净收尾，11 步证据保留。偏差：性能采样缺失（观察类工具全是 Skill 中介，DSL 无法引用），崩溃/ANR 判定随之未覆盖——见复盘 |
