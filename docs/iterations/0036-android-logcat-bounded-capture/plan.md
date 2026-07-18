# ITER-0036 Android Logcat Bounded Capture

> 状态：Completed
> 日期：2026-07-15

## 背景

设备发现、交互、任务报告、异步执行、就绪诊断和 Capability Catalog 已形成基础闭环。下一步需要
验证工程诊断类 Skill 是否也能遵循同一 Capability、Policy、Session、Lease 和 Artifact 边界。

## 目标

- 定义版本化日志采集输入、结果和 Skill Manifest Contract。
- 新增 `logs.collect@1` 与仅供 Skill 使用的注册 Tool。
- Android 使用固定参数采集最近日志快照，Fake Adapter 提供无设备测试替身。
- 日志在本地脱敏、限制为 1 MiB Artifact，公共输出不内联原文。
- 提供受认证 REST、显式确认 Web 按钮和 CLI。
- 覆盖成功、输入拒绝、能力不足、策略确认、Adapter 失败、取消、离线和截断。

## 非目标

- 不开放任意 ADB、Shell、logcat filter/tag/PID/buffer 参数。
- 不做持续流式采集、后台常驻采集或多设备并发采集。
- 不把日志上传模型、云端或遥测服务。
- 不实现 iOS、鸿蒙日志 Adapter，不实现性能采样和包管理。
- 不把本 Skill 纳入 Agent 的默认 `run_tool` allowlist。

## Contract 兼容性

- 新增 input/result/Skill Manifest Schema、Skill 和 REST 端点，属于向后兼容新增。
- Artifact 新增 `device_log` 和 `text/plain` 枚举；仓库内消费者已同步，未知枚举消费者仍需按规范 fallback。
- Tool 元数据新增 `direct_invocation` 字段；现有 Tool 默认 `true`，语义不变。
- 不修改持久化 Schema，不需要迁移。

## 架构说明

Skill 只调用注册的 `device.logs.capture` Tool；Tool 执行 Capability 与 Policy 校验，再通过 Device
Gateway 调用 Adapter。Android Adapter 是唯一构造 logcat 子进程参数的层。因新增 Adapter 端口并
明确非 UI Tool 调用边界，本迭代采用 ADR-0012。
