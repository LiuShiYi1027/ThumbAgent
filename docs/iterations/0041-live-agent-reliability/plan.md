# ITER-0041 Live Agent Reliability

> 状态：Completed
> 更新日期：2026-07-21

## 背景

MCP 真机验收已经打通 Codex、MCP、Runtime、Planner、Policy、Android Gateway 和任务报告，
但“进入蓝牙设置页面”暴露了两个可复现的可靠性缺口：模型请求连续 60 秒超时时，报告缺少请求阶段和
实际耗时；语义目标的可点击容器部分落入系统安全区时，当前实现仅检查中心点，可能拒绝仍有安全区域
的目标，或在边缘位置点击后页面不变。

## 目标

- 在不记录模型正文、密钥或原始异常的前提下，报告 Provider 请求阶段、实际耗时、尝试次数和重试数。
- 区分等待响应头、读取响应体和响应解码阶段的 Provider 故障。
- 当可点击容器只有一部分落入系统安全区时，选择容器内部的安全点击点；完全位于安全区外时继续拒绝。
- 保持一个 Runtime Task 内的有界 Provider 重试与 Agent 重规划语义，不自动重放设备动作。

## 范围

- OpenAI-compatible Planner Provider 与公共 AgentDecision 的兼容字段扩展。
- `MODEL_UNAVAILABLE.details` 的脱敏诊断扩展。
- `UiLocator` 的安全点击点解析。
- CLI、Web 任务报告和离线回归测试。

## 非目标

- 不新增模型 SDK、流式 Chat Completions 或 Provider 专用协议。
- 不提高设备写动作的自动重试次数。
- 不让 Runtime 在终态后自动创建第二个任务。
- 不扩展 Android 之外的平台 Adapter。

## 兼容性

AgentDecision 仅新增可选、带安全默认值的 `provider_latency_ms` 与
`provider_attempt_count`，属于向后兼容 Contract 变化，不提升 Schema 主版本。错误详情只新增
受控诊断键，不改变 `MODEL_UNAVAILABLE` 既有语义。

## 风险

- 标准库非流式 HTTP 无法精确区分 DNS、TCP、TLS 和首 Token；本迭代使用可观测的
  `response_headers` 与 `response_body` 阶段，禁止把推断包装成事实。
- 调整点击点必须仍位于目标 bounds 内，并保留顶部和底部系统安全边界。

## 里程碑

1. 从真实任务报告提取可复现证据并建立测试。
2. 实现 Provider 诊断与任务报告展示。
3. 实现部分安全区重叠目标的安全点击点。
4. 运行默认测试、Contract、类型和格式检查，再进行真机复测。
