# ITER-0004: Semantic Navigation

> 状态：Completed
> 更新日期：2026-07-07
> Owner：Codex

## 目标

将设备交互从裸坐标提升为基于 UI hierarchy 的语义元素定位，支持唯一匹配、bounds 安全点击、等待元素和目标页面验证，并在 Android 真机上完成一次不修改设置的安全导航。

## 范围

- UI Node、Selector 和 Match Result Contracts
- UIAutomator XML 标准化解析
- `resource_id`、text、content description、clickable 和层级路径定位
- exact/contains 匹配与唯一性判断
- `TARGET_NOT_FOUND`、`TARGET_AMBIGUOUS` 和不可点击错误
- bounds 解析、屏幕边界校验与中心点计算
- `input.tap_element` Medium 风险 Tool
- 有上限的元素等待与页面稳定检查
- 安全设置页面导航 Skill
- Runtime API、Fake Adapter、自动化测试和真机验收

## 非目标

- OCR、截图视觉定位和模型 grounding
- 文本输入、滑动与长按
- 修改系统开关或提交表单
- 通用自然语言 Agent Loop
- 跨多个 App 的复杂 Workflow

## 真机安全边界

- 只从系统设置主页进入一个无副作用子页面。
- 不点击开关、复选框、删除、确认或提交控件。
- 真机 `tap_element` 必须显式确认。
- 匹配不存在或不唯一时停止，不降级为猜测坐标。
- 导航完成后使用页面标题或结构化 UI 证据验证。

## 完成条件

以 [acceptance.md](./acceptance.md) 全部必选项和真机安全验收通过为准。
