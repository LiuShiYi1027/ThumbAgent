# ITER-0028 Retrospective

> 状态：Completed
> 更新日期：2026-07-13

## 实际交付

- 验证歧义和派发前定位错误成为可恢复 failed round。
- `finish` 新增可选前台 app/activity 条件，并在歧义时反馈候选 resource ID。
- 语义点击在进入屏幕顶部或底部 4% 启发式安全边距时拒绝派发。
- Provider 错误分类、retryable 一次重试、Decision 重试计数与 Web/CLI 展示。
- 无效 Selector 在 Web/CLI 中展示字段名和未知键，不记录 Selector 值或响应体。
- 缺失或空白 `reason` 使用固定审计说明，不触发额外模型请求；可执行字段仍严格校验。
- 失败时保留实际轮次开始时间和最后 Observation/Decision 证据。

## 验证结果

- `make check` 通过：lint、typecheck 和 142 项默认测试成功。
- 蓝牙页面两个同文本节点的离线集成用例已验证“歧义失败 → 收紧 resource ID → 成功”。
- 1256×2808 屏幕上 `tap_y=2737` 的底部目标在 Adapter 调用前被拒绝。
- 1256×2808 屏幕上 `tap_y=83` 的顶部裁切目标在 Adapter 调用前被拒绝。
- 第一轮真实 Provider 对照测试共四项：简短蓝牙成功，其余三项分别受无效 Selector 和两次 Provider 超时影响；详细目标未表现出更高成功率。
- 本地硅基流动配置的 `timeout_seconds` 已由 30 调整为 60；第二轮无任务以
  `MODEL_UNAVAILABLE` 结束，但一次 Provider 重试使单轮耗时接近 120 秒。
- 第二轮真实 Provider 对照测试中，两个简短目标和详细蓝牙均成功；详细显示已进入
  `.Settings$DisplaySettingsActivity`，但因模型连续省略 `reason` 被误判失败。四项设备目标实际均已达成。
- 最终真机复测从京东启动，经过 `app.launch`、语义点击和组合 `finish` 验证，3 轮成功进入
  `.Settings$DisplaySettingsActivity`；无模型修复、无 Provider 重试，任务终态为 `succeeded`。

## 已知限制

- 顶部和底部安全边距是启发式值，尚非 Android system insets 真值。
- Provider 重试无 backoff/Retry-After 调度，当前只提供一次立即重试。
- `finish` 支持一个 Selector 加前台 app/activity；更复杂的 all-of/any-of 业务验证尚未实现。
