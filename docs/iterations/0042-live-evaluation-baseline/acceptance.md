# ITER-0042 Acceptance

> 状态：Active
> 更新日期：2026-07-21

- [x] Suite 严格校验版本、ID、场景唯一性和每场景运行次数。
- [x] 聚合器拒绝缺失、重复或未知场景结果，不访问设备、模型或 Task Store。
- [x] Summary 展示总成功率和逐场景成功率。
- [x] Summary 展示耗时 p50/p95、平均轮次/Tool、Provider 重试、无进展和策略违规。
- [x] CLI 只通过现有评测 API 消费已完成任务，不提交或重放设备动作。
- [x] Android 设置 smoke Suite 不包含固定动作路径。
- [x] 默认测试不依赖设备、网络或模型，`make check` 与 `git diff --check` 通过。
- [x] 使用三个真实任务生成并分析首份 Android 设置 smoke Summary；识别并修复最终 Observation 评测缺陷，修复后未重复消费付费模型或操作设备。
