# Architecture Decision Records

ADR 记录影响多个模块、长期维护或安全边界的重要技术决策。

## 状态

- Proposed
- Accepted
- Superseded
- Deprecated
- Rejected

## 命名

```text
NNNN-short-kebab-case-title.md
```

编号只递增，不复用。新 ADR 可以取代旧 ADR，但不删除历史记录。

## 模板

```markdown
# ADR-NNNN: 标题

- Status: Proposed
- Date: YYYY-MM-DD
- Deciders: Team

## Context

## Decision

## Consequences

## Alternatives Considered

## Follow-up
```

## 当前 ADR

- [ADR-0001：桌面端与 Runtime 分进程](./0001-desktop-runtime-separation.md)
- [ADR-0002：Tool 与 Skill 分层](./0002-tool-skill-model.md)
- [ADR-0003：Android V1 使用 ADB-first](./0003-android-adb-first.md)
- [ADR-0004：MCP 作为外部接口](./0004-mcp-interface-boundary.md)
- [ADR-0005：Agent 决策动作模型](./0005-agent-decision-action-model.md)
- [ADR-0006：可恢复 Agent 验证与有界 Provider 重试](./0006-recoverable-agent-verification.md)
- [ADR-0007：Runtime 自主持有 Agent 成功条件](./0007-runtime-owned-goal-verification.md)
- [ADR-0008：两阶段目标编译与显式确认](./0008-confirmed-goal-compilation.md)
- [ADR-0009：持久化异步任务执行与协作式取消](./0009-durable-async-task-execution.md)
- [ADR-0010：Runtime 设备租约与任务总 Deadline](./0010-device-lease-task-deadline.md)
- [ADR-0011：Runtime 单实例与设备连接会话](./0011-runtime-instance-device-session.md)
- [ADR-0012：通过受控 Tool/Skill 采集有界设备日志](./0012-bounded-device-log-skill.md)
- [ADR-0013：异步执行器支持显式注册的多任务类型](./0013-explicit-multi-type-async-execution.md)
- [ADR-0014：性能诊断只保留聚合快照](./0014-aggregate-performance-snapshot.md)
- [ADR-0015：MCP stdio 作为本地 Runtime API 的 Interface Adapter](./0015-mcp-stdio-local-api-adapter.md)
