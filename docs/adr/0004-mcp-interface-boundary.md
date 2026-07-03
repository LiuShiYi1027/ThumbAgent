# ADR-0004: MCP 作为外部接口

- Status: Accepted
- Date: 2026-07-03
- Deciders: Mobile Agent Team

## Context

Mobile Agent 需要以 AI Native 方式被外部 Agent 调用。MCP 适合公开 Skills，但若将内部模块通信也建立在 MCP 上，会使领域和执行逻辑耦合传输协议。

## Decision

MCP 作为 Interface Adapter，调用同一 Application Use Case 和 Policy Engine。Runtime 内部使用类型明确的领域接口与事件。V1 优先支持本地 stdio，不默认对外暴露网络服务。

MCP 默认公开目标级 Skills，不公开全部原子 Tool。

## Consequences

- 外部 Agent 获得标准化入口。
- 桌面、CLI 与 MCP 共享安全和任务语义。
- 内部架构不依赖 MCP 生命周期和传输。
- 需要维护 MCP 与内部 Contract 的映射测试。

## Alternatives Considered

- MCP 作为内部总线：形式统一，但扩大协议耦合和调试复杂度。
- 仅提供 REST：实现直接，但 AI Agent 集成体验不足。
- 直接公开全部原子 Tool：灵活，但扩大攻击面和错误组合概率。

## Follow-up

- 定义 MCP Skill 命名与错误映射。
- 增加 MCP/REST 语义一致性 Contract 测试。
