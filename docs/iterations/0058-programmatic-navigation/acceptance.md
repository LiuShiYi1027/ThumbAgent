# ITER-0058 Acceptance

> 文档状态：Active
> 迭代状态：Completed
> 更新日期：2026-08-24

## 功能验收

- [x] `app.navigate` 只接受已登记枚举 ID；未知 ID 返回 `NAVIGATION_ACTION_UNKNOWN`，且发生在任何进程调用之前。
- [x] Adapter 对每个枚举 Action 只构造固定 `am start -a <action>` 参数数组；不存在任何接受原始 Action、Component、URI 或 extras 的代码路径。
- [x] 导航执行后强制验证前台包名/Activity；验证不符返回 `NAVIGATION_NOT_VERIFIED` 或 `ACTION_OUTCOME_UNKNOWN`，不自动重试。
- [x] `device.notifications.read` 有界返回（数量与字段大小上限），公共输出只含包名、截断标题与时间戳；正文与原始 dumpsys 输出不进入公共响应、日志或 Artifact 之外的位置。
- [x] 通知解析失败返回 `NOTIFICATIONS_READ_FAILED`，确认零通知返回 `NOTIFICATIONS_READ_EMPTY`，两者不以空列表混淆。
- [x] Capability 缺失、设备离线、Session 变化返回统一领域错误；Policy 确认语义与 `logs.collect@1` 一致（Medium 风险需确认）。
- [x] REST 与 MCP 入口不直接访问 ADB，REST 标记只读/幂等语义，MCP 不暴露原子 Tool。
- [x] Agent 对已登记安全捷径优先走确定性路径；捷径未命中时逐轮 `run_tool` 行为与 ITER-0057 前完全一致（回归测试证明）。

## 工程验收

- [x] Contract 正向、反向与无效样本测试通过；`contracts/generated` 与 Schema 一致。
- [x] 默认测试、类型检查、格式检查与 Contract 形状回归全部通过（一次集中 `make check`，426 通过）。
- [x] ADR-0018 已创建并记录枚举收紧、禁 extras、Runtime 捷径优先的决策与后果。
- [x] capability-model.md、technical-design-v1.md、error-handling.md 与迭代索引已同步。

## 真机 E2E（集中一次执行）

设备：Honor BKQ-AN10（MagicOS），2026-08-24 集中执行，两套脚本均全部通过
（`scripts/e2e_iter0058.py`、`scripts/e2e_iter0058_transport.py`）。

- [x] 通过 MCP 调用 `app.navigate` 进入 Wi-Fi 设置页，前台 Activity 验证通过，未产生其他设备变更。
- [x] 通过 MCP 对未登记枚举 ID 调用，MCP 输入 Schema 枚举约束在设备动作前拦截
  （`INVALID_ARGUMENT`）；经 REST 直达时 Domain 边界返回 `NAVIGATION_ACTION_UNKNOWN`
  （HTTP 400），设备无动作。两层拒绝均发生在任何进程调用之前。
- [x] 通过 REST 读取通知快照，返回结构符合脱敏 Contract；Medium 风险确认流程完整走通
  （未确认返回 403 `CONFIRMATION_REQUIRED`）。
- [x] 自然语言任务「进入 Wi-Fi 设置页面」命中程序化捷径，`completion_source=runtime_shortcut`、
  轮次数 0，终态前台验证一致。

真机发现并修复的两个 ROM 差异，详见 retrospective.md「偏差与限制」。
