# ITER-0033 Runtime Single Instance & Device Session

> 状态：Completed
> 日期：2026-07-14

## 背景

ITER-0032 的租约只在单进程内生效，且 device_id 无法表达设备断开重连这一执行边界。

## 目标

- 同一数据目录只允许一个 Runtime 实例。
- 为每段连续在线设备连接建立 Session。
- 写任务绑定 Session，并在重连后拒绝旧任务继续动作。
- 在 Device、TaskRun、TaskExecution 与 Web/CLI 报告中暴露安全的会话标识。

## 非目标

- 不实现分布式锁、跨主机协调或多设备并行调度。
- 不自动恢复或续跑断连前的写任务。
- 不实现 iOS、鸿蒙真实 Adapter。

## Contract 兼容性

- Device 新增必需但可为空的 `session_id`；在线 Runtime 设备返回会话 UUID。
- TaskRun 新增可选 `device_session_id`，旧历史任务保持可读。
- TaskExecution 新增必需但可为空的 `device_session_id`；旧 JSON 读取为空，运行后写入实际值。
- SQLite 表结构不变，新增字段保存在版本化 JSON 中，无需数据库迁移。

## 里程碑

1. Runtime 数据目录单实例锁与 ADR。
2. 平台无关 Device Session Gateway 与重连检测。
3. Lease、同步/异步任务、报告和 Contract 接入。
4. 回归测试、双进程冒烟与复盘。
