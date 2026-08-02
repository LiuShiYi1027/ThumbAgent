# ITER-0049 Acceptance

> 文档状态：Active
> 迭代状态：Completed
> 更新日期：2026-08-02

- [x] macOS 上启动桌面应用时自动拉起 Runtime sidecar，无需手动 `make run`。
- [x] sidecar 监听随机 loopback 端口，token 由 Rust 侧生成并经环境变量传入；token 不出现在
      日志、仓库或前端可见配置中。
- [x] 首页展示 Runtime 健康状态、统一就绪诊断（ADB、设备连接/授权、Session、Lease）与
      修复建议。
- [x] 连接已授权 Android 设备时，首页展示设备名称、型号、系统版本和连接状态。
- [x] 既有 Runtime 已占用默认数据目录时，UI 明确展示冲突提示，不隐式复用或抢占。
- [x] 应用退出后 sidecar 进程被清理，无残留 `mobile_agent.api.server` 进程。
- [x] 桌面端不直接执行 ADB 或任何系统命令；所有设备数据来自 Runtime REST API。
- [x] `contracts/generated` 由脚本生成并标注生成方式；门禁包含与 Schema 的一致性校验。
- [x] 默认 `make check` 保持通过且耗时无显著增加；桌面显式门禁（TS 类型检查、Rust check、
      生成一致性）通过。
- [x] 真机只读 E2E：桌面首页正确展示一台已授权 Android 设备的就绪状态。

## 验证记录

- `make check`：354 个 Python 测试与 TS 契约一致性校验全部通过（2026-08-02）。
- `make check-desktop`：oxlint、`tsc -b`、`cargo fmt --check`、`cargo clippy -D warnings`、
  10 个 Rust 单测全部通过（2026-08-02）。
- E2E（2026-08-02，emulator-5554，Android 16，独立数据目录 `/tmp/iter0049-e2e-data`）：
  sidecar 自动拉起并监听随机端口；`/v1/health`、`/v1/readiness`（status=ready）与
  `/v1/devices` 数据正确；首页设备表格与诊断面板经用户目视确认；同数据目录二次启动被
  明确拒绝；Cmd+Q 退出后无 sidecar 进程残留。
