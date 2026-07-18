# ITER-0021 验收标准

> 状态：Completed
> 日期：2026-07-10

## 验收项

- [x] Web UI 展示模型 Provider 状态卡片。
- [x] `active` 状态提示模型输出仍受 allowlist 和 Policy 约束。
- [x] `unavailable` 状态提示检查配置文件和 `MOBILE_AGENT_MODEL_SECRET_*`。
- [x] UI 不展示 `api_key_ref` 原文或真实密钥。
- [x] 仓库提供可复制的模型配置示例。
- [x] 测试覆盖 UI 状态文案入口。

## 验证命令

```bash
PYTHONPATH=runtime python3.11 -m unittest runtime.tests.test_web_ui runtime.tests.test_api_security
make check
git diff --check
```
