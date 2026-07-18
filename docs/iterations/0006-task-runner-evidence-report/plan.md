# ITER-0006: Task Runner & Evidence Report

> 状态：Completed
> 更新日期：2026-07-08
> Owner：Codex

## 目标

在已有 Tool 与 Skill 能力之上，建立 V1 最小 Task Runner，让一次确定性 Skill 调用可以被包装为可审计的任务执行报告。

本迭代要证明：

> 用户看到的不只是某个 Tool 或 Skill 返回值，而是一条有目标、有步骤、有状态、有证据摘要的本地任务执行链。

## 背景

ITER-0003 到 ITER-0005 已经完成设备发现、Observation、基础动作、语义点击、滚动查找和安全示范 Skill。但这些能力仍偏底层：调用者需要理解 Skill 内部结构，执行结果也没有统一的任务报告形态。

后续要支持设备日志、性能采集、安装卸载包、多步骤技能和 AI-native Skills，必须先把“任务”作为产品和工程上的稳定承载物。

## 范围

- 定义 `TaskRun` Contract。
- 实现最小 `TaskRunner`：
  - 支持 `settings.scroll_navigate` 作为第一条确定性任务类型。
  - 记录 `task_id`、目标、设备、状态、时间、步骤、Skill 结果和证据摘要。
  - 策略拒绝、确认缺失或执行错误时返回结构化失败报告。
- RuntimeService 暴露同步任务运行方法。
- 本地 HTTP API 暴露一个预览型同步任务运行端点。
- 补齐单元测试、Contract 测试和质量门禁。

## 非目标

- 通用自然语言规划。
- 大模型决策循环。
- 异步任务队列、暂停、恢复、取消和确认回调。
- SQLite 持久化、事件流或 WebSocket。
- 多设备并行调度。
- 任意 Shell 执行、安装卸载包、日志采集和性能采集。

## 安全边界

- TaskRunner 不绕过 Skill、Tool Registry、Policy Engine 或 Device Gateway。
- TaskRunner 不生成底层命令，不拼接模型文本。
- 任务执行必须绑定明确 `device_id`。
- Medium 风险动作仍要求显式确认。
- 失败报告可以记录错误码和结构化上下文，但不得包含密钥、验证码、密码或完整敏感 UI 内容。

## 依赖

- ITER-0005 的 `settings.scroll_navigate` Skill。
- `NavigationResult`、`ActionResult`、`Observation` 和 Artifact 引用。
- 现有 RuntimeService 与本地 HTTP API。

## 风险

- 若过早实现异步任务系统，会引入存储、恢复和并发复杂度。
- 若 TaskRun 结构过宽，后续演进成本会上升。
- 若失败报告吞掉安全策略语义，调用方可能误以为只是普通失败。

## 里程碑

1. 定义 `TaskRun` Contract 和兼容性结论。
2. 实现领域对象与最小 TaskRunner。
3. 接入 RuntimeService 和本地 API。
4. 覆盖成功、策略拒绝和 Contract 测试。
5. 更新 README、迭代索引和复盘。

## 完成条件

以 [acceptance.md](./acceptance.md) 的必选验收全部通过为准。
