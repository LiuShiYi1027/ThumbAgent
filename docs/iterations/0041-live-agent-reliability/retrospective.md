# ITER-0041 Retrospective

> 状态：Active
> 更新日期：2026-07-21

## 实际交付

- AgentDecision 以向后兼容字段记录 Provider 总耗时和尝试次数。
- `MODEL_UNAVAILABLE` 记录可观察失败阶段、单次/总耗时和重试信息，不保存响应正文。
- 语义目标部分进入系统安全区时，点击点收敛到 bounds 与安全区域交集的中部。
- MCP Agent Tool 明确一次提交查询至终态，未经新确认不自动创建替代任务。

## 验证结果

- 离线复盘确认失败点击对应 `dashboard_tile` bounds 为 `y=46..214`，旧点击点为 `y=130`。
- `make check` 与 `git diff --check` 通过，默认测试共 271 项通过。
- Android 真机 `adb:A6TG025A13002156` 通过 MCP 使用单个异步任务
  `task_110d5b3c9d9a4f05bc70bb203196b239` 完成“进入蓝牙设置页面”。
- 真机任务共两轮并以 `succeeded` 终止，最终 Activity 为
  `.Settings$BluetoothSettingsActivity`；标题节点“蓝牙”的资源 ID 为
  `android:id/action_bar_title`，完成来源为 `planner_finish`。
- 最终截图 `artifact_c7edd0b1b1bc419fac96ac8720fe1d72` 与 UI Tree
  `artifact_e19983622a9d4d0698a2a864ce79bdf1` 已进入完整任务报告；蓝牙保持关闭，未修改设置。

## 偏差与后续行动

- 非流式标准库 Transport 只能区分响应头、响应体和解码，不能准确报告首 Token。
- 一次成功不能替代多次成功率评测；后续应将系统设置基线扩展为版本化在线评测集。
