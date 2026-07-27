# ITER-0048 Acceptance

> 文档状态：Final
> 迭代状态：Completed
> 更新日期：2026-07-27

- [x] 存储摘要仅扫描 Artifact 根目录并返回有界聚合元数据。
- [x] Preview 零删除副作用，明确展示周期、截止时间、数量、大小、是否截断和 Approval 过期时间。
- [x] 未经新的明确确认或范围绑定 Approval 时不能删除文件。
- [x] Approval 绑定 Artifact ID、相对路径、大小和 SHA-256，确认后变化必须拒绝。
- [x] 任意路径、符号链接、硬链接、未知文件、临时文件和非 Artifact 数据不得进入候选。
- [x] 单次删除数量有界，部分失败保留已完成删除摘要且不自动重试。
- [x] 异步任务支持幂等、取消、Deadline 和完整报告，不获取设备 Session 或 Lease。
- [x] 历史任务保留证据元数据，并把 Artifact 标注为 available、expired 或 missing。
- [x] REST、MCP、CLI/Web 展示影响摘要和安全结果，不返回文件内容。
- [x] focused tests 与最终 `make check` 通过。
- [x] 独立临时数据目录完成 prepare → confirm → cleanup → report E2E。
