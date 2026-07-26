# ITER-0047 Acceptance

> 文档状态：Final
> 迭代状态：Completed
> 更新日期：2026-07-26

- [x] 未明确确认时不读取截图、UI Tree 或日志。
- [x] 单任务采集 Observation、脱敏日志、聚合性能及可选应用运行状态。
- [x] ZIP 只包含固定文件名，Manifest 记录来源 Artifact、大小和 SHA-256。
- [x] 公共响应不内联截图、UI Tree、日志、ZIP 内容、PID 或原始 dumpsys。
- [x] 包内容和总大小有界，路径不可逃逸，失败时保留已完成证据引用。
- [x] 异步任务支持幂等、取消、Deadline、Session 与 Lease。
- [x] REST、MCP、CLI/Web 报告展示安全摘要和诊断包 Artifact。
- [x] focused tests 和最终 `make check` 通过。
- [x] 真机完成一次诊断包采集并核验 ZIP Manifest。
