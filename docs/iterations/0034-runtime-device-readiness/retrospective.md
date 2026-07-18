# ITER-0034 Retrospective

> 状态：Completed
> 更新日期：2026-07-15

## 实际交付

- 新增 RuntimeReadiness 公共 Contract，将 Gateway、Device、Session、Lease 和建议聚合为只读快照。
- ADB 缺失时使用 UnavailableDeviceAdapter 启动诊断模式，Web/CLI 保持可用，设备动作继续明确拒绝。
- Web 增加 Runtime/设备就绪卡片，只把 ready 设备放入任务选择器。
- 新增 `mobile_agent.cli.runtime_diagnose`，无需理解底层 ADB 输出即可定位启动问题。

## 验证结果

- `make check` 通过：lint、类型检查和 189 个测试。
- 覆盖 ready、busy、unauthorized、无设备、Gateway unavailable 与缺失 ADB 启动路径。
- 错误 ADB 路径的隔离 Runtime 在 8880 正常启动，Readiness 返回
  `blocked / ADB_NOT_FOUND` 与重启建议，没有 traceback。
- 真机隔离 Runtime 在 8881 返回 `ready`、online Session、8 项能力且无 Lease 占用；验收只执行
  `adb devices/getprop` 级设备发现，不执行 Observation、模型调用或设备动作。
- 两个隔离 Runtime 均已正常关闭，临时 runtime-token 已清理。

## 偏差与后续

- 本迭代不显示 ADB 可执行文件的完整本机路径，避免将路径变成公共 Contract 或泄漏本机信息；
  只公开 transport、状态和修复建议。
- 安装或修复 ADB 后需要重启 Runtime，Unavailable Adapter 不在进程内热替换。
- 下一步可进入 Device Inspection：将设备基础信息、当前能力和受控只读检查形成独立详情视图，
  为后续日志、性能和包管理能力提供入口。
