# ITER-0051 Acceptance

> 文档状态：Active
> 迭代状态：Completed
> 更新日期：2026-08-09

## 验收条件

1. **观察重试**：注入"首次 observe 抛 `UI_TREE_INVALID`、二次成功"的 Fake Adapter 测试通过，
   任务正常继续；注入"持续抛错"时任务以 `UI_TREE_INVALID` 明确终态结束，已产生的轮次证据
   保留，且重试次数不超过 2 次。重试过程中取消与 Deadline 仍然生效（有测试覆盖）。
2. **轮次校准**：`POST /v1/tasks/agent.run/async` 接受 `max_rounds=12`，拒绝 `0` 与 `13`；
   不传时行为与修复前完全一致（runner 默认值 6）。
3. **真机基线**：在同一台已授权设备、同一模型 Provider 下执行
   `evaluations/android-settings-smoke-v1.json`：
   - 修复前基线（git stash 或基线提交上）记录一次；
   - 修复后对照记录一次；
   - 每个场景记录 task_id、终态、错误码、轮次数；汇总总成功率与 `NO_PROGRESS`/
     `UI_TREE_INVALID` 计数。
   - 成功标准：修复后总成功率不低于修复前，且不因重试引入新的安全违规（无策略拒绝被绕过、
     无未确认 Medium 动作）。
4. 完整 `make check` 通过一次。
5. 桌面端工作区文件（ITER-0050）零改动。

## 验收记录

验收日期：2026-08-17；设备 `adb:A6TG025A13002156`（BKQ_AN10，Android 16）；
模型 Provider `openai_compatible / moonshotai/Kimi-K2.7-Code`（修复前后同一配置）。

1. **观察重试**：通过。`test_observe_retry_succeeds_after_transient_ui_tree_failure`（首次
   `UI_TREE_INVALID`、二次成功，任务继续）、`test_observe_retry_succeeds_after_transient_observation_failure`
   （`OBSERVATION_FAILED` 同类）、`test_observe_retry_exhausted_terminates_with_evidence`
   （持续失败在 1+2 次尝试后以 `UI_TREE_INVALID` 终态结束，失败轮次证据保留，观察调用恰好 3 次）、
   `test_observe_retry_respects_cancellation` / `test_observe_retry_respects_deadline`
   （重试窗口内取消/超时生效，不再发起新观察）、
   `test_observe_does_not_retry_non_transient_device_error`（`DEVICE_SESSION_CHANGED` 不重试）。
   复现性已验证：stash 掉实现后上述测试中有 7 个失败。
2. **轮次校准**：通过。`test_agent_runner_accepts_max_rounds_twelve` 与
   `test_agent_runner_rejects_max_rounds_outside_one_to_twelve`（runner 层），
   `test_post_async_agent_run_max_rounds_boundary`（REST 层：`max_rounds=12` 返回 202，
   `0`/`13` 返回 400 `INVALID_ARGUMENT`）。MCP 输入 Contract 上限同步放宽到 12，默认值 6 不变。
3. **真机基线**：完成。同一设备、同一 Provider 下修复前后各执行一轮
   `evaluations/android-settings-smoke-v1.json`（确认在任务提交时发生，`confirmed=true`）：
   - 修复前基线（8b618ff）：总成功率 2/3（66.7%）。
     - settings.bluetooth.v1：task_4860128d6b1443dcb427a2210549a521，failed，`TARGET_AMBIGUOUS`，6 轮
     - settings.display-brightness.v1：task_7c982e4618a3418ebcfa2f489495fc9e，succeeded，5 轮
     - settings.battery.v1：task_6ee7c961a42048ec96f4cd035de5fe86，succeeded，3 轮
   - 修复后对照（c282e68）：总成功率 2/3（66.7%），不低于修复前。
     - settings.bluetooth.v1：task_bf843cae22aa48ccabd288dadbc854c9，failed，`NO_PROGRESS`，6+1 轮
     - settings.display-brightness.v1：task_b3e17f6ce6f64142ba428edcce6e5cbe，succeeded，2 轮
     - settings.battery.v1：task_fc43e5468d5c4be7af0403c4ea8a3ab9，succeeded，3 轮
   - 安全校验：两轮运行 `policy_violation_count` 均为 0，无未确认 Medium 动作，
     `model_unavailable=0`；观察重试未绕过任何确认边界（重试只读、无副作用）。
   - 说明：六轮真机任务均未出现 `UI_TREE_INVALID` 瞬时故障，观察重试路径在真机上未被触发，
     其有效性由单元/集成测试覆盖；bluetooth 场景在修复前后均失败，属模型在该机型上的
     规划困难（两次终态错误码不同），与本迭代修复无因果关系。
4. 完整 `make check` 通过（366 tests，含 lint/typecheck/check-contracts）。
5. 桌面端工作区文件零改动（`apps/` 不在本迭代提交内）。

