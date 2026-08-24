# ADR-0018: 程序化系统设置导航与 Runtime 导航捷径

- Status: Accepted
- Date: 2026-08-24
- Deciders: Mobile Agent Team

## Context

V1 的 Agent 通过 Observe-Plan-Act 循环逐轮探索 GUI。对于“打开显示设置”这类目标明确的系统页面
导航，让模型花多轮点击设置列表既慢又引入不确定性（模型输出不可信、选择器可能误匹配）。
同时，通知读取是高频信息需求，但通知栏包含第三方应用内容，必须有界、脱敏且默认关闭。

关键张力：程序化导航需要用 `am start -a <action>` 这类系统 Intent，如果允许任意 action、
extras 或 Deep Link URI，就等价于一个隐藏的任意命令逃生口，违背 ADR-0003 与安全规则。

## Decision

- 新增 `app.navigate@1` Capability（Low 风险、条件幂等、需要确认后置验证），只允许
  `NavigationTarget` 枚举白名单内的 14 个系统设置页面；枚举值到 `android.settings.*` action
  的映射固定在 Android Adapter 内，固定参数数组，禁止 extras 与任意 URI。
- 每次导航后重新 Observation，用目标页面的 Activity token 做后置验证，失败抛
  `NAVIGATION_NOT_VERIFIED`，outcome 记为 unknown。
- `am start -W -a <action>` 在部分厂商 ROM（实测 MagicOS）上无法冷启动 Settings 进程
  （error 102）；Adapter 在动作失败时先用固定 monkey LAUNCHER 参数预热 Settings 进程，
  再有界重试一次原动作。这是确定性状态变更后的单次重试，不适用于验证失败。
- 未知目标在 Domain 边界解析为 `NAVIGATION_ACTION_UNKNOWN`，不进入 Adapter。
- Agent Runner 在主循环前执行确定性捷径：目标文本命中注册系统页面关键词时，直接调用
  `app.navigate`，一步完成并记 `completion_source=runtime_shortcut`、步骤名
  `agent.shortcut`；设备缺少能力（`CAPABILITY_UNAVAILABLE`）时降级回模型循环。
- 捷径同样是设备动作，执行前必须通过取消与截止时间检查；可通过
  `navigation_shortcuts_enabled=False` 关闭（测试 Planner 循环或嵌入方要求纯模型路径时使用）。
- 新增 `notifications.read@1` Capability（Medium 风险、safe 幂等、需用户明确确认）：经
  `dumpsys notification` 只读解析，标题截断 32 字符、数量上限 50，结果写入
  `device_notifications` Artifact；读取失败与零记录分别映射
  `NOTIFICATIONS_READ_FAILED` / `NOTIFICATIONS_READ_EMPTY`。

## Consequences

- 导航类目标从多轮模型探索降为一次确定性动作，任务报告仍可审计（捷径步骤进入 TaskRun 与事件流）。
- 白名单之外的系统页面、任意 Deep Link、CJK 文本输入等不在本次范围，必须作为新能力单独评审。
- Planner 循环行为不变；既有测试与嵌入方若依赖循环结构，可显式关闭捷径。
- Contract、Capability、REST 与 MCP Tool 均为兼容性新增，无需数据库迁移。

## Alternatives Considered

- 任意 Deep Link / 自定义 action 参数：表达力更强但构成任意命令逃生口，拒绝。
- 把导航意图交给模型逐轮探索：慢且不可控，与 Runtime 程序化捷径优先原则冲突。
- 通知读取走无障碍或通知监听服务：需要额外权限与长驻组件，V1 不引入。
- 捷径命中但后置验证失败时静默降级回循环：会掩盖导航失败事实，选择显式报错。

## Follow-up

- 真机验证 14 个设置页面在主流厂商 ROM 上的 Activity token 覆盖率。
- ITER-0059 评估 CJK 输入法 helper 与更多注册页面的扩展方式。
- 观察 `runtime_shortcut` 完成占比，评估是否扩大捷径覆盖的目标族。
