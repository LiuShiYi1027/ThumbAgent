# ITER-0015 LLM Planner Contract

> 状态：Completed
> 更新日期：2026-07-09

## 背景

ITER-0014 已经让用户可以在 Web UI 中输入自然语言目标并触发 `agent.run`。当前 Agent Preview 使用 deterministic Planner。接入真实 LLM 前，需要先定义模型输出的受约束语法，并验证错误输出不会进入设备动作层。

## 目标

建立 LLM Planner 的内部预览契约：

```text
LLM/Mock 输出
    → 结构化解析
    → 类型/字段/范围校验
    → AgentDecision
    → Runner allowlist 校验
    → Skill 执行
```

## 范围

### 本迭代实现

- 定义 Planner 输出 payload 的字段和解析规则。
- 新增 `parse_llm_decision_payload`。
- 新增 `MockLLMPlanner`，用于离线验证真实 LLM 接入前的执行链路。
- Agent 决策报告增加 `confidence` 和 `source`。
- 增加非法输出回归测试：
  - 非对象输出
  - 非法 `decision_type`
  - 非法 `skill_id`
  - 参数缺失
  - `confidence` 越界

### 本迭代不实现

- 不调用 OpenAI、OpenAI-compatible 或本地模型服务。
- 不读取、保存或展示模型密钥。
- 不新增任意 shell、ADB 或自由坐标动作。
- 不扩展 Agent 支持目标范围。
- 不将 Planner 输出提升为公开跨语言 Contract；当前仍是 Runtime 内部 preview 契约。

## 输出 payload 草案

```json
{
  "decision_type": "run_skill",
  "skill_id": "settings.scroll_navigate",
  "arguments": {
    "target_selector": {},
    "expected_selector": {}
  },
  "reason": "根据目标需要进入显示/亮度页面",
  "confidence": 0.82
}
```

字段约束：

- `decision_type` 当前只允许 `run_skill`。
- `skill_id` 必须是字符串，且仍需由 Runner allowlist 再次校验。
- `arguments` 必须是对象，且必须包含 `target_selector` 和 `expected_selector`。
- `reason` 必须是非空短文本。
- `confidence` 可选，必须在 `[0, 1]`。

## 验收

以 [acceptance.md](./acceptance.md) 的必选验收全部通过为准。
