# ITER-0012: Web Demo Task Launcher

> 状态：Completed
> 更新日期：2026-07-09
> Owner：Codex

## 目标

在本地 Web UI 中加入第一个受控任务启动按钮，让用户可以从页面发起安全 demo 任务，并立即查看任务报告。

本迭代要证明：

> Mobile Agent 的 Web 产品雏形不只会看历史，也能以受控方式启动一个确定性 Skill 任务。

## 背景

ITER-0011 完成了只读任务历史和报告详情页。用户已经能看见产品，但还不能从页面触发任务。为了形成最小闭环，本迭代增加一个固定 demo：打开系统设置并进入显示/亮度页面。

该按钮复用已有 `settings.scroll_navigate` 任务 API，不新增底层设备动作。

## 范围

- Web UI 增加在线设备选择。
- Web UI 增加“运行安全 Demo”按钮。
- 按钮调用 `POST /v1/tasks/settings.scroll_navigate/run`。
- 页面注入本地 Runtime token，并在 POST 请求中使用 `Authorization: Bearer ...`。
- POST Origin 允许同源 loopback 页面。
- 任务完成后刷新历史列表并打开新任务报告。
- 补齐 Web UI 和 API 安全测试。

## 非目标

- 通用任务创建器。
- 任意 Selector 输入。
- 自然语言任务规划。
- 多 demo 任务。
- 桌面壳。

## 安全边界

- demo 任务固定为系统设置内的只读导航。
- 不点击开关、删除、提交、支付或账号安全控件。
- POST 仍要求本地 Runtime token。
- 浏览器页面仅允许同源 loopback POST，不开放任意 Web Origin。
- Medium 风险动作仍通过 `confirmed=true` 明确表达用户点击按钮确认。

## 依赖

- ITER-0011 本地 Web UI。
- `POST /v1/tasks/settings.scroll_navigate/run`。
- Android 真机已验证过的 `settings.scroll_navigate` 能力。

## 风险

- 当前 demo selector 使用中文系统设置项“亮度”，可兼容“显示与亮度”和“显示和亮度”；非中文系统可能无法命中。
- 不同厂商设置页滚动惯性差异较大，demo 使用小步滚动参数降低一次滑到底部的概率。
- 真实设备仍需要用户启用 USB 调试和 USB 调试安全设置。

## 里程碑

1. UI 增加设备选择和 demo 按钮。
2. 页面使用 token 发起 POST。
3. API 安全逻辑允许同源 loopback Origin。
4. 补齐测试和文档。
5. 全量质量门禁通过。

## 完成条件

以 [acceptance.md](./acceptance.md) 的必选验收全部通过为准。
