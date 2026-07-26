# ITER-0044 Retrospective

> 状态：Completed
> 更新日期：2026-07-26

## 实际交付

- ADR-0016 定义两阶段、短期、单次、范围绑定的 High 风险授权模型。
- 本地 APK 预检限制在 `<data-dir>/apks`，验证路径、大小、ZIP、binary Manifest package id 和 SHA-256。
- `app.install@1` 通过 High 风险 Tool/Skill、异步 Task、Lease、Session 和安装后 package manager 查询执行。
- REST 与 MCP 提供 prepare/submit 两阶段入口，安装 Tool 标记为 destructive。
- Approval 确认后文件变化会在 ADB 前拒绝；安装超时映射为 unknown outcome 且不自动重试。

## 验证结果

- `make check` 通过：lint、typecheck 和 300 项默认测试全部成功。
- 46 个 Contract 与 Skill Manifest JSON 文档可解析。
- Fake Device 的 MCP prepare → confirm → async install → report 完整链路通过。
- 真机 `adb:A6TG025A13002156` 完成 prepare → 独立明确确认 → async install → report 全链路验收：
  - 安装任务 `task_2994be0e6b174148b0d24bdc9f7ba73c` 终态为 `succeeded`。
  - 安装包 `com.saucelabs.mydemoapp.android`，版本 `2.2.0`（version code `25`）。
  - APK SHA-256 为 `318ef64bdcaff18e576d962ab1f557e0a2683b9b5210a6bb6b25cb0caeef62b4`，与预检结果一致。
  - `replace_existing=false`，安装后验证为 `verified`，没有自动重试、额外安装、卸载、降级、清除数据或权限授予。

## 已知限制

- 只支持一个普通 APK，不支持 split APK、APKS、XAPK、APEX、降级或权限授予。
- Approval 只存于当前 Runtime 内存，重启后失效。
- V1 只从 binary AndroidManifest 读取 package id；安装后的版本以设备 package manager 查询为准。
