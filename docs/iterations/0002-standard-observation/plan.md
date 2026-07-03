# ITER-0002: Standard Observation

> 状态：Completed  
> 更新日期：2026-07-03  
> Owner：Codex

## 目标

为已授权 Android 设备生成不可变、可追踪的标准 Observation，采集截图、前台应用、屏幕尺寸和 UI hierarchy，并把原始证据安全保存到本地 Artifact Store。

## 范围

- Observation 与 Artifact JSON Schema
- 平台无关 Observation 领域模型
- 本地 Artifact Store 与 SHA-256 完整性信息
- Android 截图、屏幕尺寸、前台应用和 UI hierarchy 采集
- `screen.observe@1` Capability
- Fake Adapter 标准 Observation
- Runtime `POST /v1/devices/{device_id}/observe`
- 无设备自动化测试与真机只读验收

## 非目标

- 点击、输入、滑动和系统按键
- OCR、视觉 grounding 或页面语义总结
- 视频流和录屏
- SQLite 持久化
- Agent Loop、Skill 或 MCP
- iOS、鸿蒙 Observation
- 将截图或 UI 内容发送到云端模型

## 隐私边界

- 截图和 UI hierarchy 可能包含敏感信息，只保存到本地忽略目录。
- API 返回 Artifact 引用和必要元数据，不内嵌截图或完整 XML。
- 测试 fixture 只使用人工生成的非真实用户内容。
- 日志不记录 UI 文本、截图数据和设备序列号。

## 风险

- 不同 Android 版本的前台应用输出格式不同。
- UIAutomator 在动画、自绘页面或锁屏状态可能失败或返回空树。
- 截图与 UI hierarchy 不是同一时刻的原子快照，必须分别记录采集时间。
- 真机 UI hierarchy 可能含隐私数据，验收后按保留策略处理。

## 里程碑

1. Contracts 与领域模型通过测试。
2. Artifact Store 原子写入和哈希验证通过。
3. Fake Adapter 完成端到端 Observation。
4. Android Adapter 完成四类只读采集。
5. Runtime API 与真机验收通过。

## 完成条件

以 [acceptance.md](./acceptance.md) 必选项通过、任务完成并提交复盘为准。
