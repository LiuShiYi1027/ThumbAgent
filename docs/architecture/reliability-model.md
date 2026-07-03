# 可靠性与执行语义

> 状态：Active  
> 更新日期：2026-07-03

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
- 人工接管持有更高优先级锁并暂停 Agent。
- 锁过期不代表设备动作可安全重试，只代表需要重新协调所有权。

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
