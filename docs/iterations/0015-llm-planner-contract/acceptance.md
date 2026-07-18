# ITER-0015 Acceptance

> 状态：Completed
> 更新日期：2026-07-09

## 必选验收

- [x] `parse_llm_decision_payload` 能将合法 payload 转换为 `AgentDecision`。
- [x] 非对象输出返回 `MODEL_OUTPUT_INVALID`。
- [x] 非法 `decision_type` 返回 `MODEL_OUTPUT_INVALID`。
- [x] 缺少 selector 参数返回 `MODEL_OUTPUT_INVALID`。
- [x] `confidence` 越界返回 `MODEL_OUTPUT_INVALID`。
- [x] Runner 仍拒绝 allowlist 外的 `skill_id`。
- [x] 默认测试不依赖真实设备、网络或模型服务。
- [x] 全量质量门禁通过。

## 验证记录

| 命令 | 结果 |
| --- | --- |
| `PYTHONPATH=runtime python3.11 -m unittest runtime.tests.test_agent_runner runtime.tests.test_task_report_cli runtime.tests.test_web_ui` | 13 tests, OK |
| `make check` | 90 tests, lint OK, typecheck OK |
| `git diff --check` | OK |

## 真机验证

本迭代不要求真实设备 E2E。真实模型和真实设备联调应在后续 Provider 迭代中显式执行。
