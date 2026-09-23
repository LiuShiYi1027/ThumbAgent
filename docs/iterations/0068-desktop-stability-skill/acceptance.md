# ITER-0068 Acceptance

> 文档状态：Draft
> 迭代状态：Active
> 更新日期：2026-09-22

| 编号 | 验收条件 | 验证方式 | 结果 |
| --- | --- | --- | --- |
| A1 | 桌面只能多提交这一条技能任务 | Rust：`skill.dsl.run/async` 通过；`/v1/skills/app.open/invoke` 仍拒绝 | 通过。`post_path_whitelist_accepts_only_submit_and_task_controls` |
| A2 | 工作台可发起官方稳定性测试 | 选择设备、填写合法包名、确认后 POST 固定 `app.stability_test@1.1.0` | 代码已接。未做桌面点击 |
| A3 | 非法包名不发请求 | 客户端按应用 id 形态校验，提交按钮保持禁用 | 代码已接。无组件测试 |
| A4 | 自然语言任务不受影响 | 既有 Agent 提交路径仍在 | 类型检查通过，自然语言提交函数仍在 |
| A5 | 类型检查 | desktop `tsc -b`，并跑 oxlint | 通过 |
| A6 | 真机桌面 | 从工作台点一次短时稳定性测试，报告能打开 | 未跑 |
