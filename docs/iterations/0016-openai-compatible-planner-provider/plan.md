# ITER-0016 OpenAI-Compatible Planner Provider Preview

> 状态：Completed
> 更新日期：2026-07-09

## 背景

ITER-0015 已经定义了 LLM Planner 的内部结构化输出契约和 `MockLLMPlanner`。下一步需要为真实模型接入准备 Provider 边界，但仍不能默认调用网络、读取密钥或让模型直接操作设备。

## 目标

实现一个可测试、默认不启用的 OpenAI-compatible Planner Provider 预览：

```text
goal + observation summary
    → prompt/request body
    → injectable transport
    → response JSON extraction
    → parse_llm_decision_payload
    → AgentDecision
```

## 范围

### 本迭代实现

- 新增模型 Provider 端口和配置对象。
- 新增 `OpenAICompatiblePlanner`。
- 使用标准库 HTTP transport，并允许测试注入 fake transport。
- 解析 chat-completions 风格响应中的 JSON object。
- 补充无网络测试：
  - 请求体包含目标和观察摘要。
  - Authorization header 不进入错误 details 或报告。
  - 合法响应转换为 `AgentDecision`。
  - 非 JSON 响应返回 `MODEL_OUTPUT_INVALID`。
  - transport 失败返回 `MODEL_UNAVAILABLE`。

### 本迭代不实现

- 不在默认 Runtime 中启用真实 Provider。
- 不读取环境变量、配置文件或 Keychain 中的模型密钥。
- 不发真实网络请求。
- 不扩展 Agent 支持的目标范围。
- 不实现流式输出、多模态输入或工具调用 API。

## 安全边界

- Provider 只生成 Planner 决策，不能执行设备动作。
- Provider 输出仍需通过 `parse_llm_decision_payload`。
- Runner 仍需执行 Skill allowlist。
- Prompt 中只放最小 observation summary，不发送截图、完整 UI 树或密钥。
- 错误 details 不包含 token、完整请求体或原始响应全文。

## 验收

以 [acceptance.md](./acceptance.md) 的必选验收全部通过为准。
