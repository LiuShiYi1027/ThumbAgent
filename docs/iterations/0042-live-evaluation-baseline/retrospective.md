# ITER-0042 Retrospective

> 状态：Active
> 更新日期：2026-07-21

## 实际交付

- 新增版本化 `AgentEvaluationSuite` 与 `AgentEvaluationSummary` Contract。
- 单任务评测新增 Provider 耗时/尝试/重试、无进展、模型不可用和终态错误指标。
- 聚合器严格要求场景覆盖与 task_id 唯一，并输出总/分场景成功率和耗时分位数。
- 新增只消费现有评测 API 的 Suite CLI，以及蓝牙、显示和亮度、电池三个设置 smoke 场景。

## 验证结果

- `make check` 在首版实现后通过：lint、typecheck 和 276 项默认测试全部成功；最终回归数以仓库最新检查为准。
- Suite 文件通过领域 Contract 解析，包含 3 个场景且每场景运行 1 次。
- 真机三场景原始执行结果为 2 成功、1 次 `NO_PROGRESS`；首份 Summary 暴露评测器错误依赖 Planner `verified_node` 的问题。
- 评测器已改为优先使用最终 Observation，并增加回归测试；基于产品决策不再为该设置页样本重复消耗模型或操作设备，因此未重新聚合修复后的 Summary。

## 后续行动

- 后续在能力或 Planner 有实质变化时，再把 `runs_per_scenario` 提升到 3～5 建立成功率基线。
- 第三方 App 场景需要先补充环境元数据与更丰富的独立成功条件，不能直接复用设置页假设。
