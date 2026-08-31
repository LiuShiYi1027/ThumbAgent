# ITER-0061 Agent Working Memory & Task Results（跨轮工作记忆 + 结构化任务结果）

> 文档状态：Draft
> 迭代状态：Planned
> 创建日期：2026-08-31
> 关联：[能力路线图 §4.0](../../product/capability-roadmap.md) · [ITER-0060 复盘](../iterations/0060-live-agent-cjk-task-loop/retrospective.md) · [契约版本规范](../../engineering/contract-versioning.md)

## 背景

2026-08-30 跨应用比价场景评估（「打开京东查 iPhone 17 价格 → 打开淘宝对比」）
暴露 Agent 内核两个结构性缺口：

1. **跨轮记忆缺失**：Provider `_request_body` 每轮只发 `goal + 当前 observation +
   round`，不带历史。Agent 离开页面即遗忘其中信息——任何「记住前面看到的」类
   意图（比价、验证码回填、多页表单）都不成立。
2. **结果契约缺失**：finish/acceptance 仅支持 UI 状态断言（前台应用 + Selector），
   任务无法带回任何数据答案。契约全量检索确认无 scratchpad / answer /
   result_data 字段。

路线图 §4.0 已将内核层列为 V2 前置、结构性必需（不适用需求拉动）。本迭代交付
其中前两项；子目标追踪以 scratchpad 内 plan 字段的轻量形态随行，不立独立机制。

## 目标

- **跨轮工作记忆**：AgentDecision 增加可选 `scratchpad` 字段（模型每轮可读写），
  Runner 持久化并随下一轮 observation 注入 prompt；长度有界；任务级隔离，
  不跨任务共享。
- **结构化任务结果**：finish 决策携带可选 `answer`（有界字符串），Runner 持久化到
  `TaskRun.result` 并在报告 CLI / REST / Desktop 透出；验收语义保持 UI 断言不变，
  answer 的正确性由模型负责并在报告中呈现（V1 不做数据自动断言）。
- **驱动场景真机验证**：「打开京东，搜索 iPhone 17，带回价格」——模型经
  scratchpad 记录所见价格，finish 带回 answer，任务 succeeded 且报告含价格文本。

## 非目标

- 不做跨应用全链路比价的真机验收（轮次预算与登录墙属环境性因素，留后续场景）。
- 不做长期记忆 / 向量检索 / 跨任务记忆。
- 不做 Skill DSL 与管理面（ITER-0062 候选，依赖本迭代契约）。
- 不做结果正确性的自动断言（数据断言 DSL 待真实需求再设计）。
- 不改验收的 UI 断言语义；不新增设备动作。

## 关键决策点（实施前需在 tasks/ADR 中明确）

- **scratchpad 语义**：每轮全量覆盖（模型自管合并）还是追加式（Runner 拼接）？
  倾向全量覆盖 + 长度上限——模型可见全文、语义最简单、无并发合并问题。
- **answer 与 acceptance 的关系**：answer 独立于 acceptance 存在；finish 时
  acceptance（若有）仍先验 UI，answer 只作为结果载荷，不参与通过判定。
- **敏感信息**：scratchpad/answer 会进任务报告。沿用报告既有呈现边界；
  长度上限兜底，不做内容级过滤（与 sensitive 输入拦截职责分开）。

## 兼容性

全部为可选字段新增，向后兼容：旧决策（无 scratchpad/answer）行为不变；
Fake Provider 与既有测试不受影响。按 contract-versioning.md 走兼容性新增流程：
Schema → 生成类型 → 消费者 → Contract 测试。无持久化迁移（TaskRun 为新写路径）。

## 风险与应对

- **prompt 变长加剧本地模型延迟**：scratchpad 上限收紧（如 1024 字符），
  摘要注入而非全量历史。
- **模型滥用 scratchpad 存敏感内容**：长度上限 + 报告呈现边界说明；
  不存原文密码/验证码的纪律写进 prompt。
- **answer 空转**：模型提前 finish 带空 answer → 由 goal acceptance（若有）兜底；
  无 acceptance 时允许空 answer（合法：纯操作类任务无答案可带）。

## 测试与验收要点

- Contract 测试：scratchpad/answer 字段序列化、长度上限拒绝、旧载荷兼容。
- Runner 单测：scratchpad 跨轮传递与更新、finish answer 持久化进 TaskRun.result、
  任务隔离（下个任务不带上轮 scratchpad）。
- Fake Provider 集成：决策链路全通。
- 真机 E2E：京东查价带回场景（显式标记，不进默认测试集）。
