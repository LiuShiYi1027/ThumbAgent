# ITER-0020 验收标准

> 状态：Completed
> 日期：2026-07-10

## 验收项

- [x] 默认配置关闭时，Agent Runner 仍使用规则 Planner。
- [x] 显式启用且密钥可解析时，Runtime 构造 OpenAI-compatible Planner。
- [x] 显式启用但密钥不可用时，模型状态为 `unavailable`。
- [x] 模型不可用时，Agent 任务失败为 `MODEL_UNAVAILABLE`，且不执行设备动作。
- [x] 状态 API 和任务错误不包含真实密钥或 `api_key_ref` 原文。
- [x] 模型 Planner 仍受 AgentDecision 解析、Skill allowlist 和 Policy 约束。

## 验证命令

```bash
PYTHONPATH=runtime python3.11 -m unittest runtime.tests.test_runtime_service runtime.tests.test_agent_runner runtime.tests.test_model_provider_config runtime.tests.test_api_security runtime.tests.test_web_ui
make check
git diff --check
```
