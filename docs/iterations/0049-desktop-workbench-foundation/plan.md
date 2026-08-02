# ITER-0049 Desktop Workbench Foundation

> 文档状态：Active
> 迭代状态：Completed
> 更新日期：2026-08-02

## 产品结果

用户在 macOS 上启动 Mobile Agent 桌面应用，应用自动拉起并认证本地 Python Runtime，首页展示
Runtime 健康、统一就绪诊断、已发现设备列表和修复建议。既有 `/ui` 临时页面继续保留，用于
MCP/CLI 调试。

## 背景

ADR-0001 已确定 Tauri Desktop 与 Python Runtime 分进程架构；前 48 个迭代集中完成 Runtime
内核，桌面工作台是 V1 产品形态的最大剩余缺口。本迭代交付桌面线的第一个可运行纵向切片。

## 范围

- `apps/desktop` Tauri 2 + React + TypeScript + Vite 脚手架，TypeScript 严格模式。
- Rust sidecar 生命周期：启动 `python3.11 -m mobile_agent.api.server`、随机 loopback 端口、
  一次性 API token、健康检查轮询、应用退出时清理子进程。
- 首页只读展示：`GET /v1/health`、`GET /v1/readiness`、`GET /v1/devices`，含修复建议。
- `contracts/generated`：从 `contracts/schemas` 生成首批桌面端消费的 TypeScript 类型
  （Device、RuntimeReadiness 等首页子集），并提供一致性校验脚本。
- Makefile 增加桌面端显式检查目标；默认 `make check` 保持 Python 快速门禁不变。

## 非目标

- 不做任务工作台（自然语言输入、Agent 执行时间线、取消）、设备画面、报告查看和设置页。
- 桌面端不触发任何设备写动作，首版只调用只读 GET API。
- 不做应用打包分发（dmg/notarize）、自动更新和窗口多开。
- 不引入 WebSocket；Runtime 尚无事件流，桌面端使用有界轮询。
- 不修改 Runtime 业务行为；不新增 REST 端点。
- 不做 iOS、鸿蒙真实 Adapter 与多设备并发。

## 依赖

- Rust stable toolchain（rustup，安装于本迭代开始时）。
- Node 22 + npm（已就绪）。
- 既有 Python 3.11 Runtime，行为不变。

## 风险与兼容性

- 仓库首次引入 Rust/Node 工具链：门禁拆分为 Python 默认目标与桌面显式目标，避免拖慢
  `make check`；桌面依赖通过 lockfile 固定。
- sidecar 安全：仅监听 loopback、随机端口、token 由 Rust 侧生成并经环境变量传入 Runtime
  进程，不写入日志、仓库或前端可见配置。
- Runtime 单实例锁按数据目录生效：若已有 Runtime 占用默认数据目录，sidecar 启动会失败，
  首版在 UI 明确展示该错误并提示关闭既有实例，不做隐式复用或抢占。
- TS 类型生成器使用 Python stdlib 脚本（与 `scripts/quality.py` 同风格），不新增 Python
  依赖；生成目录标注生成方式，门禁校验与 Schema 一致。
- 架构边界已由 ADR-0001 覆盖，本迭代不改变模块依赖方向、安全信任模型或既有 Contract，
  预计不需要新 ADR；若实现中出现边界变化，先补 ADR 再继续。

## 预算

- 5 个 Task，目标 2–3 个工作日。
- 开发阶段只运行 focused tests；候选稳定后运行一次完整 `make check` 与桌面门禁。
- E2E 为只读场景：桌面首页展示一台已授权 Android 真机的就绪状态，无需用户风险确认。
