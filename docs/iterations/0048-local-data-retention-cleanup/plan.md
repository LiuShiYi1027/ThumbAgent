# ITER-0048 Local Data Retention & Cleanup

> 文档状态：Final
> 迭代状态：Completed
> 更新日期：2026-07-27

## 产品结果

用户可以查看 Mobile Agent 本地 Artifact 的数量、分类和空间占用，预览超过保留周期的证据，
并在重新明确确认后清理一组范围固定、完整性可验证的过期 Artifact。

## 范围

- 默认保留周期为 7 天，允许单次预检使用 1–365 天的明确周期。
- 存储摘要和 Cleanup Preview 只读，不读取 Artifact 内容。
- Cleanup 使用十分钟有效、单次、范围绑定的 High 风险 Approval。
- Approval 固定每个候选的 Artifact ID、相对路径、大小和 SHA-256。
- 执行前重新验证候选文件，拒绝路径逃逸、符号链接或确认后变化。
- 清理结果进入异步 Task、REST、MCP、CLI/Web 报告。

## 非目标

- 不自动后台清理，不修改系统计划任务。
- 不接受任意目录、文件路径、glob 或模型生成的删除列表。
- 不删除 SQLite 任务、事件、配置、密钥、APK 或仓库文件。
- 不上传、同步或备份数据。
- 不实现录屏、Crash/ANR、iOS、鸿蒙或多设备并发。

## 风险与兼容性

存储摘要和预检为 Low 风险；清理是不可恢复的本地证据删除，属于 High 风险，复用短期范围绑定
Approval 信任模型。新增 Contract、REST、MCP Tool、Task 类型和可选 Artifact 可用性字段均为
兼容性新增，不改变模块依赖方向，不需要数据库迁移或 ADR。

## 预算

- 5 个 Task，目标 1–2 个工作日。
- 开发阶段只运行 focused tests，候选稳定后运行一次完整 `make check`。
- E2E 使用独立临时数据目录，不需要操作真实手机。
