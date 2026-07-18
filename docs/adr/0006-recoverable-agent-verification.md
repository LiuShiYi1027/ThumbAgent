# ADR-0006: 可恢复 Agent 验证与有界 Provider 重试

- Status: Accepted
- Date: 2026-07-13
- Deciders: Mobile Agent Team

## Context

真机任务已正确进入蓝牙页面，但 `finish` 的文本 Selector 同时匹配页面标题、开关和开关文字，
Runtime 以 `TARGET_AMBIGUOUS` 终止任务。另一真机任务将屏幕底部被手势条遮挡的元素视为可点击，
动作无变化后第二次模型请求超时，但所有 Provider 异常都被压缩为无详情的
`MODEL_UNAVAILABLE`。

这些错误在发生时均没有产生未知设备副作用，直接终止会降低简单任务的稳定性。

## Decision

- `finish` 支持可选的前台 app/activity 与必需的 UI Selector 组合验证。
- `finish` 的 `TARGET_NOT_FOUND` / `TARGET_AMBIGUOUS` 以及 Tool 派发前的目标定位错误是可恢复轮次。
- 可恢复轮次保留 failed step 和 Error，并将脱敏结构化 feedback 交给下一轮 Planner；不伪装为成功。
- 相同无进展决策再次出现时，仍以 `NO_PROGRESS` 停止。
- 语义点击在派发前排除屏幕顶部和底部各 4% 的启发式系统安全边距，由模型决定滑动恢复。
- Provider 错误区分 timeout、HTTP status、connection 和 invalid JSON，且不记录响应体或密钥。
- 仅对 retryable 且没有设备副作用的模型 HTTP 请求自动重试一次。

## Consequences

- 任务可以从验证歧义、目标未进入安全点击区域等确定失败中自主恢复。
- TaskRun 可以在最终 succeeded 时包含中间 failed step；客户端必须分开展示每轮状态与终态。
- 短暂 Provider 故障可能导致一次额外模型调用和延迟，报告必须展示重试次数。
- 顶部和底部 4% 安全边距是 V1 的保守通用值；后续应由 Adapter 提供真实 system insets。

## Alternatives Considered

- 文本匹配多个时直接成功：会将任意页面中的普通文本误判为目标页。
- Runtime 自动滑动后点击：会隐藏本应由 Agent 决策的页面导航。
- 对所有设备动作重试：无法区分已产生副作用和结果未知，不符合可靠性模型。

## Follow-up

- Android Adapter 增加结构化 system insets，替换通用顶部和底部边距。
- 将外部 AgentEvaluationScenario 的验收条件直接绑定到 Runtime 成功判定。
