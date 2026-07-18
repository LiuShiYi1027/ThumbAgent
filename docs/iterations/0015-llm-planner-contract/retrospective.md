# ITER-0015 Retrospective

> 状态：Active
> 更新日期：2026-07-09

## 实际交付

- 新增 LLM Planner 内部预览契约解析器：`parse_llm_decision_payload`。
- 新增离线 `MockLLMPlanner`，用于验证未来真实 LLM 输出链路。
- `AgentDecision` 增加 `confidence` 和 `source`，CLI/Web 报告同步展示。
- 增加模型输出非法形状、缺少 selector、confidence 越界和 allowlist 拒绝测试。
- README 和技术方案同步记录边界。

## 验收结果

- 定向测试 13 tests OK。
- 全量 `make check` 90 tests OK，lint/typecheck OK。

## 计划偏差

- 未新增公开 JSON Schema；当前 Planner 输出仍是 Runtime 内部 preview 契约。等真实 Provider、MCP 或桌面端需要共同依赖时再提升到 `contracts/schemas`。
- 未调用真实模型服务，符合本迭代范围。

## 有效做法

- 将“结构化解析”和“Runner allowlist”分成两道门：模型输出合法不代表可以执行。
- 使用 Mock Planner 在无网络、无密钥环境下验证模型式输出。
- 报告中展示 `source/confidence`，便于后续比较 rule/mock/真实模型决策。

## 问题与根因

- 当前 parser 仍只验证最小字段，不做完整 selector schema 校验；完整校验仍由 Skill/Tool 层承担。

## 长期文档回写

- README 和技术方案已记录 LLM Planner Contract preview。
- 本迭代不改变安全信任模型、持久化 Schema 或平台 Adapter，不需要 ADR。

## 后续行动

- 下一步可以实现真实 `OpenAICompatiblePlanner` 的配置模型，但默认仍关闭。
- 接入真实模型前需要补充 prompt 模板、输出截断、超时和敏感信息最小化策略。
