# ITER-0019 任务拆解

> 状态：Completed
> 日期：2026-07-10

## 任务

- [x] 增加本地模型配置文件读取。
- [x] 增加模型配置环境变量覆盖。
- [x] 增加受限 `EnvironmentSecretResolver` 预览。
- [x] 将默认 Runtime 接入配置读取，缺失配置时保持 disabled。
- [x] 修正模型错误 details，避免暴露 `api_key_ref` 原文。
- [x] 增加配置读取、环境变量覆盖、SecretResolver 和脱敏错误测试。
- [x] 更新 README、技术方案和迭代索引。

## 环境变量

- `MOBILE_AGENT_MODEL_CONFIG`
- `MOBILE_AGENT_MODEL_ENABLED`
- `MOBILE_AGENT_MODEL_PROVIDER`
- `MOBILE_AGENT_MODEL_BASE_URL`
- `MOBILE_AGENT_MODEL_NAME`
- `MOBILE_AGENT_MODEL_API_KEY_REF`
- `MOBILE_AGENT_MODEL_TIMEOUT_SECONDS`

开发预览 SecretResolver 只允许读取形如 `MOBILE_AGENT_MODEL_SECRET_*` 的环境变量。
