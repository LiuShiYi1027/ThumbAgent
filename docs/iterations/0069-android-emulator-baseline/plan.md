# ITER-0069 Android Emulator Baseline（Android 模拟器一键基线）

> 文档状态：Active  
> 迭代状态：Completed  
> 创建日期：2026-10-31  
> 关联：[设备测试规范](../../engineering/testing.md) · [E2E 套件](../../../scripts/e2e/README.md)
> 完成日期：2026-10-31  

## 背景

ITER-0068 的稳定性预算修复已通过手工启动的 Pixel 7 API 36 Emulator 验证，但启动、等待、
任务提交、证据收集和清理都依赖临时操作。该结果尚不能作为可重复回归入口。

## 目标

- 提供 `make test-e2e-emulator`：从模拟器未运行状态完成创建/复用测试专用 AVD、启动、
  基线执行、证据保存和受控清理。
- 基线覆盖设备发现与 readiness、设置启动与 Observation、系统页面导航、2 轮稳定性任务。
- 连续两次执行均成功；脚本只关闭自己启动的 Emulator，不影响其他设备。

## 非目标

- 不接入 CI，不在默认 `make check` 中启动 Android Emulator。
- 不下载 SDK 或系统镜像，不修改、清空个人 AVD。
- 不运行真实模型、商业 App、Helper IME 安装或高风险设备动作。
- 不声称国产 ROM 兼容性，不替代真机验收。

## 关键决策

1. 固定测试 AVD 为 `ThumbAgent_API_36`，镜像为本机已安装的
   `system-images;android-36;google_apis;arm64-v8a`，设备模板为 `pixel_7`。
2. 测试 AVD 未运行时由脚本以 `-wipe-data -no-snapshot-save` 启动；已运行时复用且不关闭。
3. 使用动态空闲 Emulator 端口和显式 serial，避免占用或关闭其他设备。
4. 稳定性场景通过真实 loopback REST 异步入口提交，其余场景复用 RuntimeService。
5. 每次结果写入 `e2e-output/emulator-baseline/<timestamp>/`，包含 summary、场景结果和 Emulator 日志。

## 兼容性

- 只新增显式 E2E 命令与脚本，不改变 Runtime Contract、默认测试或发布行为。
- 不需要 ADR、数据库迁移或模型配置。

## 风险

- 本机缺少指定系统镜像时必须失败并给出安装命令，不自动联网下载。
- 启动失败或场景异常仍要清理本脚本启动的进程，并保留日志和结果。
- 测试专用 AVD 已运行时不能清空其数据；复用模式的初始状态由调用方负责。

## 验证

- 连续两次从 Emulator 未运行状态执行 `make test-e2e-emulator`，退出码均为 0。
- 两次均生成成功 summary，结束后由脚本启动的 serial 不在线。
- 最终运行一次 `make check` 与 `make check-desktop`。
