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
