# ITER-0020 复盘

> 状态：Completed
> 日期：2026-07-10

## 完成内容

本迭代完成了模型 Planner 到默认 Runtime 的第一条受控接线：配置关闭时走规则 Planner；配置开启且可用时走 OpenAI-compatible Planner；配置开启但不可用时，Agent 任务以 `MODEL_UNAVAILABLE` 明确失败。

## 关键取舍

- 没有在模型不可用时静默回退规则 Planner，因为这会让用户误以为真实模型参与了决策。
- 用 `UnavailablePlanner` 复用现有 Agent Runner 的错误报告能力，避免在 Runner 内增加特殊分支。
- 保持 Skill allowlist 不变，真实模型只替换“计划者”，不扩大可执行能力。
- 状态面板只展示脱敏错误码和消息，不展示密钥引用值。

## 后续建议

下一步可以做真实模型的手动端到端验证与体验保护：

- 提供一份本地配置模板和启动说明；
- 在 Web UI 中增加模型状态说明和不可用提示；
- 对模型调用失败、结构化输出失败分别优化用户提示；
- 再往后接入 Keychain SecretResolver。
