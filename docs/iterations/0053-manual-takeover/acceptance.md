# ITER-0053 Acceptance

> 文档状态：Completed
> 迭代状态：Completed
> 更新日期：2026-08-20

## 验收条件

1. **暂停端点**：`POST /v1/task-executions/{task_id}/pause`
   - 无 token 401；不存在任务 404；QUEUED 或终态任务 409 `TASK_STATE_CONFLICT`；
   - RUNNING 任务返回 202，执行持久化 `pause_requested=true` 并发出 `task.pause_requested`；
   - 重复暂停幂等返回当前状态。
2. **恢复端点**：`POST /v1/task-executions/{task_id}/resume`
   - 无 token 401；不存在任务 404；未暂停任务 409；
   - PAUSED 任务返回 202，恢复后状态回到 running 并发出 `task.resumed`
     （payload 含 `takeover: true`、`resume_reason`）。
3. **执行语义**：暂停在安全边界生效（不强杀在途调用）；暂停期间无新设备动作；
   deadline 在暂停中继续计时，到期自动恢复并以 `timed_out` 结束；暂停中取消自动恢复
   并以 `cancelled` 结束；暂停期间设备租约不释放。
4. **崩溃恢复**：SQLite 中 `paused` 状态的执行在 Runtime 重启后以 `TASK_INTERRUPTED`
   失败，不自动续跑。
5. **Contract**：task-execution 增加 `paused` 与 `pause_requested`，task-event 增加三个
   事件类型；`make contracts` 重新生成的 TS 类型与工作区一致；新增 Contract 测试通过。
6. **桌面 UI**：RUNNING 显示「暂停（人工接管）」，PAUSED 显示「恢复执行」与接管横幅；
   设备画面栏暂停期间显示接管占位；时间线正确渲染三种新事件。oxlint 与 tsc 通过。
7. 完整 `make check` 与 `make check-desktop` 各通过一次。
8. 真机 Low 风险验证：`settings.display-brightness.v1` 执行中暂停 → 确认事件与无新动作 →
   人工操作设备 → 恢复 → 任务基于新画面继续至终态，事件流完整记录接管区间。

## 验收记录

| 条件 | 结果 | 证据 |
| --- | --- | --- |
| 1 暂停端点 | 通过 | `runtime/tests/test_api_security.py`：无 token 401、未知任务 404、非空 body 400、RUNNING 任务 202 且 `pause_requested` 翻转；`test_async_task_execution.py`：QUEUED 409 `TASK_STATE_CONFLICT`、重复暂停幂等（仅一条 `task.pause_requested`）、终态幂等返回 |
| 2 恢复端点 | 通过 | 同上 API 测试覆盖 401/404/202；执行器测试覆盖未暂停 409、PAUSED 恢复后回 running 并发出 `task.resumed`（`takeover: true`、`resume_reason: user`） |
| 3 执行语义 | 通过 | 执行器测试：探针边界生效（暂停中 `second_probe` 未触发）、暂停×取消 → `cancelled`（resumed reason=cancel）、暂停×deadline → `timed_out`（resumed reason=deadline，预算不延长）、租约语义未改动；真机 E2E 确认暂停 6 秒窗口内零新轮次 |
| 4 崩溃恢复 | 通过 | `test_sqlite_recovery_fails_paused_execution_without_replay`：SQLite 中 paused 执行恢复为 `TASK_INTERRUPTED`/`unknown_outcome`，不续跑 |
| 5 Contract | 通过 | task-execution 增 `paused`/`pause_requested`、task-event 增三事件类型；`make contracts` 重生成与工作区一致（`generate_ts_contracts.py --check` 过）；`test_async_execution_contracts_are_versioned` 增补断言 |
| 6 桌面 UI | 通过 | `npm run lint`（oxlint 0 错误）与 `npm run typecheck`（tsc -b）通过；RUNNING 显示「暂停（人工接管）」、PAUSED 显示「恢复执行」+接管横幅、设备画面栏接管占位、报告内接管区间（paused/resumed 配对）、时间线三新事件标签 |
| 7 完整门禁 | 通过 | 2026-08-20 `make check`（387 tests）与 `make check-desktop`（clippy + 17 Rust tests + oxlint + tsc）各通过一次 |
| 8 真机验证 | 通过 | 2026-08-20 14:25 真机 `adb:A6TG025A13002156`：任务 `task_3077b0434f67441c8b1da80fed727532` 首个动作轮后 pause → `task.paused` → 6 秒接管窗口零新轮次 → resume → `task.resumed(takeover, user)` → 再 3 轮后 `succeeded`；事件序列 1–10 完整记录接管区间 |
