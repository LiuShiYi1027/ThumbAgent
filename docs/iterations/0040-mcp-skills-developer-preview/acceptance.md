# ITER-0040 Acceptance

> 状态：Completed
> 更新日期：2026-07-18

- [x] MCP 支持 initialize/initialized、ping、tools/list 和 tools/call 生命周期。
- [x] stdio stdout 只包含逐行 UTF-8 JSON-RPC，畸形消息返回安全协议错误。
- [x] Tool Catalog 只公开目标级能力，不公开 ADB、Shell 和原子输入 Tool。
- [x] Tool 输入来自公共 Contract，并在访问 Runtime 前严格拒绝缺失、越界和未知字段。
- [x] MCP 仅连接固定 HTTP loopback 地址，token 只从环境变量注入。
- [x] 设备任务异步提交并返回 task_id，可查询状态、报告和请求取消。
- [x] Agent 与日志入口要求确认，Runtime Policy 不被 MCP 绕过。
- [x] 领域错误使用 isError structuredContent，不泄露 HTTP body、traceback 或 token。
- [x] 默认测试不依赖网络、设备、模型或真实 socket。
- [x] 全量检查和真实 Runtime stdio E2E 通过。
- [ ] MCP Tasks、远程传输和自动确认不属于本迭代。
