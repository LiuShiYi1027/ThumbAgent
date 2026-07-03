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
