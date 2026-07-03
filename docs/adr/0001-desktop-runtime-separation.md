# ADR-0001: 桌面端与 Runtime 分进程

- Status: Accepted
- Date: 2026-07-03
- Deciders: Mobile Agent Team

## Context

产品既需要桌面工作台，也需要 CLI、MCP 和未来设备实验室节点。若设备与 Agent 逻辑直接写入桌面进程，能力难以复用，UI 生命周期也会影响任务稳定性。

## Decision

采用 Tauri Desktop 与 Python Runtime 分进程架构。桌面端通过受认证的 localhost API 和 WebSocket 使用 Runtime；发布时 Runtime 作为 sidecar 管理。

## Consequences

- Runtime 可独立测试和被多种接口复用。
- UI 刷新不直接终止任务。
- 需要处理 sidecar 生命周期、认证、版本协商和打包。
- 前端不得直接执行设备或系统命令。

## Alternatives Considered

- 全部使用 Tauri/Rust：部署简洁，但 V1 设备、AI 和数据开发效率较低。
- Electron 内嵌 Node Runtime：生态成熟，但仍容易将 UI 与核心能力耦合。
- 纯 Web 服务：不符合本地设备和隐私优先目标。

## Follow-up

- 定义 Runtime 健康检查和版本协商协议。
- 建立 sidecar 随机端口与短期令牌机制。
