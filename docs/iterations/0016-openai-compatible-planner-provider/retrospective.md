# ITER-0016 Retrospective

> 状态：Active
> 更新日期：2026-07-09

## 实际交付

- 新增 `runtime/mobile_agent/providers` 模块。
- 新增 `OpenAICompatiblePlannerConfig`、`ModelTransport`、`HttpModelTransport` 和 `OpenAICompatiblePlanner`。
- Provider 构造 chat-completions 风格请求，使用最小 observation summary。
- Provider 解析 `choices[0].message.content` 中的 JSON object，并复用 `parse_llm_decision_payload`。
- fake transport 测试覆盖合法响应、非 JSON 输出、transport 失败和 token 不泄露。
- README 与技术方案已同步记录 Provider 默认关闭边界。

## 验收结果

- 定向测试 12 tests OK。
- 全量 `make check` 94 tests OK，lint/typecheck OK。

## 计划偏差

- 未把 Provider 接入默认 Runtime，符合本迭代“Provider Preview 默认关闭”的范围。
- 未读取环境变量或 Keychain 中的模型密钥，避免提前扩大安全边界。

## 有效做法

- 使用可注入 transport，让默认测试完全无网络、无模型密钥。
- Provider 错误 details 只包含本地生成的 response id，不保留 token、请求体或原始响应全文。
- 复用 ITER-0015 的 Planner 输出解析，避免 Provider 自己定义第二套决策语义。

## 问题与根因

- 目前只支持非流式 chat-completions 风格响应；流式、多模态和工具调用需要后续单独设计。
- Prompt 仍是最小版本，后续真实模型接入前需要版本化 prompt 和评测集。

## 长期文档回写

- README 和技术方案已记录 OpenAI-compatible Provider Preview。
- 本迭代未改变默认 Runtime 行为、持久化 Schema 或安全信任模型，不需要 ADR。

## 后续行动

- 下一步可以做 Provider 配置入口，但默认保持关闭，并要求用户显式提供密钥。
- 真实模型启用前需要补充数据边界提示、prompt injection 策略和模型调用审计。
