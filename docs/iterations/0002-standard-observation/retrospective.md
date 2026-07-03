# ITER-0002 Retrospective

> 状态：Active  
> 更新日期：2026-07-03

## 实际交付

- Observation 与 Artifact JSON Schema 和领域模型。
- 本地 Artifact Store：原子写入、SHA-256、相对路径和逃逸保护。
- Fake Adapter 与 Android Adapter 的标准 Observation。
- Android 截图、前台窗口、屏幕尺寸/方向和 UI hierarchy 采集。
- `screen.observe@1` Capability 与 Runtime HTTP observe endpoint。
- 23 个无设备测试和 Android 16 真机验收。

## 验收结果

- 所有必选项和真机验收通过。
- API 仅返回 Artifact 引用和元数据，没有内嵌敏感二进制或 XML。

## 计划偏差

- 原计划直接使用 `dumpsys window windows` 获取前台应用，但目标 Android 16 厂商系统只在完整 `dumpsys window` 输出中提供 `mFocusedApp`，已调整命令和解析测试。
- Device state 没有足够可靠证据，因此 Android Adapter 返回 `unknown`，没有为了“字段好看”而假设 interactive。

## 有效做法

- PNG IHDR 直接提供实际截图尺寸，减少一次设备命令和厂商格式依赖。
- ArtifactWriter 作为领域端口，使 Adapter 与具体存储策略解耦。
- 真机输出只展示元数据，避免在日志和文档泄露 UI 内容。

## 问题与根因

- Android `dumpsys` 的窗口焦点格式存在厂商和版本差异，需要多格式解析与真机 fixture。
- UIAutomator dump 大约需要数秒，是当前 Observation 的主要耗时来源。
- 截图、前台应用和 UI hierarchy 是顺序采集，不是原子快照。

## 长期文档回写

- `screen.observe@1` 已按照 Capability 模型加入在线 Android 设备。
- Observation 明确记录各部分独立时间戳，与技术方案一致。

## 后续行动

- 下一迭代实现基础只读/低风险 Tools 和 `app.launch`，形成第一个动作前后 Observation 闭环。
- 增加可靠的 device lock/interactive 状态检测。
- 后续评估设备端 helper，以降低 UI hierarchy 延迟和改善采集一致性。
