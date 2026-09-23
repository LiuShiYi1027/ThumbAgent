# ITER-0068 Desktop Stability Skill（桌面稳定性测试入口）

> 文档状态：Draft
> 迭代状态：Active
> 创建日期：2026-09-22
> 关联：[ITER-0062](../0062-declarative-skill-dsl/plan.md) · [ITER-0065](../0065-stability-reporting/plan.md)

## 背景

`app.stability_test@1.1.0` 已能从 REST 提交，桌面报告也能画采样曲线。桌面工作台只能提交自然语言 Agent 任务：sidecar 的 POST 白名单不含 `skill.dsl.run`，用户在官方客户端上启动不了稳定性测试。

## 目标

- 桌面「新任务」增加「稳定性测试」：选择就绪设备、填写包名、确认后提交官方 `app.stability_test@1.1.0`。
- 提交走既有异步任务、时间线和报告。默认时间盒 120 秒（任务 deadline 180 秒），让采样和收尾日志有机会完成。
- sidecar 只新增这一条 POST。同步 Skill 调用、自定义 Skill 注册仍然拒绝。

## 非目标

- 不做 Skill 管理页、自定义 DSL 编辑或任意 `skill_id`。
- 不跑官方 10 分钟全程测量。
- 不改 DSL 解释器或稳定性报告算法。

## 关键决策

1. 桌面写死官方技能 id 与 1.1.0，避免工作台变成任意技能执行器。
2. 确认框单独说明遍历动作（启动、滑动、返回、性能采样、日志采集）。
3. 包名在提交前按应用 id 形态校验，非法值不发请求。

## 兼容性

- 自然语言任务路径不变。
- 无 Contract 破坏性变更。sidecar 白名单是桌面进程内约束。

## 风险

- 短时间盒仍可能在收尾日志前触达 deadline。文案说明「到时间结束并保留已采集采样」，不承诺每次都有崩溃判定。

## 测试

- Rust：新 POST 路径在白名单内；`/v1/skills/.../invoke` 仍拒绝。
- Desktop `tsc`。
- 真机桌面点击若本环境无法拉起 Tauri，记为待目检，不以类型检查代替点击验收。
