# ITER-0048 Retrospective

> 文档状态：Final
> 迭代状态：Completed
> 更新日期：2026-07-27

## 实际交付

- 新增默认 7 天保留周期的本地 Artifact 聚合盘点和只读 Cleanup Preview。
- 新增十分钟有效、单次、范围与幂等键绑定的 High 风险 Approval；执行前复核相对路径、
  大小、SHA-256、修改时间和链接属性。
- 清理作为 `local.data.cleanup` 异步任务执行，支持取消、Deadline、幂等和部分失败证据，
  不获取设备 Session 或 Lease。
- REST、MCP、CLI 与 Web 完成预览、确认、提交和报告闭环；历史任务报告继续保留 Artifact
  元数据，并展示 available、expired 或 missing。

## 验证结果

- 99 项本地数据、MCP、REST、CLI/Web、持久化和 Task focused tests 通过。
- 独立临时目录的 MCP → REST → Runtime → async Task 集成用例完成
  prepare → confirm → cleanup → report，并验证只删除批准的过期 Artifact。
- 2026-07-27 完整 `make check` 通过：lint、类型标注检查和 350 项测试。
- `git diff --check` 通过；测试覆盖确认缺失、候选变化、部分失败、数量截断、取消边界、
  硬链接、异常超大文件和历史报告可用性。

## 效率指标

- 在一个迭代内完成 3 个 Contract、Domain/Tool/Skill、异步执行、四类 Interface 和文档收口。
- 开发阶段用 focused tests 快速反馈，候选稳定后执行完整门禁；完整门禁发现并修复了 Runtime
  本地能力与 Device Capability 断言边界不一致的问题。

## 已知限制

- V1 不自动定时清理；用户必须主动预检并重新明确确认。
- 单次最多批准 2,000 个 Artifact；超过范围通过 `truncated` 提示并需再次分批预检。
- 大于 64 MiB 的单个异常 Artifact 不进入清理候选，避免对伪造文件执行无界哈希；存储摘要仍会
  统计其空间，需未来受控维护能力处理。
- 清理只删除 Artifact 文件，不删除历史 Task/Event；若进程在删除文件后、保存清理报告前崩溃，
  历史报告会诚实标注为 missing，而不是推断为 expired。
