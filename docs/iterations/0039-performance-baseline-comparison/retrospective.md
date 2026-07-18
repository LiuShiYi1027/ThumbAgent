# ITER-0039 Retrospective

> 状态：Completed
> 更新日期：2026-07-15

## 实际交付

- 新增严格的两点性能比较 Contract 和无 I/O Domain 比较器。
- Runtime 从 TaskStore 读取并验证两条性能 TaskRun，Interface 不直接访问持久化实现。
- Web 支持在历史报告中选择基线和候选快照；CLI 输出数值、delta、unit 与 trend。
- 对噪声使用公开稳定阈值，对缺失温度使用 unavailable，不输出“回退”等因果判断。

## 验证结果

- `lint`、类型检查和 `git diff --check` 通过；默认快速测试共 251 项通过。
- 34 个 JSON Schema/Manifest 均可解析；定向单元、集成、API、Web 和 CLI 测试通过。
- Android 真机生成两条独立 TaskRun，均经历 `queued -> running -> succeeded`，随后在不访问设备的
  比较阶段确认同一 Session、采样间隔 5.467 秒。
- 真机比较成功输出六项 delta、unit、threshold 和 trend；本次变化均落在公开稳定阈值内。

## 后续观察

- 两点样本适合快速诊断，不适合统计回归判定。
- Web 基线选择只保存在当前页面内存中，刷新后需要重新选择；Comparison 本身不持久化为新 Task。
- 后续若要包裹 Agent 任务做前后采样，应设计独立 Workflow、异常清理和任务关联 Contract。
