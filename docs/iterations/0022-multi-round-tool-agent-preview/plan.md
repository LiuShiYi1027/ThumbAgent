# ITER-0022 Multi-round Tool Agent Preview

> 状态：Completed
> 日期：2026-07-12

## 目标

将 Agent Preview 从“一轮模型决策调用一个大 Skill”推进到“多轮观察、模型决策、原子 Tool 执行、再观察”的受控闭环。

## 背景

ITER-0020/0021 已经能把真实模型接入 Planner，但执行形态仍偏 deterministic：模型输出 `settings.scroll_navigate`，随后 Skill 内部决定滚动和点击细节。这能提升 demo 稳定性，但不符合 AI Native 的产品方向。滚动方向、点击目标和完成判断应由模型基于每轮 Observation 决策，Runtime 负责安全校验和执行。

## 范围

### 本迭代实现

- 扩展 Planner 决策契约，支持：
  - `run_skill`：兼容旧路径。
  - `run_tool`：执行 allowlist 内原子 Tool。
  - `finish`：请求任务完成，并由 Runtime 做确定性验证。
- Agent Runner 支持最多 6 轮 Observe–Plan–Act。
- Agent Observation Summary 增加紧凑 UI 摘要，让模型能看到当前页面的候选文本和资源 ID。
- OpenAI-compatible Provider prompt 改为多轮 Tool Agent 约束。
- Web Agent Preview 默认使用多轮预算。
- 任务报告记录每轮 observation、decision、tool/action 结果。

### 本迭代不实现

- 不新增高风险 Tool。
- 不允许模型调用任意 Shell、ADB 或未注册 Tool。
- 不接入视觉模型或 OCR。
- 不实现异步任务取消、暂停、设备锁。
- 不扩大到 iOS、鸿蒙或多设备。

## 安全边界

模型输出仍然必须经过：

```text
模型响应
  → AgentDecision 结构化解析
  → Agent Runner Tool/Skill allowlist
  → Tool Registry
  → Capability 检查
  → Policy Engine
  → Device Gateway
  → 下一轮 Observation
```

`finish` 不是模型自述成功。Runtime 必须通过当前 UI 结构或前台应用状态做确定性验证，否则任务失败。

## 验收标准

- 规则 Planner 在无模型时能以多轮 Tool 方式完成打开设置并进入显示页。
- Mock LLM Planner 可通过多轮 `run_tool` + `finish` 完成任务。
- 非 allowlist Tool 仍被策略拒绝。
- 模型输出字段错误仍返回 `MODEL_OUTPUT_INVALID`。
- `make check` 通过。
