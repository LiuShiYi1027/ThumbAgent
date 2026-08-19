# ITER-0052 Retrospective

> 文档状态：Completed
> 迭代状态：Completed
> 更新日期：2026-08-19

## 实际交付

1. Runtime 新增有界只读截图内容端点 `GET /v1/artifacts/{artifact_id}/content`：
   Bearer token 认证（401）、id 模式校验、仅已落盘的截图 PNG、`resolve()` 防越界、
   1 B–8 MiB 大小界、PNG 签名重校验；响应带 `Cache-Control: no-store` 与
   `X-Content-Type-Options: nosniff`；新增错误码 `ARTIFACT_NOT_FOUND`。
2. 异步 Agent 任务的 `task.step_completed` 事件在动作轮携带 `screenshot_artifact_id`，
   兼容 `SkillResult.action` 与 `NavigationResult.tap_action` 两种结果形态。
3. 桌面 Rust 新增 `runtime_api_get_bytes` 命令：路径白名单仅允许 Artifact 内容模式、
   响应上限 12 MiB、200 判定先于 JSON 解析、内置 RFC4648 base64（零新增依赖）。
4. 前端新增 `DeviceScreenPanel`（执行中轮询事件流展示最新轮次截图，结束后展示最后一轮）
   与报告页每轮"查看截图"开关；执行/报告区切换为双栏 `workbench-grid` 布局。
5. 文档同步：README 当前进展、`technical-design-v1.md` 追加 ITER-0051/0052 段落。

## 验证指标

- Active → Verifying 耗时：约 1 天（2026-08-18 建档，2026-08-19 完成实现与门禁）
- Verifying → Completed 耗时：约 1 天（设备掉线等待重连占用主要时间；重连后实测约 30 分钟）
- 计划 Task 数 / 新增 / 取消：5 / 0 / 0
- 完整 `make check` / `make check-desktop` 执行次数：各 2 次（实现后 + 收尾前）
- 真机 E2E 往返次数：1（`settings.display-brightness.v1` 单次提交到终态）
- 真机场景成功数与失败原因：1 成功 / 0 失败；执行中 1 个动作轮
  `TARGET_OUT_OF_BOUNDS` 失败，Agent 下一轮自行恢复，任务终态 `succeeded`

## 偏差与限制

- 真机验证因设备掉线顺延约一天；期间用 8 月 17 日真机产出的真实截图 Artifact
  对运行中 Runtime 做了端点实测（401/200/404 全链路），重连后仅补跑任务闭环。
- 桌面窗口内的最终渲染观感未机器核验（无 GUI 自动化与前端单测框架）；UI 依赖的
  数据链路（事件字段、存储步骤结构、端点字节、IPC 二进制桥）已在真机任务上逐层核对，
  渲染问题若有属纯样式修复，不涉及契约。
- 截图为每轮动作后的静态画面（事件 1.2 s 轮询），不是实时视频流；截图仅在桌面端
  内存渲染，不向本地另存副本。
- 人工接管（暂停 Agent、用户操作设备后继续）按 plan 约定不属于本迭代范围。

## 后续行动

- 候选迭代方向：人工接管（暂停/继续/接管标记）；桌面端设置页（模型 Provider、token、
  数据目录管理）；执行中点击截图放大查看。
- 用户下次打开桌面端执行任务时人工过目设备画面栏渲染观感，如有样式问题开修复任务。
