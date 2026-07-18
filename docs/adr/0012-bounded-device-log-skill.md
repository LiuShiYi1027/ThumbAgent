# ADR-0012: 通过受控 Tool/Skill 采集有界设备日志

- Status: Accepted
- Date: 2026-07-15
- Deciders: Mobile Agent Team

## Context

工程诊断需要读取 Android logcat，但设备日志可能包含账号标识、令牌、路径和业务数据，输出规模也
可能失控。直接暴露 ADB/logcat 参数、把 stdout 内联到 REST，或让 Skill 直接调用 Android Adapter，
都会破坏命令安全、Tool/Skill 分层和数据最小化边界。

## Decision

- 新增平台无关 `logs.collect@1` Capability，V1 由 Android ADB Adapter 实现。
- 底层 `device.logs.capture` 注册为仅供 Skill 调用的 Tool；通用 Action Tool 入口直接调用时返回
  `TOOL_REQUIRES_SKILL`。
- 对外提供 deterministic `device.logs.collect@1` Skill，风险为 Medium，必须显式确认。
- Android 只构造固定 `logcat -d -t <1..2000> -v threadtime *:<level>` 参数数组。调用方不能提供
  tag、PID、buffer、格式、文件路径或任意 ADB/Shell 参数。
- 原始输出先受进程输出和超时限制，再进行本地脱敏；最终 `.log` Artifact 最大 1 MiB。公共结果
  只返回 Artifact 引用、大小、截断和脱敏计数，不内联日志正文。
- 第一版是同步“最近日志快照”，持有短期设备 Lease 并绑定连接 Session；不提供持续流式采集。

## Consequences

- 日志能力可被 Web、CLI 和未来 MCP 以统一 Skill 语义消费，且不会扩大任意命令能力。
- 脱敏只能降低常见敏感信息暴露概率，不能保证识别业务自定义秘密，因此仍需用户确认并保持本地。
- 快照采集无法覆盖问题发生前已被 ring buffer 淘汰的日志，也不能替代长时间复现采集。
- `DeviceAdapter` 增加平台无关日志端口，所有 Adapter 必须显式实现或返回能力不可用。

## Alternatives Considered

- 暴露自由格式 logcat filters：灵活，但会形成命令参数逃生口并扩大数据采集范围。
- 把日志当作普通 UI ActionResult：现有 Observe–Act–Verify 结构不适合大文本 Artifact。
- 本迭代直接实现持续异步流：覆盖更完整，但会同时引入生命周期、取消、并发读取和持久化任务协议变化。

## Follow-up

- 评估独立的异步诊断 Task 类型、持续采集、复现窗口和协作式取消。
- 增加按应用进程过滤时，必须使用结构化、可验证的应用/进程选择器，不能接收原始 logcat 表达式。
- 在导出诊断包前增加用户可检查的 Artifact 清单与删除入口。
