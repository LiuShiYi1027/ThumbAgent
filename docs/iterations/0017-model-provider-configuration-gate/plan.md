# ITER-0017 Model Provider Configuration Gate

> 状态：Completed
> 更新日期：2026-07-09

## 背景

ITER-0016 已经实现默认关闭的 OpenAI-compatible Planner Provider Preview。下一步需要建立显式配置门，确保真实模型 Provider 只有在用户明确启用、配置模型端点和密钥引用后才会被构造。

## 目标

提供一个默认安全的 Planner Provider 配置入口：

```text
ModelProviderSettings(enabled=false)
    → RuleBasedPlanner

ModelProviderSettings(enabled=true, provider=openai_compatible, ...)
    → SecretResolver.resolve(api_key_ref)
    → OpenAICompatiblePlanner
```

## 范围

### 本迭代实现

- 新增 `ModelProviderSettings`。
- 新增 `SecretResolver` 端口。
- 新增 `build_planner_from_settings`。
- 默认配置返回 `RuleBasedPlanner`。
- 显式启用 OpenAI-compatible Provider 时校验：
  - provider 类型
  - base_url
  - model
  - api_key_ref
  - timeout_seconds
- 测试使用 fake secret resolver 和 fake transport，不读取真实环境变量、配置文件或 Keychain。

### 本迭代不实现

- 不把 Provider 配置接入默认 Runtime。
- 不读取真实密钥。
- 不提供 Web UI 配置页。
- 不发真实网络请求。
- 不改变 Agent 支持目标范围。

## 安全边界

- 默认关闭。
- 配置对象只保存 `api_key_ref`，不保存原始 API key。
- Secret 获取通过注入的 `SecretResolver` 完成。
- 错误 details 不包含密钥值。
- 即使启用 Provider，Planner 输出仍需经过结构解析和 Runner allowlist。

## 验收

以 [acceptance.md](./acceptance.md) 的必选验收全部通过为准。
