# ITER-0064 Acceptance

> 文档状态：Draft
> 迭代状态：Planned
> 更新日期：2026-09-02

| 编号 | 验收条件 | 验证方式 | 结果 |
| --- | --- | --- | --- |
| A1 | M4 取消/暂停/deadline 在模型调用期间生效 | 单测：慢速假 Provider（sleep 30s）+ 调用中取消 → <2s 到 cancelled；真机：任务执行中暂停的端到端延迟对比修复前 | 待验证 |
| A2 | unicode 读回节点缺席可恢复 | 单测：首次读回 match_count=0、重读后命中 → succeeded；tamper 仍立即失败不重读 | 待验证 |
| A3 | queued 可暂停 | 单测全链路 + 重启恢复 queued-paused → TASK_INTERRUPTED；真机验证排队任务暂停/恢复 | 待验证 |
| A4 | 捷径副作用有证据 | 单测：捷径验收失败的报告含 shortcut_step；任务回退模型循环 | 待验证 |
| A5 | Web UI 幂等键稳定 | 单测：Web UI JS 派生键与服务端规范化哈希一致；同参重试命中去重 | 待验证 |
| A6 | 集中全量验证 | 一次 `make check` 全绿，无回归 | 待验证 |
