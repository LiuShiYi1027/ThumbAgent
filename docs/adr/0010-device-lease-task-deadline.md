# ADR-0010: Runtime 设备租约与任务总 Deadline

- Status: Accepted
- Date: 2026-07-14
- Deciders: Mobile Agent Team

## Context

ITER-0031 增加异步任务队列，但旧同步 Agent、直接 Tool 和 Skill API 仍可能与异步任务同时操作
同一设备。模型和设备调用也可能持续较长时间，只有 Provider timeout 不能表达整个任务的时间预算。

## Decision

- 在 Runtime Application 层新增进程内 `DeviceLeaseManager`。公开写 Tool、Skill、确定性任务、
  同步 Agent 和异步 Agent 都必须先取得同一 `device_id` 的独占租约。
- 只读设备发现和 Observation 不占写租约，报告与评测也不占租约。
- 租约包含 owner、取得时间和期限。期限仅用于诊断；即使期限已过，也不能自动把设备交给另一个
  Owner，因为原设备动作可能仍在执行。只有持有者明确释放或 Runtime 重启才能清除租约。
- 异步 Agent 与其他入口发生租约冲突时以 `DEVICE_LOCKED` 结束，不在设备状态未知时自动等待或
  重试；同步入口直接返回 HTTP 409。
- `agent.run` 新增可选 `deadline_seconds`，默认 600 秒，范围 1–1800 秒。异步执行从真正进入
  running 时开始计时，排队时间不消耗任务预算。
- Runner 在 Observation 后、Planner 后和每轮动作验证后检查 deadline。不会强杀模型线程或
  ADB 进程；到达安全边界后返回 `timed_out/TASK_DEADLINE_EXCEEDED` 并禁止下一步动作。
- 已经完成且验证过的动作保留在 TaskRun，deadline 不伪装成动作撤销或普通失败。

## Consequences

- Web、同步 API 和直接 Tool 不再能并发写同一台设备。
- 用户可以在 TaskExecution 和 TaskRun 中看到 deadline 预算；Web 将 `timed_out` 视为终态。
- 进程内租约符合当前单 Runtime V1，但不能协调两个独立 Runtime 进程。产品启动层仍应确保同一
  数据目录只运行一个 Runtime。
- 异步任务在租约冲突时会失败而不是无限等待，调用方可在确认原任务终态后重新提交。
- 模型或 ADB 调用超过 deadline 时，UI 可能在调用返回前仍显示 running；这比强制中断后误判
  设备副作用更安全。

## Alternatives Considered

- 在 Adapter 内加锁：会把任务调度语义下沉到平台实现，并让 iOS/鸿蒙重复实现产品策略。
- 每个 Tool 独立加锁：Agent 持有租约时内部 Tool 会产生嵌套锁冲突，且任务中间可能被抢占。
- 租约到期自动抢占：无法证明旧写动作已经停止，可能导致并发副作用。
- 对整个协程使用 `asyncio.wait_for`：取消传播无法证明设备动作是否已经发送，容易错误标记结果。

## Follow-up

- 增加 Runtime 单实例锁和 Device Session 标识，将租约绑定到连接会话。
- 为 Provider transport 与 ADB Runner 增加显式取消令牌和分层 deadline 预算。
- 在明确安全的前提下评估租约等待队列、人工接管和租约续期事件。
