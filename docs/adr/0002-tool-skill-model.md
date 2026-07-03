# ADR-0002: Tool 与 Skill 分层

- Status: Accepted
- Date: 2026-07-03
- Deciders: Mobile Agent Team

## Context

AI 既需要点击、截图等原子设备动作，也需要打开应用、执行任务等目标级能力。如果全部称为 Skill，会混合底层动作、业务编排和 Agent 自主循环，导致风险与验证边界模糊。

## Decision

采用三层模型：

- Tool：原子、确定性设备能力。
- Skill：有输入输出、风险、能力要求和验证的目标级能力。
- Workflow：多个 Skill 的可复用业务编排。

所有 Tool 经过 Schema、Capability 和 Policy 校验。Agentic Skill 必须声明 Tool allowlist、预算和失败阈值。

## Consequences

- 底层动作可以稳定复用并集中审计。
- Skills 可以面向 Agent 提供更清晰语义。
- 需要维护 Tool Registry、Skill Registry 与 Contract。
- 不允许 Skill 直接访问平台命令以图方便。

## Alternatives Considered

- 所有能力统一为 Tool：简单，但无法表达验证、风险和目标语义。
- 所有能力统一为 Skill：命名统一，但原子与目标能力边界不清。
- 直接让模型生成脚本：灵活但不可控，不符合安全目标。

## Follow-up

- 定义第一版 Tool 和 Skill Manifest Schema。
- 建立 Registry contract tests。
