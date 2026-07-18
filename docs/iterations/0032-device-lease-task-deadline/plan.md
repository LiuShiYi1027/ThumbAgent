# ITER-0032 Device Lease & Task Deadline

> 状态：Completed
> 日期：2026-07-14

## 背景

异步队列内部已经串行，但同步 Agent、直接 Tool 与 Skill 仍可能绕过队列并发操作设备；同时任务
缺少跨多轮模型和设备动作的总执行预算。

## 目标

- 为所有 Runtime 公开写入口建立统一设备租约。
- 同一设备只允许一个写 Owner，冲突使用稳定 `DEVICE_LOCKED`。
- 为同步和异步 Agent 增加任务总 deadline。
- deadline 在安全边界停止后续动作，并持久化 timed_out 报告与证据。
- Web/CLI 展示 deadline，Web 正确识别 timed_out 终态。

## 非目标

- 不实现跨进程或分布式锁。
- 不实现多设备并行、租约优先级或人工抢占。
- 不强杀正在运行的模型线程或 ADB 进程。
- 不把租约过期解释为设备动作已经停止。

## Contract 兼容性

- Agent 请求新增可选 `deadline_seconds`，旧请求使用 600 秒默认值。
- TaskExecution 新增 deadline 字段与 timed_out 状态。
- TaskRun 新增可选 deadline 字段与 timed_out 状态。
- SQLite 表结构不变；旧 TaskExecution JSON 在读取时使用安全默认值并由 API 输出新 Contract。

## 里程碑

1. 设备租约领域边界与 ADR。
2. 同步/异步 Agent deadline 和租约接入。
3. 直接 Tool/Skill 入口统一租约，Web/CLI 展示。
4. 并发、超时、释放测试和运行态验收。
