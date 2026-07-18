# ITER-0018 Model Provider Status Surface

> 状态：Completed
> 日期：2026-07-10

## 目标

在本地 Web UI 中展示模型 Provider 的只读状态，让“未来接入真实大模型”的产品入口先可见，同时保持默认关闭、安全脱敏、不可编辑。

## 背景

ITER-0016 和 ITER-0017 已经完成 OpenAI-compatible Planner Provider 预览与配置门，但用户在产品界面无法判断当前 Runtime 是否启用了模型 Provider。

本迭代先做状态展示，不做真实模型启用、不读取真实密钥、不把配置编辑能力暴露给 Web UI。

## 范围

### 本迭代实现

- Runtime 暴露模型 Provider 只读状态。
- Local API 增加 `GET /v1/model-provider/status`。
- Web UI 展示 provider、model、是否启用、是否存在密钥引用。
- 状态返回不得包含真实密钥，也不得包含 `api_key_ref` 原文。
- 补充单元测试与 UI shell 测试。

### 本迭代不实现

- 不接入真实模型到默认 Runtime。
- 不提供 Web UI 配置编辑。
- 不读取 Keychain、环境变量或配置文件。
- 不改变 Agent Runner 的默认 Planner。
- 不改变 Skill、Tool、Policy 或 Device Adapter 边界。

## 设计约束

- 模型配置仍默认关闭，Runtime 继续使用 `RuleBasedPlanner`。
- UI 状态只读，不能成为配置真源。
- 前端不得接触真实密钥或密钥引用值。
- API 返回字段应面向展示，不暴露敏感实现细节。
