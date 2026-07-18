# ITER-0020 Controlled Model Planner Runtime

> 状态：Completed
> 日期：2026-07-10

## 目标

在显式模型配置启用且密钥引用可解析时，将 OpenAI-compatible Planner 受控接入默认 Runtime 的 Agent Runner。

## 背景

ITER-0019 已经支持 Runtime 读取本地模型配置，但默认 Agent Runner 仍固定使用 `RuleBasedPlanner`。本迭代把模型 Planner 接入执行链路，同时保持失败可解释、密钥脱敏和默认关闭。

## 范围

### 本迭代实现

- Runtime 启动时根据 `ModelProviderSettings` 构造 Planner。
- `enabled=false` 时继续使用 `RuleBasedPlanner`，状态为 `disabled`。
- `enabled=true` 且密钥引用可解析时使用 OpenAI-compatible Planner，状态为 `active`。
- `enabled=true` 但模型不可用时注入 `UnavailablePlanner`，状态为 `unavailable`。
- `UnavailablePlanner` 在决策阶段返回 `MODEL_UNAVAILABLE`，任务报告明确失败，不静默退回规则 Planner。
- `/v1/model-provider/status` 展示 `active/unavailable/disabled`，错误信息脱敏。

### 本迭代不实现

- 不扩大 Agent Skill allowlist。
- 不新增设备动作或高风险能力。
- 不记录真实 prompt、模型响应全文、密钥或密钥引用原文。
- 不提供 Web UI 模型配置编辑。
- 不接入正式 Keychain SecretResolver。

## 安全边界

模型输出仍然必须经过：

```text
模型响应
  → AgentDecision 结构化解析
  → Agent Runner Skill allowlist
  → Skill 参数校验
  → Tool Registry
  → Policy Engine
  → Device Gateway
```

模型不能直接执行 Tool、ADB、Shell 或绕过策略。
