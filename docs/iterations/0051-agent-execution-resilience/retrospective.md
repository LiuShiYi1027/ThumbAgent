# ITER-0051 Retrospective

> 文档状态：Active
> 迭代状态：Completed
> 更新日期：2026-08-17

## 实际交付

1. **观察阶段有界重试**（TASK-0051-02）：`AgentRunner` 新增 `_observe_with_retry`，仅对
   `UI_TREE_INVALID` / `OBSERVATION_FAILED` 两类瞬时 `DEVICE` 错误做最多 2 次重试
   （共 3 次尝试，间隔 0.3s），每次重试前检查取消与 Deadline；耗尽后原错误传播为明确终态，
   已完成轮次证据保留。连接性错误（`DEVICE_SESSION_CHANGED` 等）保持立即终止，不重试。
2. **轮次预算校准**（TASK-0051-03）：runner、REST、MCP 输入 Contract 的 `max_rounds`
   允许范围从 1–6 放宽到 1–12，默认值 6 不变；RuleBasedPlanner 演示预算维持 6。
   兼容性放松，原合法输入行为不变。
3. **真机成功率基线**（TASK-0051-04）：在同一台已授权设备、同一模型 Provider 下完成
   修复前后各一轮 `android-settings-smoke-v1`，指标见 acceptance.md 验收记录。

## 验证指标

- Active → Verifying 耗时：约 8 天（迭代 8/9 建立，实现集中在 8/17 完成，中间工作区处于
  测试先行、实现未动的暂停状态）
- Verifying → Completed 耗时：约 0.5 小时（一次集中真机 E2E）
- 计划 Task 数 / 新增 / 取消：4 / 0 / 0
- 完整 `make check` 执行次数：2（实现后一次、收尾一次；366 tests 通过）
- 真机 E2E 往返次数：1（修复前后各一轮场景集，确认均在任务提交时发生）
- 真机场景成功数与失败原因：修复前 2/3（bluetooth `TARGET_AMBIGUOUS`）；
  修复后 2/3（bluetooth `NO_PROGRESS`）；两侧 `policy_violation_count` 均为 0
- 修复前后成功率基线对照：66.7% → 66.7%，成功率不降；修复后平均轮次 4.67→4.0、
  平均耗时 68659ms→50973ms、Provider 调用 14→11 次，效率略有改善（单轮采样，仅供参考）

## 偏差与限制

- 六轮真机任务均未触发 `UI_TREE_INVALID`，观察重试路径只在测试中注入验证，真机收益
  待后续运行积累数据；成功率基线样本量小（每场景 1 次），66.7% 的读数波动大。
- bluetooth 场景两次失败终态不同（`TARGET_AMBIGUOUS` vs `NO_PROGRESS`），提示该场景在
  此机型上对模型偏难，建议后续单独分析，不作为本迭代回归。
- 评审发现先行测试一度"误绿"（未真实注入瞬时故障也会通过），已在实现前修正为
  `_FlakyObserveAdapter` 显式注入，并通过 stash 复现性检查确认测试有效。

## 后续行动

- 在后续 Agent 改动前沿用本基线对照流程（同一设备 + 同一 Provider + 同一 Suite）。
- 观察蓝牙类场景在该机型的失败模式，必要时扩充评测场景集（新迭代另行评估）。
