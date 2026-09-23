# ITER-0068 Tasks

> 文档状态：Active
> 迭代状态：Completed
> 更新日期：2026-09-23

| Task | 状态 | Owner | 交付 |
| --- | --- | --- | --- |
| TASK-0068-01 | done | Cursor | sidecar 白名单放行 `POST /v1/tasks/skill.dsl.run/async`；`/v1/skills/.../invoke` 与同步 `skill.dsl.run` 仍拒绝。白名单单测已通过 |
| TASK-0068-02 | done | Cursor | 新任务增加「稳定性测试」：包名校验、确认文案、固定提交 `app.stability_test@1.1.0`，沿用既有执行与报告 |
| TASK-0068-03 | done | Kimi | 2026-09-23 真机（荣耀 DNN-AN00）桌面点击收口：AX 脚本驱动真实窗口完成选择设备 → 填包名 → 确认 → 提交，任务 `task_58264803e0b7415bab7e9533853dc09f` 执行 28 步，报告打开且采样曲线渲染；A3 非法包名禁用同时验证。desktop `tsc`、oxlint 与 sidecar 白名单单测通过 |
