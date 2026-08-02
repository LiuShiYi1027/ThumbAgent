# ITER-0049 Retrospective

> 文档状态：Active
> 迭代状态：Completed
> 更新日期：2026-08-02

## 实际交付

- `apps/desktop` Tauri 2 + React 19 + TypeScript 严格模式脚手架，oxlint 与 `tsc -b` 门禁。
- Rust sidecar 生命周期：随机 loopback 端口、`getrandom` 一次性 token（仅经环境变量传入
  Runtime）、20 秒健康轮询、退出清理、单实例锁冲突检测与 10 个 Rust 单元测试。
- 设备就绪首页：React Query 有界轮询 `GET /v1/health`、`/v1/readiness`、`/v1/devices`，
  展示运行环境诊断、修复建议和设备表格；前端只能经 IPC 桥访问 Runtime，token 不出 Rust 层。
- `scripts/generate_ts_contracts.py`：从 `contracts/schemas` 生成首页子集（Device、
  RuntimeReadiness）TypeScript 类型，`--check` 漂移校验已并入 `make check`。
- Makefile 新增 `contracts`、`check-contracts`、`check-desktop`；默认 `make check` 保持
  Python 快速门禁不变。

## 验证结果

- `make check`：354 个测试通过，含 TS 契约一致性校验。
- `make check-desktop`：lint、typecheck、cargo fmt/clippy/test 全部通过。
- 只读 E2E（emulator-5554，Android 16，独立临时数据目录）：sidecar 自动启动、随机端口、
  token 仅存在于进程环境、就绪诊断与设备列表正确展示、冲突拒绝、退出清理，全部通过。
  验收明细见 [acceptance.md](./acceptance.md)。

## 效率指标

- 计划 Task 5 个，新增 0 个、取消 0 个。
- 完整 `make check` 执行 2 次（含最终候选 1 次），桌面门禁 1 次。
- 人工确认/E2E 往返 1 次；E2E 场景 1/1 成功。
- Active 至 Completed 历时约 3 天（2026-07-31 至 2026-08-02），含一次跨 Agent 交接
  （Codex → Kimi），交接成本主要是 tasks.md 状态滞后于代码实际进度。

## 已知限制

- E2E 在 Android Emulator 完成，未覆盖真机厂商差异；后续迭代涉及桌面端写路径时应在真机
  补验。
- 桌面端首版只读：IPC 桥仅支持有界 GET，触发设备动作需后续迭代新增 POST 桥与确认 UI。
- 无前端单元测试框架；首页逻辑靠类型检查、lint 和 E2E 覆盖。
- Runtime 尚无事件流，首页使用轮询；WebSocket 事件流仍为技术方案中的未实现项。
- 应用打包分发（dmg/notarize）、自动更新未做，`tauri dev` 为当前唯一运行方式。
- 多 Runtime 通过不同数据目录共存（如 MCP 预览 `/tmp/mobile-agent-demo` 与桌面默认目录）；
  同一数据目录仍严格互斥。
