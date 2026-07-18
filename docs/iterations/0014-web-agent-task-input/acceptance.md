# ITER-0014 Acceptance

> 状态：Completed
> 更新日期：2026-07-09

## 必选验收

- [x] Web UI 展示自然语言任务输入框。
- [x] Web UI 展示“运行 Agent Preview”按钮。
- [x] 按钮调用 `POST /v1/tasks/agent.run`。
- [x] 未选择设备或目标为空时不发起任务。
- [x] 任务返回后刷新任务列表并打开任务报告。
- [x] 默认测试不依赖真实设备、网络或模型服务。
- [x] 全量质量门禁通过。

## 验证记录

| 命令 | 结果 |
| --- | --- |
| `PYTHONPATH=runtime python3.11 -m unittest runtime.tests.test_web_ui runtime.tests.test_agent_runner` | 6 tests, OK |
| `make check` | 86 tests, lint OK, typecheck OK |
| `git diff --check` | OK |

## 真机验证

本迭代不要求真实设备 E2E；真实设备行为由后续产品验证阶段覆盖。
