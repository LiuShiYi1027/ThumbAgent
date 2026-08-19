# ThumbAgent Desktop

ThumbAgent 的 macOS 桌面工作台（Tauri 2 + React 19 + TypeScript + Vite）。桌面端不直接
执行 ADB 或任何系统命令；所有设备数据来自本地 Python Runtime 的 REST API。

## 架构

- 应用启动时由 Rust 侧拉起 Runtime sidecar（`python3.11 -m mobile_agent.api.server`），
  监听随机 loopback 端口，一次性 API token 由 Rust 生成并仅经环境变量传入 Runtime 进程。
- 前端只能通过 IPC 桥（`runtime_api_get`，有界 GET 白名单）访问 Runtime；token 不进入
  前端可见配置。
- 应用退出时自动清理 sidecar 子进程；同一数据目录已有 Runtime 运行时展示冲突提示，不复用、
  不抢占。
- 共享类型来自 `contracts/generated/typescript`（由 `scripts/generate_ts_contracts.py`
  从 `contracts/schemas` 生成，勿手改）。

## 开发

```bash
npm install
npm run tauri dev
```

要求：Rust stable 工具链、Node 22+、Python 3.11 以及仓库根目录的 Runtime 代码。可用
`MOBILE_AGENT_PYTHON` 指定 Python 解释器、`MOBILE_AGENT_DATA_DIR` 指定独立数据目录。

## 检查

```bash
# 在仓库根目录执行
make check-desktop
```

包含 oxlint、`tsc -b`、`cargo fmt --check`、`cargo clippy -D warnings` 和 Rust 单元测试。
默认 `make check` 不包含桌面端。
