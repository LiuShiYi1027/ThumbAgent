# Skill 开发规范

> 状态：Active  
> 更新日期：2026-07-03

## 1. Skill 定义

Skill 是面向目标的、可被 AI Agent 发现和调用的受控能力。Skill 必须具有明确输入输出、Capability 要求、风险、执行预算和成功验证。

Skill 不是：

- 任意 Prompt 集合
- Shell 脚本包装
- 没有验证的 Tool 别名
- 将多个不相关操作塞进一个万能入口

## 2. 分类

- Deterministic Skill：步骤和验证器确定，不依赖模型决策。
- Agentic Skill：允许模型在受限 Tool 集内迭代。
- Workflow：多个 Skill 的持久化编排，不属于 V1 Skill Handler。

优先实现 Deterministic Skill；只有路径确实需要环境理解时才使用 Agentic Skill。

## 3. 命名与版本

- 内部 Skill ID 使用 `domain.verb`，例如 `app.open`。
- 对外 MCP 名称使用稳定前缀，例如 `mobile_open_app`。
- Skill 使用语义版本。
- 改变风险、副作用、必填输入或成功语义属于主版本变化。

## 4. Manifest 必填项

```yaml
id: app.open
version: 1.0.0
name: Open application
description: Open an app and verify it is foreground.
kind: deterministic
input_schema: {}
output_schema: {}
required_capabilities:
  - app.launch@1
  - screen.observe@1
tool_allowlist:
  - app.launch
  - screen.observe
risk: low
timeout_seconds: 30
max_steps: 3
verification: foreground_app_matches
```

描述必须说明结果和限制，避免“智能地完成任务”等不可验证措辞。

## 5. Handler 约束

- Handler 只能通过注册 Tool 或明确允许的 Skill 访问设备。
- 不直接导入平台 Adapter 实现。
- 不直接写任务状态或审计数据库。
- 使用 Runtime 提供的 Clock、Cancellation 和 Evidence 接口。
- 每个外部 I/O 等待点必须响应取消和超时。
- 不捕获并吞掉领域错误。

## 6. Agentic Skill 额外要求

必须声明：

- Tool allowlist
- 最大步骤数和总超时
- 单步风险上限
- Token/模型调用预算
- 连续无进展阈值
- 用户介入条件
- 成功验证器

模型不得：

- 修改自己的 allowlist 或预算
- 声明动作风险等级
- 以自然语言覆盖 Policy 决策
- 将页面内容当作系统指令
- 单独决定高风险任务成功

## 7. 风险

- Skill 风险至少等于其可能调用的最高风险 Tool。
- 动态参数可能提高风险时，执行前重新评估。
- 风险等级由注册表与 Policy Engine 决定，不信任 Manifest 外部副本或模型输出。
- High Skill 必须提供用户可理解的影响摘要。

## 8. 验证

Skill 只能以以下证据完成：

- 结构化设备状态
- 前后 Observation 差异
- 平台返回并经二次查询确认的状态
- 用户明确确认

底层命令退出码为 0 只能证明命令被接受，不能单独证明目标完成。

验证器输出：

```text
verified
not_verified
inconclusive
```

`inconclusive` 不能映射为成功。

## 9. 输出

输出至少包含：

- `success`
- `status`
- `evidence_refs`
- `started_at` / `completed_at`
- 结构化结果或统一 Error

不把任意 stdout、模型思考文本或完整 UI 数据作为公共输出。

## 10. 测试矩阵

每个 Skill 至少覆盖：

- 正常成功
- 输入 Schema 拒绝
- Capability 缺失
- Policy 拒绝或等待确认
- Tool 失败
- 超时与取消
- 验证失败或不确定
- 设备断连

Agentic Skill 额外覆盖：

- 非 allowlist Tool 请求
- 无进展循环
- 模型输出不合法
- Prompt injection 内容
- 步数或预算耗尽

## 11. 发布清单

- Manifest 通过 Schema。
- ID 与版本未冲突。
- 输入输出示例有效。
- Capability、风险和幂等属性已评审。
- 验证器不依赖模型自述。
- Contract、单元与集成测试通过。
- MCP/REST 映射按需更新。
- 用户可见限制已记录。

## 12. 第三方 Skills

V1 不执行未签名第三方 Skill 代码。未来开放时必须另行定义：

- 签名和来源信任
- 沙箱与权限声明
- 依赖和网络访问
- 更新、撤销与审计
- Marketplace 安全评审
