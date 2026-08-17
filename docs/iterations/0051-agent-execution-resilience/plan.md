# ITER-0051 Agent Execution Resilience

> 文档状态：Active
> 迭代状态：Completed
> 更新日期：2026-08-09

## 产品结果

Agent 任务不再因为一次瞬时观察失败（如转场动画期间 dump 出非法 UI 节点）而整任务判死；
轮次预算上限从硬编码 6 校准到 12，使"差一步成功"的任务有机会完成；同时在真机上用版本化
评测 Suite 建立成功率基线，作为后续所有 Agent 改动的对照基准。

## 背景

ITER-0050 桌面端真机试用暴露两个系统性问题：

1. `AgentRunner` 中 `adapter.observe()` 的失败（如 `UI_TREE_INVALID`）直接传播为任务终态。
   决策执行错误已有 `_is_recoverable_decision_error` 有界恢复机制（ITER-0028），观察阶段没有
   对等保护。实测一次设置导航任务在第 1 轮因转场瞬间 bounds 非法直接失败。
2. `max_rounds` 在 runner 与 API 均硬校验 1–6。实测弱模型任务第 6 轮成功点进目标页，但没有
   第 7 轮完成 finish，以 `NO_PROGRESS` 判死——距离成功差一轮。上限取值从未经过成功率数据
   校准。

同时，项目已有在线评测设施（ITER-0027/0042）但从未产出过真机成功率基线，导致上述参数
（轮次、重试）的调整缺乏数据支撑。本迭代把两件事一起闭环：修韧性，同时建立度量。

## 范围

- 观察阶段有界重试：`AgentRunner` 对观察调用遇到的瞬时设备类错误（`UI_TREE_INVALID` 及
  同类可恢复 `DEVICE` 类错误）做有限次重试（默认最多 2 次，重试间遵守取消与 Deadline 检查）；
  重试耗尽后任务以明确错误终态结束，已完成轮次证据保留。先写复现测试再实现。
- 轮次预算校准：runner、REST、MCP 的 `max_rounds` 允许范围从 1–6 放宽到 1–12，默认值 6
  不变；RuleBasedPlanner 内部演示预算维持 6 不变。事件与报告语义不变。
- 真机成功率基线：在一台已授权 Android 设备上执行 `evaluations/android-settings-smoke-v1.json`
  场景集，记录修复前基线与修复后对照，指标含总成功率、逐场景成功率、轮次 p50/p95、
  `NO_PROGRESS`/`UI_TREE_INVALID` 分布。

## 非目标

- 不修改安全区点击拦截、Policy 风险分级或确认语义（这些防护本身工作正常）。
- 不修改桌面端任何文件（ITER-0050 工作区并行进行中，不做文件交集）。
- 不调整 RuleBasedPlanner 的目标匹配范围或"演示模式"行为。
- 不引入视觉/多模态观察，不修改 UI 解析器的严格校验规则本身（只在调用侧重试）。
- 不新增评测场景集；只使用既有 `android-settings-smoke-v1`。
- 不修改 Contract Schema；观察重试复用既有失败轮次与事件结构。

## 依赖

- 既有异步任务链路（ITER-0031/0032/0033）的取消、Deadline、Lease、Session 语义不变。
- 既有评测设施：`POST /v1/tasks/{task_id}/evaluate`（ITER-0027）与
  `scripts/report-mcp-evaluation.zsh`（ITER-0042）。
- 一台已授权 Android 真机与可用的模型 Provider 配置。

## 风险与兼容性

- 观察重试会产生额外截图/UI Tree Artifact：重试上限 2 次，增量有界，在任务报告中可见。
- 重试间隔不得绕过取消与 Deadline：每次重试前执行 `_raise_if_stopped` 检查。
- `max_rounds` 上限放宽是兼容性放松（原合法输入仍合法），无破坏性变更；调用方不传时行为
  完全不变。轮次增多意味着模型调用与设备动作增多，仍受 Deadline（默认 600s）、Lease 和
  `NO_PROGRESS` 重复动作拦截约束，不扩大安全授权。该调整属于执行参数校准，不涉及信任模型
  或风险策略变化，预计不需要新 ADR。
- 基线评测消耗真实模型调用，次数有界（3 场景 × 修复前后各至多 2 轮采样）。

## 预算

- 4 个 Task，目标 2 个工作日。
- 开发阶段只运行 focused tests；候选稳定后运行一次完整 `make check`。
- 真机 E2E 集中执行一次：场景集内点击属 Medium 风险，确认只在任务提交面板发生。
