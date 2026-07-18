# ITER-0019 验收标准

> 状态：Completed
> 日期：2026-07-10

## 验收项

- [x] 配置文件不存在时，Runtime 使用 disabled / rule-based 默认配置。
- [x] 有效配置文件可以生成启用状态的 `ModelProviderSettings`。
- [x] 环境变量可以覆盖配置文件中的非密钥字段和 `api_key_ref` 引用。
- [x] SecretResolver 只解析 `env:MOBILE_AGENT_MODEL_SECRET_*` 引用。
- [x] 错误、状态 API 与测试快照不包含真实密钥或 `api_key_ref` 原文。
- [x] 默认 Agent Runner 仍不调用真实模型。

## 验证命令

```bash
PYTHONPATH=runtime python3.11 -m unittest runtime.tests.test_model_provider_config runtime.tests.test_api_security runtime.tests.test_runtime_service runtime.tests.test_web_ui
make check
git diff --check
```
