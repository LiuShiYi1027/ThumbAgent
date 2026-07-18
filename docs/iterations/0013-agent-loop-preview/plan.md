# ITER-0013 Agent Loop Preview

> 状态：Completed
> 更新日期：2026-07-09

## 背景

ITER-0012 已经让本地 Web UI 能发起固定 demo 任务，并在任务结束后查看报告。这个闭环证明了“产品能看见”，但任务本质仍是一个固定 Skill 调用。

在接入真实大模型前，需要先建立 Agent Loop 的最小骨架，让模型未来只负责输出受约束的决策，而不是直接操作设备或绕过 Tool/Policy/Task Store。

## 目标

完成一个不依赖真实 LLM 的 Agent Loop Preview：

```text
用户目标
    → 观察设备
    → Planner 生成结构化决策
    → Runner 经过 allowlist 执行 Skill
    → 保存 Agent 轮次、决策理由、执行结果和证据
    → 形成 TaskRun 报告
```

## 范围

### 本迭代实现

- 新增 Agent Planner 抽象。
- 新增 deterministic `RuleBasedPlanner`，只支持安全示范目标：进入系统设置的显示/亮度页面。
- 新增 Agent Runner，执行最多一轮 preview 决策。
- 新增本地 API：`POST /v1/tasks/agent.run`。
- 将 Agent 决策、观察摘要和 Skill 结果写入现有 `TaskRun.steps[].result`。
- 保存到现有 Task Store，并可通过任务历史、CLI 报告和 Web 报告查看。

### 本迭代不实现

- 不接真实 LLM。
- 不实现自由规划、多轮复杂任务或工具自动选择。
- 不新增原子设备动作。
- 不实现 iOS、鸿蒙真实 Adapter。
- 不允许模型或 Planner 输出任意 shell、ADB 命令或未注册 Tool。
- 不改变现有 `settings.scroll_navigate` demo API。

## 设计约束

- Planner 输出一律视为不可信输入，Runner 必须做 allowlist 校验。
- Preview 只允许调用 `settings.scroll_navigate` Skill。
- Agent Runner 必须绑定明确 `device_id`。
- 每次任务至少记录一次前置 Observation 摘要。
- 失败必须形成结构化错误和任务报告，而不是静默抛出。
- 默认测试不依赖真实设备、网络或模型服务。

## API 草案

```http
POST /v1/tasks/agent.run
Authorization: Bearer <local-runtime-token>
Content-Type: application/json

{
  "device_id": "adb:...",
  "goal": "进入显示和亮度页面",
  "confirmed": true,
  "max_rounds": 1
}
```

返回：

```json
{
  "task": {
    "task_type": "agent.run",
    "status": "succeeded",
    "steps": [
      {
        "kind": "agent_round",
        "name": "agent.round",
        "result": {
          "round": 1,
          "planner_id": "rule_based.preview",
          "decision": {
            "decision_type": "run_skill",
            "skill_id": "settings.scroll_navigate",
            "reason": "..."
          }
        }
      }
    ]
  }
}
```

## 验收

以 [acceptance.md](./acceptance.md) 的必选验收全部通过为准。
