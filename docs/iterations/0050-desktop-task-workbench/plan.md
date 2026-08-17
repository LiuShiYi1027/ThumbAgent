# ITER-0050 Desktop Task Workbench

> 文档状态：Active
> 迭代状态：Active
> 更新日期：2026-08-02

## 产品结果

用户在桌面工作台输入自然语言目标，选择一台就绪设备，在明确展示目标、设备与动作风险的
确认面板中显式确认后提交异步 Agent 任务；执行过程中看到逐轮进展并可随时取消；任务结束后
查看完整的 Observe–Plan–Act 报告（每轮观察摘要、Planner 决策、动作结果、完成依据）。

## 背景

ITER-0049 交付了桌面端只读首页（sidecar、认证、就绪诊断与设备列表），但 IPC 桥仅支持
GET。Runtime 的异步 Agent 任务链路（ITER-0031 起）已完整：`POST /v1/tasks/agent.run/async`
提交、`GET /v1/task-executions/{id}` 与 `/events` 轮询、`POST .../cancel` 取消、终态
`GET /v1/tasks/{id}` 返回完整 TaskRun。`/ui` 原型（ITER-0014/0031）已验证同一交互流程。
本迭代把该流程以正式产品形态搬进桌面端，桌面端从只读诊断走向可执行任务。

## 范围

- Rust IPC 桥增加有界 POST 通道：路径白名单仅含 `POST /v1/tasks/agent.run/async` 与
  `POST /v1/task-executions/{id}/cancel`；`Idempotency-Key` 由 Rust 侧生成；token 仍不出
  Rust 层；结构化错误透传前端。
- `contracts/generated` 扩展桌面端消费子集：TaskExecution、TaskEvent、TaskRun 及
  `agent.run` 报告引用链（AgentStepResult、AgentDecision、AgentObservationSummary、
  AgentActionFeedback、ActionResult 等），生成器按需补齐引用链与复合类型支持。
- 任务提交：自然语言输入、就绪设备 gating（仅 `ready` 设备可提交）、确认面板展示目标、
  设备与 Medium 风险动作说明，用户显式确认后才提交 `confirmed=true`。
- 执行时间线：有界轮询 TaskExecution 与 TaskEvent，展示 queued/running/cancelling/终态、
  逐轮 `agent.round` 完成与失败轮次错误码，提供取消按钮。
- 任务报告：终态后渲染 TaskRun——目标、状态、`completion_source`、每轮 observation/
  decision/action_result、错误与证据摘要。

## 非目标

- 不引入 WebSocket；执行进展使用有界轮询（与 ITER-0049 一致）。
- 不做 GoalSpec 编译交互（`POST /v1/goals/compile`）、自定义 acceptance 输入与任务历史
  列表页；本轮只使用 `goal` + `confirmed` 最小提交面。
- 不做设备画面（截图/屏幕镜像）、人工接管、暂停/继续。
- 不开放任意 POST 路径；不新增或修改 Runtime REST 端点，不修改 Runtime 业务行为。
- 不做设置页、模型 Provider 配置编辑、应用打包分发。
- 不做 iOS、鸿蒙真实 Adapter 与多设备并行；同一时刻桌面端只跟踪一个活跃任务。

## 依赖

- ITER-0049 已交付的桌面壳、GET 桥与只读首页。
- 既有 Runtime 异步任务链路（ITER-0031/0032/0033）：Lease、Deadline、Device Session、
  幂等与取消语义不变。
- 无新工具链依赖。

## 风险与兼容性

- 确认信任模型：桌面端获得触发 Medium 风险设备动作的能力。确认语义与 MCP 保持一致——
  只有确认面板向用户展示目标、设备与风险且用户显式确认后，才允许提交 `confirmed=true`；
  模型输出仍经过 Tool allowlist、Capability 与 Policy Engine，桌面端不扩大 Runtime 授权。
  该变化属于 ADR-0001 既定桌面-Runtime 信任边界的延伸，预计不需要新 ADR；若实现中确认
  语义或授权范围发生变化，先补 ADR 再继续。
- TS 生成器需支持 TaskRun 的引用链（跨文件 `$ref`、`oneOf`、数组项复合类型）。若整条
  引用链支持成本失控，裁剪为 `agent.run` 报告所需最小子集，不允许绕过生成器手写近似类型
  （AGENTS.md Contract-first 约束）。
- 执行中事件为紧凑格式（step_id/kind/status/error_code），逐轮详情仅在终态 TaskRun
  可用；时间线只承诺轮次级进展，不伪造实时决策细节。
- 幂等：提交按钮去抖 + Rust 侧单次任务生命周期内复用同一 Idempotency-Key，双击或重试
  不产生重复任务。
- 兼容性：不改动既有 Contract、REST 行为与数据库；新增 TS 生成文件与桌面代码均为增量。

## 预算

- 5 个 Task，目标 2–3 个工作日。
- 开发阶段只运行 focused tests；候选稳定后运行一次完整 `make check` 与 `make check-desktop`。
- E2E 在一台已授权 Android 设备上集中执行：一次完整任务（含提交前确认）与一次中途取消；
  Medium 风险确认只在提交面板发生一次，不重复要求。
