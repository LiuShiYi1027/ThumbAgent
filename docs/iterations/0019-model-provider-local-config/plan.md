# ITER-0019 Model Provider Local Config

> 状态：Completed
> 日期：2026-07-10

## 目标

为模型 Provider 增加本地配置读取能力，让 Runtime 能在启动时读取显式模型配置，并把脱敏后的状态展示给本地 API 与 Web UI。

## 背景

ITER-0018 已经提供模型 Provider 只读状态面板，但状态只能来自注入的默认配置。下一步需要让 Runtime 能从本地配置文件和受控环境变量读取配置，同时继续保持真实密钥不进入配置文件、日志、API 或测试快照。

## 范围

### 本迭代实现

- 增加 `load_model_provider_settings`。
- 默认读取 `<data-dir>/model-provider.json`，缺失时使用安全默认值。
- 支持 `MOBILE_AGENT_MODEL_CONFIG` 指定配置文件路径。
- 支持 `MOBILE_AGENT_MODEL_*` 环境变量覆盖配置字段。
- 增加 `EnvironmentSecretResolver` 预览，只解析 `env:MOBILE_AGENT_MODEL_SECRET_*` 形式的显式引用。
- Runtime 默认加载本地配置，并继续只在状态面板展示脱敏信息。
- 修正模型不可用错误，避免返回 `api_key_ref` 原文。

### 本迭代不实现

- 不在默认 Agent Runner 中启用真实模型 Planner。
- 不读取或保存真实 API key。
- 不提供 Web UI 配置编辑。
- 不接入系统 Keychain。
- 不新增第三方配置库或模型 SDK。

## 配置示例

```json
{
  "enabled": true,
  "provider": "openai_compatible",
  "base_url": "https://model.example/v1",
  "model": "example-model",
  "api_key_ref": "env:MOBILE_AGENT_MODEL_SECRET_EXAMPLE",
  "timeout_seconds": 30
}
```

真实密钥必须放在外部密钥源中。本迭代仅提供开发预览用的环境变量 resolver；正式桌面端应进入 Keychain 方案。
