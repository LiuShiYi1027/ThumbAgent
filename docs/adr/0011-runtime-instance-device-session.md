# ADR-0011：Runtime 单实例与设备连接会话

- Status: Accepted
- Date: 2026-07-14
- Deciders: Team

## Context

进程内 DeviceLease 只能阻止同一 Runtime 内的并发写入。两个 Runtime 若共享数据目录，仍可能
同时操作设备和 SQLite；设备断开后以相同 device_id 重连时，旧任务也可能错误地继续执行。

## Decision

- 每个 Runtime 数据目录使用一个非阻塞 POSIX 文件锁，同一目录只允许一个 Runtime 进程。
- Device Gateway 为每段连续在线连接分配不可复用的 `session_id`；离线、消失再出现均创建新会话。
- 写任务在取得 DeviceLease 时绑定当前 `session_id`，每次 Observation 和动作前重新校验。
- 会话变化以 `DEVICE_SESSION_CHANGED` 终止旧任务，不在新连接上自动续跑。
- TaskRun 与 TaskExecution 记录实际绑定的设备会话，供报告和审计使用。

Runtime 单实例、Device Session 与 DeviceLease 是独立边界：前者协调本机数据目录进程，中者标识
一次连续设备连接，后者协调某次连接上的写 Owner。

## Consequences

- 第二个共享数据目录的 Runtime 会在创建服务和令牌前明确失败。
- USB 瞬断后的旧任务不会把后续动作发送到新的连接会话。
- 当前锁依赖 POSIX `flock`，适用于 V1 的 macOS/Linux 本地 Runtime，不是分布式锁。
- Runtime 重启后会生成新的内存会话身份；旧非终态任务仍按既有恢复策略失败，不自动重放。

## Alternatives Considered

- 只依赖端口占用：不同端口无法阻止共享数据库和设备的双 Runtime。
- 只依赖 device_id：同一序列号重连后无法区分旧连接与新连接。
- 自动在新会话续跑：可能重复或错序执行已有真实副作用的动作。

## Follow-up

- 桌面端 sidecar 生命周期接入单实例错误提示。
- 后续多设备调度仍须以 `(device_id, session_id)` 作为执行绑定，不复用旧 Session。
