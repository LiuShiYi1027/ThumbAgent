# 可靠性与执行语义

> 状态：Active
> 更新日期：2026-07-14

## 1. 目标

设备动作具有真实副作用，Runtime 必须区分“确定失败”和“结果未知”，并为超时、取消、重试、断连和恢复提供一致语义。

## 2. 核心原则

- 命令成功不等于目标成功。
- 超时不等于设备没有执行。
- 取消只能阻止后续工作，不能假装撤销已经发生的动作。
- 自动重试只用于明确安全、幂等且结果可判断的操作。
- 不确定状态优先观察或请求用户介入，不盲目重复动作。

## 3. 动作结果

每个 Action 使用以下结果之一：

- `succeeded`：动作执行且后置验证通过。
- `failed`：确定没有完成，或验证明确失败。
- `cancelled`：在动作开始前取消，或执行器确认动作未发生。
- `timed_out`：等待超过预算，且结果可确定为未完成。
- `unknown_outcome`：动作可能已经发生，但无法确认。
- `rejected`：Schema、Capability 或 Policy 阻止执行。

`unknown_outcome` 不得自动转换为 `failed` 或自动重试。

## 4. Task 状态

```text
draft → ready → running
                  ├→ paused → running
                  ├→ awaiting_confirmation → running / cancelled
                  ├→ awaiting_user → running / cancelled
                  ├→ unknown_outcome → awaiting_user / failed / succeeded
                  ├→ succeeded
                  ├→ failed
                  ├→ timed_out
                  └→ cancelled
```

Task 进入 `unknown_outcome` 时必须停止后续写动作，先尝试只读 Observation 和验证。

`paused` 由 `POST /v1/task-executions/{task_id}/pause` 显式请求（ITER-0053）：请求持久化后
在轮次安全边界生效，不强杀在途模型或 ADB 调用；暂停期间不派发新动作、继续持有设备租约，
供用户直接在设备上人工接管。`/resume` 恢复后 Agent 基于最新 Observation 重新规划。
Task deadline 在暂停期间继续计时：到期自动恢复并按超时收尾；暂停中收到取消请求同样
自动恢复并按取消收尾。Runtime 重启时 `paused` 与 `running` 一样以 `TASK_INTERRUPTED`
失败，不在新进程自动续跑。

## 5. 幂等与重试

动作注册时声明：

- `safe`：重复执行不会改变最终语义，例如读取设备列表。
- `conditional`：满足明确条件时可重试，例如启动已知应用。
- `unsafe`：可能重复产生副作用，例如发送、删除、提交。

自动重试还必须同时满足：

- Error 标记 `retryable=true`。
- 结果不是 `unknown_outcome`。
- 未被取消。
- 重试预算未耗尽。
- 设备 Session 未变化。

采用有上限的指数退避并加入 jitter。V1 默认最多重试 2 次；设备写动作默认 0 次。

## 6. 超时

- Process timeout：底层命令预算。
- Action timeout：执行与后置 Observation 总预算。
- Skill timeout：整个目标级能力预算。
- Task deadline：用户任务总预算。

内层超时必须小于外层预算，并预留清理和证据采集时间。不能依赖单一全局 timeout。

V1 Agent 默认 deadline 为 600 秒，可配置范围 1–1800 秒，从任务真正开始运行时计时。Deadline
不会强杀未知状态的设备调用；调用返回并完成确定性验证后，Runtime 在安全边界停止下一步动作。

ITER-0037 的异步日志快照使用相同 Task deadline，默认 60 秒。取消或 Deadline 发生在 ADB 调用
期间时不强杀设备命令；调用返回后停止后续步骤，并保留已经生成的 Artifact 与完成步骤证据。

ITER-0041 起，非流式 OpenAI-compatible 请求按 `response_headers`、`response_body` 和
`response_decode` 记录可观察失败阶段，并记录毫秒耗时、尝试与重试次数。标准库 Transport 无法可靠
拆分 DNS、TCP、TLS 和首 Token，因此报告不得声称这些更细阶段。Provider 重试仍只发生在当前任务、
当前 Planner 决策内，不授权客户端在任务终态后自动创建替代任务。

语义点击优先使用目标中心；若中心落入顶部或底部系统安全区，但目标 bounds 仍有安全可点击部分，
Runtime 将点击点约束到该安全交集的中部。目标完全位于安全区时继续在派发前拒绝，不产生设备副作用。

性能基线比较只消费两个已经进入 succeeded 终态的 TaskRun，不参与设备动作重试、取消或恢复。
不同设备、失败任务和时间倒序在读取阶段明确拒绝；Device Session 不同作为结果事实公开，不被
静默当作同一连续测量。两点趋势使用公开噪声阈值，不能自动升级为性能回退结论。

## 7. 取消

- 取消请求必须持久化并传播到当前执行上下文。
- 子进程收到取消后先优雅终止，超时后强制结束。
- 如果动作已发送到设备且无法判断是否生效，结果为 `unknown_outcome`。
- 取消后禁止启动新的写动作。
- 清理操作只能是本地资源释放或已证明安全的设备操作。

## 8. 设备断连

断连时：

1. 停止派发新动作。
2. 标记 Device Session 失效。
3. 判断当前动作是 failed 还是 unknown_outcome。
4. 保存最后 Observation 和错误证据。
5. Task 进入 `paused`、`awaiting_user` 或 `unknown_outcome`。

设备重连产生新 Session。未经用户或验证器确认，不在新 Session 自动续跑旧写动作。

V1 由 Device Gateway 的平台无关 Session Tracking 装饰器维护连续在线状态。Task 在每次
Observation 和写动作前核对绑定 Session；设备消失、非 online 或重新出现均使旧绑定失效并返回
`DEVICE_SESSION_CHANGED`。Session 变化不触发自动重试。

## 9. Runtime 崩溃恢复

- 启动时扫描非终态 Task。
- 未开始的 Task 可恢复为 `ready`。
- 正在执行的只读动作重新观察后判断。
- 正在执行的写动作默认恢复为 `unknown_outcome`。
- 不自动重放 ToolCall。
- 记录 Runtime restart audit event。

## 10. 设备锁与租约

- 同一 Device Session 同时最多一个写任务。
- 锁具有 Owner、创建时间和租约。
- 续租失败停止新动作。
- 人工接管持有更高优先级锁并暂停 Agent。V1 单机场景中该更高优先级锁即人对设备的
  物理持有：Runtime 侧通过 ITER-0053 的 `paused` 状态停止派发，任务租约不释放，
  暂停-恢复区间以 `task.paused` / `task.resumed` 事件计入证据。
- 锁过期不代表设备动作可安全重试，只代表需要重新协调所有权。

V1 租约由单 Runtime 进程管理，公开写 Tool、Skill 和 Task 共享同一 device_id 锁。租约到期只
产生诊断信息，不自动释放或抢占；持有者离开执行上下文时明确释放。详见 ADR-0010。

同一数据目录另由 Runtime 单实例文件锁保护。单实例锁解决跨进程所有权，Device Session 解决
重连身份，DeviceLease 解决写任务并发；三者不可互相替代。详见 ADR-0011。

## 11. Verification

动作后置验证优先顺序：

1. 查询平台结构化状态。
2. 比较前后 Observation。
3. 使用专用确定性验证器。
4. 请求用户确认。

模型判断只能作为建议，不能单独把不确定结果升级为成功。

## 12. 测试要求

- 超时发生在发送动作前和发送动作后两种情况。
- 取消在等待、执行、验证阶段的行为。
- 写动作 unknown outcome 不自动重试。
- 断连和重连 Session 变化。
- Runtime 重启恢复非终态任务。
- 设备锁租约过期和人工接管。
