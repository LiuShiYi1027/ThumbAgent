# 测试规范

> 状态：Active
> 更新日期：2026-07-03

## 1. 测试金字塔

```text
少量真实设备 E2E
      集成测试
   Contract 测试
大量快速单元测试
```

默认测试集必须在没有 Android 设备、网络和模型密钥的环境运行。

## 2. 单元测试

覆盖：

- 状态机与领域规则
- Policy 决策
- Schema 校验
- selector 匹配
- ADB 输出解析
- 错误映射
- 超时、取消和防循环

单元测试必须确定性运行，不使用真实时间等待。

## 3. Contract 测试

确保：

- JSON Schema 与 Python/TypeScript 类型一致
- Adapter 实现满足统一接口
- Tool/Skill Manifest 与 Handler 一致
- REST、WebSocket 和 MCP 表达同一领域语义
- Error code 和 Task state 没有未经登记的值

## 4. 集成测试

使用 Fake Adapter 和 Fake Model Provider 驱动完整流程。

至少覆盖：

- 成功任务
- 参数错误
- Capability 不足
- 策略拒绝与等待确认
- 元素不存在或不唯一
- 动作后页面无变化
- 设备断连
- 超时、取消和人工接管
- Runtime 重启后的任务处理

## 5. Android Adapter 测试

- ADB Runner 使用 Fake Process Runner 测试参数和超时。
- XML、截图、dumpsys 等解析使用去敏样本 fixture。
- 不在普通测试中调用开发者机器上的 `adb`。
- 真机测试使用显式 marker，例如 `device_e2e`。
- 真机测试结束后恢复可恢复状态，禁止清除用户数据。

## 6. Agent 评测

评测任务必须版本化，包含：

- 初始状态
- 用户目标与约束
- 可用 Tools
- 成功判定器
- 禁止动作
- 步数和时间预算

Prompt 或模型变更至少比较成功率、平均步数、耗时、人工介入率和策略违规数。

在线 E2E 评测与离线轨迹回归必须明确区分：

- 在线 E2E 使用真实设备、当前 App 版本和待评模型，每次从最新 Observation 自主规划；场景不规定固定 ToolCall 序列。
- 在线场景以独立的最终状态、禁用动作、预算和人工介入作为评判依据，不以历史路径相似度打分。
- 离线轨迹只用于复现 Parser、Contract、Policy、Runner 和错误处理问题，不用于衡量模型对高频改版 App 的真实成功率。
- Runtime-owned 成功条件必须覆盖：all-of 成功、条件不满足后的可恢复反馈、歧义 Selector、无效请求在设备动作前被拒绝，以及未提供条件时的兼容路径。
- Goal 编译必须覆盖：严格 Contract、编译阶段零设备动作、LLM 草案未确认拒绝、确认后使用 execution_goal、TaskRun 保留 source_goal，以及旧直接运行路径兼容。
- 异步任务必须覆盖：202 提交、逐轮事件顺序、排队取消零设备动作、运行中安全边界取消、
  Idempotency-Key 重放与冲突、SQLite 重启中断，以及同步端点兼容。
- 设备租约与 deadline 必须覆盖：同步/异步/直接 Tool 冲突、释放后重入、过期不抢占、无动作
  deadline、动作验证后 deadline、timed_out 持久化，以及无效预算在设备调用前拒绝。
- Runtime 单实例与 Device Session 必须覆盖：同数据目录锁竞争、释放后重启、连续在线 Session
  稳定、消失/离线后重连生成新 Session，以及旧 Session 在设备动作前被拒绝。
- Runtime Readiness 必须覆盖：ADB 缺失仍可启动、无设备、offline、unauthorized、busy、ready，
  并断言诊断过程中没有 Observation、模型调用或设备写动作。
- Device Inspection 必须覆盖：Capability Catalog 与 Tool Registry 元数据一致、Medium 确认、
  ready/busy/offline 映射、缺失设备，以及检查过程中没有 Observation 或设备写动作。
- 性能比较必须覆盖：同设备成功、不同设备、任务类型/状态错误、时间倒序、缺失可选指标、Session
  差异和稳定阈值，并断言比较过程没有设备或模型调用。
- MCP 必须覆盖：初始化顺序、协议版本协商、Tool Catalog、严格输入、确认缺失、未知 Tool、限流、
  structured error、stdout framing 和 MCP→API→Runtime→TaskStore 跨层链路。默认测试使用无 socket
  Handler Transport，不依赖已启动 Runtime 或网络权限。
- High 风险包管理必须覆盖：Prepare 零设备写动作、范围绑定 Approval、独立明确确认、Capability
  与 Policy 拒绝、固定平台参数、确认后对象变化、后置验证、超时 unknown outcome 和禁止自动重试。
  卸载还必须覆盖系统应用保护与数据保留影响摘要。
- 在线评测 Suite 必须保证 scenario_id 唯一、每个场景覆盖声明的运行次数、task_id 不重复，并同时
  汇总总/分场景成功率、耗时分位数、Provider 重试、无进展、模型不可用和策略违规。聚合过程不得
  调用设备、模型或重放 TaskRun 动作。

## 7. Bug 回归

Bug 修复流程：

1. 添加失败测试或最小复现 fixture。
2. 确认测试在修复前失败。
3. 实现最小修复。
4. 运行相关层级测试。
5. 必要时加入版本化 Agent 评测任务。

## 8. 测试命名

测试名称描述行为和条件，例如：

```text
test_launch_app_returns_capability_error_when_adapter_cannot_launch
test_task_pauses_when_device_disconnects_after_action
test_policy_requires_confirmation_for_medium_risk_input
```

避免 `test_basic`、`test_case_1` 等无语义名称。

## 9. CI 门禁

首个脚手架完成后，CI 至少运行：

- 格式检查
- Lint
- Python 与 TypeScript 类型检查
- 单元测试
- Contract 测试
- 无设备集成测试
- 生成文件一致性检查
- Secret scanning 与依赖安全检查

真实设备 E2E 使用独立、受控的流水线。
