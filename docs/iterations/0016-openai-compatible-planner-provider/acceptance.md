# ITER-0016 Acceptance

> 状态：Completed
> 更新日期：2026-07-09

## 必选验收

- [x] Provider 请求体包含用户目标和 observation summary。
- [x] 合法 chat-completions 风格响应可转换为 `AgentDecision`。
- [x] 非 JSON 或无结构化内容返回 `MODEL_OUTPUT_INVALID`。
- [x] transport 失败返回 `MODEL_UNAVAILABLE`。
- [x] 错误 details 不包含 Authorization token。
- [x] 默认 Runtime 不启用真实 Provider。
- [x] 默认测试不依赖真实设备、网络或模型服务。
- [x] 全量质量门禁通过。

## 验证记录

| 命令 | 结果 |
| --- | --- |
| `PYTHONPATH=runtime python3.11 -m unittest runtime.tests.test_openai_compatible_provider runtime.tests.test_agent_runner` | 12 tests, OK |
| `make check` | 94 tests, lint OK, typecheck OK |
| `git diff --check` | OK |

## 真机验证

本迭代不要求真实设备或真实模型 E2E。真实 Provider 启用必须在后续迭代中显式配置和授权。
