# ADR-0007: Runtime 自主持有 Agent 成功条件

- Status: Accepted
- Date: 2026-07-13
- Deciders: Mobile Agent Team

## Context

模型擅长根据实时页面决定路径，但不应成为任务是否完成的唯一信任来源。真机任务曾实际进入目标
页面，却因模型生成的 `finish` 元数据或 Selector 不稳定被标记失败。ITER-0027 的外部评测条件
只能事后评分，无法约束当次 Runtime 终态。

## Decision

- `agent.run` 可选接收调用方提供的结构化 `AgentGoalAcceptance`。
- 模型仍决定何时请求 `finish`；提供外部验收时，Runtime 忽略模型 Selector 的判定语义，改用
  调用方条件验证当前 Observation。
- app id、Activity 和 Selector 使用 all-of 语义；Selector 必须唯一匹配。
- 验收失败发生在只读验证阶段，可作为 failed round 反馈模型继续规划。
- 未提供外部验收时继续使用模型 `finish` 条件，保持兼容。
- TaskRun 保存验收条件和完成来源，客户端不得把两种来源混为一谈。

## Consequences

- 路径继续由模型动态决定，成功标准由用户、Skill、测试场景或外部 Agent 独立定义。
- 模型不能通过自述或宽松 Selector 把未完成目标升级为成功。
- 错误的外部验收会造成确定性假阴性，因此必须可见、可审计且默认可选。
- 第一版仍依赖一个 UI Selector，复杂业务状态需要后续验证器模型。

## Alternatives Considered

- 从自然语言自动推导验收：当前缺少可信编译与确认机制，容易把模型判断重新包装成权威条件。
- Runtime 在每轮自动结束：会改变现有 Agent 决策和报告语义，本迭代仍由模型发出 `finish` 请求。
- 接受任意一个条件即成功：会使仅进入目标 App 就掩盖页面未到达，采用 all-of 更安全。

## Follow-up

- 支持由 GoalSpec、Skill 或版本化场景生成用户可确认的验收条件。
- 增加平台结构化状态和业务结果验证器。
- 评估在外部验收已满足时由 Runtime 无需额外模型调用直接完成任务。
