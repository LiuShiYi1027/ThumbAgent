# ADR-0015: MCP stdio 作为本地 Runtime API 的 Interface Adapter

- Status: Accepted
- Date: 2026-07-18
- Deciders: Mobile Agent Team

## Context

产品定位要求以 AI-native Skills 形式服务 Codex、Claude 和其他 Agent。现有 Runtime 已通过 localhost
REST 提供任务、设备、日志和性能能力，并使用单实例锁、Session、Lease、Policy 与 SQLite 维护真源。
如果 MCP stdio 子进程另建 Runtime，会与桌面/Web 争抢同一数据目录和设备；如果 MCP 直接访问 ADB
或数据库，则会破坏强制架构边界。

## Decision

- 实现 MCP `2025-11-25` stdio Server，并兼容 `2025-06-18`、`2025-03-26`、`2024-11-05` 握手。
- MCP 子进程是 Interface Adapter，只调用固定的 loopback REST 端点；不创建第二个 Runtime，不读取
  SQLite，不访问 Artifact 文件，不执行 ADB。
- stdio 使用逐行 UTF-8 JSON-RPC；stdout 只输出协议消息，诊断只能进入 stderr。
- 首版只声明稳定 `tools` capability，不实现 Resources、Prompts、Sampling 或实验性 MCP Tasks。
- 设备任务通过现有异步 REST 入口立即返回 Mobile Agent `task_id`；状态、报告和取消由独立 MCP
  Tools 查询，不在 stdio 请求内等待长任务。
- Tool 输入 Schema 以 `contracts/schemas/mcp-tool-inputs.schema.json` 为真源，MCP 在访问 REST 前执行
  严格校验；只公开目标级能力，不公开 `input.tap`、ADB 或底层诊断 Tool。
- MCP 只允许 HTTP loopback Runtime 地址，API token 从环境变量读取；不接受远程 URL、URL 内凭据或
  自由路径。每个 stdio 进程串行处理请求，并限制 Tool 调用频率。
- 需要设备交互或日志采集的 Tool 要求 `confirmed=true`，其描述和 annotations 要求 MCP Host 在调用前
  展示参数并取得用户确认；Policy Engine 仍是最终授权者。
- Tool 成功同时返回 text 与 structuredContent；领域失败使用 `isError=true`，保留安全 Error Contract。

## Consequences

- Web、CLI、桌面和多个 MCP 客户端共享一个 Runtime、设备 Session、Lease 与任务历史。
- MCP 客户端必须先启动 localhost Runtime，并安全注入同一个 API token。
- MCP Host 是否真正向用户展示确认仍属于 Host 信任边界；未来可增加 Runtime-issued approval token，
  替代当前布尔确认的传输语义。
- 首版不使用 MCP Tasks 扩展；外部 Agent 需要轮询 Mobile Agent execution Tool。
- 从源码运行时 MCP 读取仓库 Contract；打包时必须随包携带 Contract 或配置
  `MOBILE_AGENT_CONTRACT_DIR`。

## Alternatives Considered

- MCP 子进程直接构造 Runtime：会触发单实例冲突，且与桌面端割裂。
- MCP 直接访问 SQLite/ADB：绕过 Application、Policy、Session 和 Lease，不可接受。
- 首版采用 Streamable HTTP：与现有 localhost API 功能重叠，且增加 Origin、Session 和 HTTP MCP
  授权复杂度；stdio 更适合本地开发者预览。
- 立即采用 MCP Tasks：该能力在稳定规范中仍为实验性，现有 TaskExecution 已满足状态和取消需求。
