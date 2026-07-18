# ITER-0039 Acceptance

> 状态：Completed
> 更新日期：2026-07-15

- [x] 输入和输出使用严格、版本化的公共 Contract。
- [x] 只能比较两个成功的性能快照任务，且必须来自同一设备并按时间排序。
- [x] 比较过程不访问设备、模型、原始 Artifact 或平台诊断内容。
- [x] 每项指标保留 baseline、candidate、delta、unit、threshold 和 trend。
- [x] 缺失温度使用 unavailable，不伪造数值或整次比较失败。
- [x] 设备 Session 相同、不同或缺失可被客户端区分。
- [x] Web 支持选择基线和候选快照，CLI 消费同一接口。
- [x] 结果明确说明两点样本不能证明因果或性能回退。
- [x] 全量质量检查和本地真实 TaskRun smoke 通过。
- [ ] 连续采样、评分、告警和业务任务 Workflow 不属于本迭代。
