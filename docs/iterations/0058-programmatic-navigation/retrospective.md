# ITER-0058 Retrospective

> 文档状态：Draft
> 迭代状态：Completed
> 更新日期：2026-08-24

## 实际交付

- `app.navigate@1` + `notifications.read@1` 两项 Capability；`app.navigate` / `device.notifications.read`
  确定性 Skill；Android Adapter 枚举制 Settings Action 映射（固定 argv、禁 extras）与
  `dumpsys notification` 有界脱敏解析。
- Agent Runner 导航捷径：关键词命中即一步完成（`completion_source=runtime_shortcut`），
  能力缺失降级回模型循环；捷径执行前强制取消/截止检查；`navigation_shortcuts_enabled` 可关闭。
- REST `/v1/skills/app.navigate/invoke`、`/v1/skills/device.notifications.read/invoke` 与
  对应两个 MCP Tool（含 readOnly/idempotent 注解，target 在 MCP 层即被枚举 Schema 约束）。
- ADR-0018；capability-model.md、technical-design-v1.md、error-handling.md 同步。
- 真机 E2E 脚本两套：`scripts/e2e_iter0058.py`（Runtime 直连）、
  `scripts/e2e_iter0058_transport.py`（REST + MCP stdio 真实链路）。

## 验证结果

- 集中 `make check` 最终通过：lint、类型检查、431 项 unittest、Contract 生成一致性。
- 真机 E2E（Honor BKQ-AN10 / MagicOS，2026-08-24）4 场景全部通过：
  Wi-Fi 设置直达前台验证通过；未知枚举在 MCP Schema 层（INVALID_ARGUMENT）与
  REST Domain 层（`NAVIGATION_ACTION_UNKNOWN`，HTTP 400）双重拦截；通知读取未确认 403、
  确认后返回脱敏结构（10/50 条两档）；自然语言目标命中捷径，0 轮次、终态一致。
- E2E 期间发现并修复 3 个真实缺陷，均有先行回归测试：
  1. 捷径路径绕过取消/截止守卫（补 `_raise_if_stopped`）；
  2. MagicOS dumpsys 脱敏格式 `String [length=N]` 被误认为标题（长度标记按缺失处理）；
  3. MagicOS 冷启动 Settings Action 报 error 102（monkey 预热后有界重试一次）。
- 另修复错误映射缺陷：`NAVIGATION_ACTION_UNKNOWN` 由 503 更正为 400。

## 偏差与限制

- MagicOS 在 dumpsys 中对通知 extras 整体脱敏，标题只能拿到长度标记；该 ROM 上通知快照
  实际提供包名 + 发布时间，标题恒为 null。这是平台行为，不是解析缺陷；其他 ROM 待观察。
- Settings 冷启动预热依赖 monkey LAUNCHER 入口，预热会短暂把设置主页带到前台再跳转目标页，
  用户可感知一次页面切换。
- 捷径关键词表目前覆盖中文高频表述与部分英文；表述偏离关键词时仍走模型循环（行为正确，
  只是不享受捷径加速）。
- MCP 层未知枚举拒绝码（INVALID_ARGUMENT）与 REST/Domain 层（NAVIGATION_ACTION_UNKNOWN）
  不同，已在 acceptance.md 记录为预期的分层语义。

## 效率指标

- Active → Verifying → Completed：1 天（2026-08-24）。
- 计划 Task 5 个，全部完成；无取消；新增计划外修复 4 项（均为 E2E/回归暴露的真实缺陷）。
- 完整 `make check` 共 3 次（431 项测试最终全绿）；真机 E2E 集中 1 轮、2 套脚本。
- 范围扩张：无（预热重试与解析兼容均属于验收发现的缺陷修复，不是新能力）。

## 后续行动

- ITER-0059 候选：CJK 输入法 helper（方案甲切片遗留）。
- 观察 `runtime_shortcut` 完成占比与关键词命中率，评估扩大捷径覆盖的目标族。
- 更多 ROM（小米 HyperOS、OPPO ColorOS、原生 Pixel）的 Settings Action 冷启动与通知
  dumpsys 格式采样，必要时扩充解析器与预热策略。
- Deep Link B 档 URI 白名单治理保持独立迭代与 ADR，不在捷径中开洞。
