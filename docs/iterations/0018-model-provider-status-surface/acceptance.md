# ITER-0018 验收标准

> 状态：Completed
> 日期：2026-07-10

## 验收项

- [x] 默认 Runtime 的模型 Provider 状态为 `disabled` / `rule_based`。
- [x] 启用配置的状态可展示 provider 和 model。
- [x] API 与 UI 均不返回、不展示真实密钥或 `api_key_ref` 原文。
- [x] Web UI 能加载 `/v1/model-provider/status` 并展示模型 Provider 状态。
- [x] 默认 Agent Runner 行为不变，仍使用 deterministic Planner。
- [x] 测试覆盖默认状态、脱敏状态和 UI 入口。

## 验证命令

```bash
PYTHONPATH=runtime python3.11 -m unittest runtime.tests.test_model_provider_config runtime.tests.test_runtime_service runtime.tests.test_web_ui
make check
git diff --check
```
