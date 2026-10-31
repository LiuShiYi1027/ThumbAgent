# ITER-0069 Acceptance

> 文档状态：Active  
> 迭代状态：Completed  
> 更新日期：2026-10-31

| 编号 | 验收条件 | 验证方式 | 结果 |
| A1 | 使用独立 `ThumbAgent_API_36`，不创建时不清空个人 AVD | 检查脚本固定参数与实际运行日志 | 通过。脚本只创建/复用 `ThumbAgent_API_36`；个人 `Pixel_7_API_36` 未修改。独立 AVD 启动时才使用 `-wipe-data` |
| A2 | 基线覆盖 readiness、设置启动、Observation、页面导航和 2 轮稳定性 REST 任务 | `make test-e2e-emulator`；检查各场景断言与终态 | 通过。三次运行均完成 6 个场景；显示页 Activity 为 `.Settings$DisplaySettingsActivity`，最终回到 Settings 首页 |
| A3 | 每次生成 summary、分场景结果与 Emulator 日志；只清理脚本启动的实例 | 检查 `e2e-output/emulator-baseline/` 与运行前后 `adb devices` | 通过。独立运行后 serial 均离线；复用运行 `started_by_script=false`、`stop_requested=false`、serial 保持在线 |
| A4 | 从未运行状态连续两次成功，重复执行结果一致 | 连续两次执行同一 Make 目标，退出码均为 0 | 通过。`20261031T151615Z` / `20261031T151757Z`；任务 `task_36f7ce2247ef46968c8462f8004f9b28` / `task_7fb117bbd556446591c6943b0061eb2c` 均 `succeeded`，各 2 轮、2 个采样点 |
| A5 | 默认快速测试不启动 Emulator；完整门禁通过 | `make check`、`make check-desktop` | 通过。Runtime 731 项；Desktop lint/typecheck/fmt/clippy 与 26 项 Rust 测试全绿 |
