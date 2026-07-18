# ITER-0021 Model Provider UX Guardrails

> 状态：Completed
> 日期：2026-07-10

## 目标

让用户在本地 Web UI 中更清楚地理解模型 Provider 当前状态，以及模型不可用时应该检查什么。

## 背景

ITER-0020 已经让 Runtime 具备 `disabled/active/unavailable` 的模型运行态，但 Web UI 仍只展示一行技术字段。用户需要更直接地知道：

- 当前是否使用模型 Planner；
- 模型不可用是否会影响 Agent Preview；
- 下一步该检查配置文件还是密钥环境变量；
- 模型接入后是否仍受安全策略约束。

## 范围

### 本迭代实现

- Web UI 模型 Provider 卡片按状态展示不同视觉样式。
- 状态文案从技术字段变成用户可理解的说明。
- `unavailable` 状态展示脱敏错误 code/message。
- `active` 状态明确提示模型输出仍受 Skill allowlist 和 Policy 约束。
- 新增本地模型配置模板 `docs/examples/model-provider.example.json`。
- 补充 Web UI shell 测试。

### 本迭代不实现

- 不提供 Web UI 配置编辑。
- 不保存或读取真实密钥。
- 不执行真实模型网络 E2E。
- 不扩大 Agent Skill allowlist。

## 安全要求

UI 只展示是否存在密钥引用，不展示 `api_key_ref` 原文或真实密钥。错误展示只允许 code 和用户可读 message。
