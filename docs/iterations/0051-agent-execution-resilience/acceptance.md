# ITER-0051 Acceptance

> 文档状态：Active
> 迭代状态：Active
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

（Verifying 阶段填写：task_id、终态、指标数值、make check 结果。）
