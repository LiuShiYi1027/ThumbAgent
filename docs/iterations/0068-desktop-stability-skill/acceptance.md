# ITER-0068 Acceptance

> 文档状态：Active
> 迭代状态：Completed
> 更新日期：2026-09-23

| 编号 | 验收条件 | 验证方式 | 结果 |
| --- | --- | --- | --- |
| A1 | 桌面只能多提交这一条技能任务 | Rust：`skill.dsl.run/async` 通过；`/v1/skills/app.open/invoke` 仍拒绝 | 通过。`post_path_whitelist_accepts_only_submit_and_task_controls` |
| A2 | 工作台可发起官方稳定性测试 | 选择设备、填写合法包名、确认后 POST 固定 `app.stability_test@1.1.0` | 通过。2026-09-23 macOS AX 脚本驱动真实桌面窗口：选中荣耀 DNN-AN00（`adb:A6RVVB5A23006075`）、填入 `com.quark.browser`、确认框展示遍历说明后「确认执行」。Runtime 落库 `task_58264803e0b7415bab7e9533853dc09f`，`task_type=skill.dsl.run`，goal 为 `app.stability_test@1.1.0`，执行 28 步 |
| A3 | 非法包名不发请求 | 客户端按应用 id 形态校验，提交按钮保持禁用 | 通过。同次会话输入非法值（IME 导致的变形文本）后渲染「包名需要像 com.example.app 这样的形式」，「提交任务」`enabled=false`，无请求发出 |
| A4 | 自然语言任务不受影响 | 既有 Agent 提交路径仍在 | 通过。「自然语言」标签与目标输入区仍在（截图证据），类型检查通过 |
| A5 | 类型检查 | desktop `tsc -b`，并跑 oxlint | 通过（2026-09-23 `npm run build` 复跑通过） |
| A6 | 真机桌面 | 从工作台点一次短时稳定性测试，报告能打开 | 通过。任务于 14:39:03–14:42:06 真机执行（夸克首启隐私弹窗场景），报告页呈现 `性能采样序列（6 次）` 曲线（CPU 16.0% / 内存 43.9% / 电量 56%）、`已超时` 徽标与逐轮 `skill.dsl.run` 成功记录。终态 `timed_out`（`TASK_DEADLINE_EXCEEDED`）与 plan 风险节记录一致：120 秒时间盒 + 收尾超出 180 秒 deadline，采样保留 |

> 验证方式说明：桌面点击由 macOS 辅助功能（AX）脚本驱动真实 ThumbAgent 窗口完成，
> 非 mock；全程见 2026-09-23 会话记录与 `task_58264803e0b7415bab7e9533853dc09f` 事件流。
