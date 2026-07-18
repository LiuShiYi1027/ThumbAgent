# ITER-0038 Android Performance Snapshot

> 状态：Completed
> 日期：2026-07-15

## 背景

日志 Skill 和异步诊断任务已经验证完整工程链路。下一项 V1 工程能力是性能采集，但必须避免将
Android dumpsys 的进程与应用明细扩散到 Artifact 和公共接口。

## 目标

- 定义聚合性能 Snapshot、Skill Result、Input 和 Manifest Contract。
- 新增 `performance.snapshot@1`、注册 Tool、deterministic Skill 和 Android/Fake Adapter。
- 采集总 CPU、总/Free RAM、电池电量/温度/状态、uptime 和 load average。
- 仅保存规范化 JSON Artifact，不保存原始 dumpsys 或进程/应用明细。
- 同时提供同步 Skill、异步 Task、Web 和 CLI 产品入口。
- 第二个诊断任务出现后提炼共享 DiagnosticTaskRunner。

## 非目标

- 不采集单个应用、PID、线程、GPU、网络流量或帧率。
- 不持续采样、不做时序图、阈值告警或基线比较。
- 不接受任意 dumpsys、文件路径、Shell 或采样命令参数。
- 不实现 iOS、鸿蒙真实 Adapter，不进入安装/卸载包能力。

## Contract 兼容性

- 新增性能 Snapshot/Input/Result Schema、Skill、Capability 和 REST 端点，属于兼容性新增。
- Artifact 新增 `device_performance` 与 `application/json` 枚举；仓库内消费者同步更新。
- TaskExecution/TaskRun 新增 `device.performance.snapshot` 与对应 diagnostic result，属于兼容性枚举新增。
- SQLite 表结构不变，不需要迁移；消费者必须对未知任务和 Artifact 枚举 fallback。

## 架构说明

Android Adapter 是唯一读取并解析 dumpsys/proc 的层；Tool 完成 Capability/Policy 校验并写 Artifact，
Skill 提供稳定目标语义，TaskRunner 只包装生命周期。原始平台文本不跨 Adapter。详见 ADR-0014。
