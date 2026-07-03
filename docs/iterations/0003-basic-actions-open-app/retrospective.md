# ITER-0003 Retrospective

> 状态：Active  
> 更新日期：2026-07-03

## 实际交付

- Action 与 Skill Result Contracts。
- 固定 Tool Registry、Capability、风险和幂等元数据。
- Deny-by-default Policy Engine。
- Android/Fake Adapter 的 launch、Back、Home、tap。
- Observe–Act–Verify Tool Runtime。
- `app.open@1` Deterministic Skill。
- Tool 清单、Tool invoke 与 Skill invoke Runtime API。
- 33 个无设备测试和 Android 16 真机安全验收。

## 验收结果

- 全部必选项和真机安全验收通过。
- `app.open` 只有在动作后前台包名匹配时返回成功。
- Back/Home 没有确定性业务目标，因此如实返回 `inconclusive`。

## 计划偏差

- 完整前后 Observation 使单个真机动作耗时较长，但保留了可靠性和审计证据。
- 本期没有实现确认 UI；Medium tap 仅支持显式 `confirmed=true` 的内部/API 调用，并且没有真机验收。

## 有效做法

- Tool 风险由注册表固定，调用参数无法降低风险。
- Adapter 只执行平台动作，成功验证保持在 Tool/Skill Runtime。
- Fake Adapter 提供可控前台应用状态，验证器无需真实设备即可回归。

## 问题与根因

- Back/Home 无法仅凭通用前台包名证明用户意图完成，需要由更高层 Skill 提供目标验证。
- 当前 Observation 的 UIAutomator 延迟使动作闭环约十余秒，后续需要优化采集策略。

## 长期文档回写

- Tool/Skill 分层、Policy 和 Capability 模型已按工程规范首次落地。
- 真机结果验证与可靠性文档保持一致，没有把 `inconclusive` 升级为 verified。

## 后续行动

- 下一迭代实现语义元素定位与低风险页面导航，为简单自然语言任务做准备。
- 引入任务状态与确认对象后，再开放真机 tap。
- 优化 Observation：动作验证阶段可按目标采用轻量 Observation，完整证据异步补充。
