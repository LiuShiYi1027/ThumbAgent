# ITER-0026 Acceptance

> 状态：Active
> 更新日期：2026-07-13

## 验收标准

- [x] 缺失 `resolve_clickable_ancestor=true` 的 `input.tap_element` 在设备动作前被拒绝。
- [x] Tool 参数的缺失字段、多余字段、类型和范围受 Contract 约束。
- [x] Provider 只对 `MODEL_OUTPUT_INVALID` 追加一次脱敏修复请求。
- [x] 修复成功的 Decision 记录 `repair_count=1`。
- [x] 第二次仍无效时以 `MODEL_OUTPUT_INVALID` 失败，不进入设备动作。
- [x] 合法 ToolCall 执行失败时，failed step 保留 Observation 和 Decision。
- [x] 未通过 allowlist/Contract 的决策不保存未受信参数为失败 step result。

## 验证命令

```bash
PYTHONPATH=runtime python3.11 -m unittest \
  runtime.tests.test_agent_runner \
  runtime.tests.test_openai_compatible_provider

make check
```

## 证据要求

- 单元测试覆盖无效点击参数、修复成功和动作失败证据。
- Contract 测试验证新 Schema ID 和 `repair_count`。
- 默认测试不依赖真机、网络或模型密钥。
- 真机 E2E 需在 Runtime 重启后由用户显式发起，不进入默认快速测试集。
