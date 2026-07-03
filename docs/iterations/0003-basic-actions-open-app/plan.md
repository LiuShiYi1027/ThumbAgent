# ITER-0003: Basic Actions & Open App

> 状态：Completed  
> 更新日期：2026-07-03  
> Owner：Codex

## 目标

建立第一条受 Contract、Capability 和 Policy 约束的真实设备动作链，支持启动应用、Back、Home 和坐标点击，并实现可验证的 `app.open` 确定性 Skill。

## 范围

- Action、Tool Result 和 Skill Result Contracts
- Tool Registry 与风险元数据
- 最小 Policy Engine：Low 自动允许、Medium 需要确认、High/Prohibited 拒绝
- Android `app.launch`、`navigation.back`、`navigation.home`、`input.tap`
- 动作前后 Observation 与结构化结果
- `app.open@1` Deterministic Skill
- Runtime Tool/Skill API
- Fake Adapter、自动化测试和可逆真机验收

## 非目标

- 文本输入和滑动
- 任意 Shell、应用安装或清除数据
- Agent Loop 和模型规划
- 持久化任务状态机
- 完整用户确认 UI
- 多设备并发

## 真机安全边界

- 只验证启动系统设置、Back 和 Home。
- `input.tap` 只使用 Fake Adapter 验证，不在真机随机点击。
- 不修改系统开关、不输入文本、不提交表单。
- 所有真机动作前后生成 Observation。

## 完成条件

以 [acceptance.md](./acceptance.md) 必选项与真机安全验收通过为准。
