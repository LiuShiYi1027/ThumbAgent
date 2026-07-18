# ADR-0014: 性能诊断只保留聚合快照

- Status: Accepted
- Date: 2026-07-15
- Deciders: Mobile Agent Team

## Context

设备性能诊断需要 CPU、内存、电池温度和系统负载，但 Android `dumpsys cpuinfo/meminfo` 原始输出
包含进程名、应用信息和大量无关数据。保存或公开原始输出会扩大隐私范围，也会让跨平台 Contract
绑定 Android 文本格式。性能采集同时新增 DeviceAdapter 能力端口，必须明确其平台边界。

## Decision

- 新增平台无关 `performance.snapshot@1` Capability 和 deterministic
  `device.performance.snapshot@1` Skill，风险为 Low、幂等为 safe。
- Android Adapter 只执行固定的 `dumpsys cpuinfo`、`dumpsys meminfo`、`dumpsys battery`、
  `cat /proc/uptime` 与 `cat /proc/loadavg` 参数数组，不接收客户端参数。
- Adapter 只解析总 CPU、Total/Free RAM、电量、温度、充电状态、uptime 和三段 load average；
  原始输出与进程/应用明细立即丢弃，不进入 Artifact、事件、错误或公共响应。
- 规范化指标使用平台无关 Contract 和明确单位（percent、bytes、seconds、Celsius），保存为本地
  `device_performance/application-json` Artifact。
- 底层 `device.performance.capture` Tool 只能由 Skill 调用，通用 Action 入口直接调用时拒绝。
- 同步 Skill 与 `device.performance.snapshot` 异步任务同时提供；Web 默认使用异步任务。
- 第二个诊断任务出现后，提炼内部 `DiagnosticTaskRunner` 复用取消、Deadline、步骤和证据语义；
  它只接受 Runtime 构造的受信任闭包，不是动态 Handler Registry。

## Consequences

- Artifact 小且结构稳定，可被报告、CLI、未来基线对比和跨平台 Adapter 消费。
- 无法按进程或应用定位性能热点；这是隐私最小化的第一步，后续需另行设计受控目标选择器。
- `dumpsys` 文本格式变化会导致明确的 `PERFORMANCE_SNAPSHOT_FAILED`，不会保存原文供客户端猜测。
- 当前 CPU/memory 命令仍会在 Adapter 进程内短暂持有原始 bytes，但受 Process Runner 超时和输出
  上限保护，解析后不持久化。

## Alternatives Considered

- 保存完整 dumpsys：诊断丰富，但数据量、隐私和跨平台耦合不可接受。
- 在 Host 使用 shell/grep：依赖 shell 且容易产生参数注入，不符合命令安全规范。
- 首版按应用 PID 采样：需要安全解析包名/PID 生命周期和多进程语义，超出聚合快照目标。
- 立即做连续时间序列：需要采样间隔、分片、取消和存储保留策略，适合后续独立迭代。

## Follow-up

- 建立多次聚合快照的基线比较和阈值解释。
- 需要应用级性能时先定义结构化 App Selector、PID 重新解析和敏感数据边界。
- 设计连续采样时复用显式 Task 类型，并增加样本预算、Artifact 分片和保留策略。
