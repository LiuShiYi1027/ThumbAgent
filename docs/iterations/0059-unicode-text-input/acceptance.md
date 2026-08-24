# ITER-0059 Acceptance

> 文档状态：Active
> 迭代状态：Active
> 更新日期：2026-08-24

## 功能验收

- [ ] `input.unicode_text` 接受 CJK、空格与常见标点，长度有界；纯 ASCII 仍走现有快路径。
- [ ] 验证码（4–8 位数字）、手机号（11+ 位数字）等敏感形态在 Tool 层拒绝，先于任何设备动作。
- [ ] IME 切换前记录原默认输入法，完成后恢复；恢复失败返回 `IME_RESTORE_FAILED` 并显著上报。
- [ ] 输入后读回目标输入框内容验证；不一致返回 `TEXT_INPUT_NOT_VERIFIED`，不自动重试。
- [ ] helper 未安装/未启用返回 `IME_HELPER_NOT_INSTALLED`，引导经 `app.install` 两阶段流程安装。
- [ ] 广播 action 与参数数组固定；不存在任何接受原始 Intent extras 的代码路径。
- [ ] REST 与 MCP 入口不直接访问 ADB；MCP 不暴露原子 Tool。

## 工程验收

- [ ] ADR-0019 已创建，记录 helper 分发信任模型、IME 切换/恢复语义与读回验证容差。
- [ ] Contract 正向、反向与无效样本测试通过；`contracts/generated` 与 Schema 一致。
- [ ] 默认测试、类型检查、格式检查与 Contract 形状回归全部通过（一次集中 `make check`）。
- [ ] capability-model.md、technical-design-v1.md §11.4、error-handling.md 与迭代索引已同步。

## 真机 E2E（集中一次执行）

- [ ] MagicOS 设备中文输入到可编辑框，读回验证一致，任务结束后原 IME 已恢复。
- [ ] helper 未安装时返回 `IME_HELPER_NOT_INSTALLED`，设备无状态变更。
- [ ] 敏感数字形态输入被拒绝，设备无动作。
- [ ] 自然语言中文任务（如「在设置中搜索 显示」）经模型循环完成输入步骤。
