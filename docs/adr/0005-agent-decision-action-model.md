# ADR-0005: Agent 决策动作模型

- Status: Accepted
- Date: 2026-07-12
- Deciders: Mobile Agent Team

## Context

Mobile Agent 在 ITER-0022 引入多轮 Agent Preview。Planner 不再只输出一个目标级 Skill 调用，而是可以基于每轮 Observation 决定下一步动作。

这带来一个关键边界问题：`run_tool`、`run_skill` 和 `finish` 是否都应该长期存在？如果存在，它们分别表达什么语义？

如果边界不清，后续实现容易出现两类偏差：

- 把页面探索、滚动方向、点击路径等动态决策藏进 Skill 内部，使 Skill 变成黑盒小 Agent。
- 让模型直接调用过细或过宽的能力，绕过 Tool Registry、Skill 验证和安全策略。

## Decision

Agent 决策动作采用三类长期语义：

```text
run_tool   → 原子设备动作
run_skill  → 目标级受控能力
finish     → 请求完成，由 Runtime 验证
```

### run_tool

`run_tool` 是 Agent Loop 的默认动作形态，用于需要逐轮观察、动态调整和恢复的页面交互。

适用场景：

- 打开应用
- 点击元素
- 滑动
- 返回或 Home
- 等待或只读观察类动作

约束：

- 只能调用 Tool allowlist 内的 Tool。
- 参数必须通过结构化校验。
- 每次执行前必须经过 Capability 和 Policy 检查。
- 每次执行后必须重新 Observation。
- 模型不能生成 Shell、ADB 命令、自由格式脚本或坐标逃生口。

### run_skill

`run_skill` 长期保留，但不是 Agent Loop 的默认动作。它用于边界稳定、可复用、可验证的目标级能力。

适用场景：

- 安装、卸载、启动、停止应用等具备清晰输入输出的目标能力。
- 采集日志、导出诊断包、采集性能样本等工程能力。
- 已经产品化、验证器稳定、风险和预算明确的复合能力。

约束：

- Skill 必须声明输入输出、风险、Capability、Tool allowlist、预算和验证方式。
- Skill 只能通过 Tool Registry、Policy Engine 和 Device Gateway 执行动作。
- Skill 不能为了“方便”隐藏本应由 Agent 逐轮决策的页面探索逻辑。
- 不确定导航、滚动方向选择、页面路径恢复等动态探索优先使用 `run_tool` 多轮完成。

### finish

`finish` 表示模型认为任务可以结束，但不代表任务已经成功。

约束：

- `finish` 必须携带可验证条件，例如 `expected_selector`、前台应用状态或明确的结构化断言。
- Runtime 必须执行确定性验证。
- 验证失败时任务不能成功，应返回领域错误。
- 模型自述、reason 或 confidence 不能单独作为成功证据。

## Consequences

- Agent Loop 的主路径更 AI Native：模型逐步观察并决策原子动作。
- Skills 仍保留产品化和复用价值，但不会吞掉 Agent 的核心决策过程。
- `finish` 的成功语义由 Runtime 控制，避免“模型说完成就完成”。
- 需要在 Planner prompt、Runner allowlist、Skill 开发规范和测试中持续维护三类动作的边界。

## Alternatives Considered

### 只保留 run_tool

优点是边界最简单，模型每一步都透明。

缺点是无法复用稳定的工程能力，例如日志采集、安装包、诊断导出等目标级操作会被拆得过碎，难以统一验证和审计。

### 只保留 run_skill

优点是对外语义高层、调用简单。

缺点是容易把动态决策藏进 Skill，使 Skill 成为不可观察黑盒，削弱 Agent 的观察—决策—验证循环。

### 允许模型直接调用任意底层命令

灵活性最高，但破坏安全模型，无法满足本地优先、可审计和高风险动作拦截要求。

## Follow-up

- 将 `run_tool / run_skill / finish` 写入技术方案和 Skill 开发规范。
- 后续新增 Skill 时评审其是否隐藏了本应由 Agent Loop 决策的动态路径。
- 当 Agent 决策 Contract 外部化到 JSON Schema 时，将三类动作纳入 Contract 测试。
