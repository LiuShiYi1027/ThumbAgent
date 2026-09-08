# ITER-0064 Acceptance

> 文档状态：Final
> 迭代状态：Completed
> 更新日期：2026-09-08

| 编号 | 验收条件 | 验证方式 | 结果 |
| --- | --- | --- | --- |
| A1 | M4 取消/暂停/deadline 在模型调用期间生效 | 单测：慢速假 Provider + 调用中取消 → <2s；真机：执行中暂停端到端延迟 | 通过：单测 3 条全绿（修复前延迟 ~30s 复现）；真机（OnePlus PLG110）模型调用窗口内暂停 **1.3s** 生效 |
| A2 | unicode 读回节点缺席可恢复 | 单测：首次读回 match_count=0、重读后命中 → succeeded；tamper 仍立即失败不重读 | 通过：3 条新测试修复前失败修复后绿；tamper 不回归；真机夸克中文输入 succeeded（2 轮 90s，ColorOS 首次覆盖） |
| A3 | queued 可暂停 | 单测全链路 + 重启恢复 queued-paused → TASK_INTERRUPTED | 通过：4 条测试（queued→paused→resume→执行；未暂停 queued 的 resume 仍冲突；queued-paused 取消立即收尾；重启恢复） |
| A4 | 捷径副作用有证据 | 单测：捷径验收失败的报告含 shortcut_step；任务回退模型循环 | 通过：2 条测试（回退后成功、终败仍保留 shortcut_step） |
| A5 | Web UI 幂等键稳定 | 单测：JS 派生与服务端 stable_idempotency_key 跨语言一致 | 通过：node 跨语言 5 组向量逐一相等（含中文/嵌套/乱序键）；5 个提交点全部接入 |
| A6 | 集中全量验证 | 一次 `make check` 全绿 | 通过：665→685 tests OK |
