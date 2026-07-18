# ITER-0037 Acceptance

> 状态：Completed
> 更新日期：2026-07-15

- [x] AsyncTaskExecutor 只接受代码内显式登记的任务类型。
- [x] `device.logs.collect` 返回 202、task_id 和 queued 状态。
- [x] 日志任务产生 queued、started、step_completed、completed 增量事件。
- [x] 任务绑定 Device Session 和 Lease，并将终态 TaskRun 持久化到统一 TaskStore。
- [x] Idempotency-Key 同请求复用、不同请求冲突。
- [x] 未确认日志采集在排队前以 CONFIRMATION_REQUIRED 拒绝。
- [x] 运行中取消在当前 ADB 安全边界后生效，已生成 Artifact 证据不丢失。
- [x] Web 默认使用异步入口，CLI 可选择同步或异步提交。
- [x] Task 报告只展示 Artifact 引用和安全摘要，不展示日志正文。
- [x] Runtime 重启恢复继续适用于新增任务类型且不自动重放。
- [ ] 持续流式采集和 ADB 调用中即时强制取消不属于本迭代。
