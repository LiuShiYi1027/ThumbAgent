# ITER-0042 Live Evaluation Baseline

> 状态：Completed
> 更新日期：2026-07-21

## 背景

ITER-0041 已完成单个蓝牙目标的真实 E2E，但一次成功无法回答 Agent 的成功率、时延和主要失败来源。
ITER-0027 已能对单个 TaskRun 做路径无关评测，本迭代在其上建立版本化场景集和多任务聚合，不比较
固定 ToolCall 路径，也不在评测阶段访问设备或模型。

## 目标

- 将多个 `AgentEvaluationScenario` 组织为版本化 Suite，并声明每个场景的运行次数。
- 聚合成功率、场景覆盖、轮次、Tool、耗时分位数、Provider 重试、无进展和策略违规。
- 提供只消费已完成任务的 CLI 报告入口。
- 提供第一组 Android 系统设置 smoke 场景，作为真机在线基线入口。

## 非目标

- 不回放历史动作，不规定页面路径或 ToolCall 顺序。
- 不在 Runtime 内自动批量操作设备或消费付费模型。
- 不建立排行榜、云端遥测或跨设备调度。
- 不以一次 smoke 结果宣称第三方 App 泛化能力。

## 兼容性

新增 Suite 与 Summary Contract；单任务 EvaluationResult 只增加可选指标，属于向后兼容变化。
无需数据库迁移或 ADR。
