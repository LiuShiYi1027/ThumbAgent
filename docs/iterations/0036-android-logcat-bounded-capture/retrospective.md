# ITER-0036 Retrospective

> 状态：Completed
> 更新日期：2026-07-15

## 实际交付

- 第一个工程诊断类 deterministic Skill：`device.logs.collect@1`。
- 日志能力复用 Capability Catalog、Policy、设备 Session、Lease 和 Artifact Store，没有建立旁路。
- Android logcat 参数由 Adapter 固定构造，结果先脱敏再落本地 `.log` Artifact。
- Web 提供显式确认按钮，CLI 要求 `--confirm` 和本地 API token；两者只展示元数据。

## 验证结果

- `make check` 通过：lint、类型检查和 214 个测试。
- 单元与集成测试覆盖固定 ADB 参数、输入边界、Capability、Policy、失败、取消、离线、脱敏和截断。
- 真机 `adb:A6TG025A13002156` 完成 100 行 Warn+ 快照 smoke：采集成功，生成 11,006 bytes
  `device_log/text/plain` Artifact，未截断；验收输出没有打印日志正文。

## 偏差与后续

- 本迭代选择同步快照，没有把日志强行套入 `agent.run` 的 TaskRun 或 UI ActionResult。
- 通用 Tool 注册表新增 `direct_invocation`，明确部分底层 Tool 只能被目标级 Skill 使用。
- 脱敏是防御性降低风险，不是完整 DLP；原始业务日志仍可能包含未知敏感格式。
- 后续应设计异步诊断 Task，再支持持续采集、复现时间窗、取消事件和诊断包组合。
