# ITER-0017 Acceptance

> 状态：Completed
> 更新日期：2026-07-09

## 必选验收

- [x] 默认配置返回 `RuleBasedPlanner`。
- [x] 显式启用 OpenAI-compatible 配置可构造 `OpenAICompatiblePlanner`。
- [x] 缺少 provider/model/base_url/api_key_ref 返回结构化错误。
- [x] secret resolver 失败返回 `MODEL_UNAVAILABLE`。
- [x] 错误 details 不包含原始 API key。
- [x] 默认 Runtime 行为不变。
- [x] 默认测试不依赖真实设备、网络或模型服务。
- [x] 全量质量门禁通过。

## 验证记录

| 命令 | 结果 |
| --- | --- |
| `PYTHONPATH=runtime python3.11 -m unittest runtime.tests.test_model_provider_config runtime.tests.test_openai_compatible_provider` | 8 tests, OK |
| `make check` | 98 tests, lint OK, typecheck OK |
| `git diff --check` | OK |

## 真机验证

本迭代不要求真实设备或真实模型 E2E。真实 Provider 启用应在后续显式配置和授权后验证。
