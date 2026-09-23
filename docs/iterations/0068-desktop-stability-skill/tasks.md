# ITER-0068 Tasks

> 文档状态：Draft
> 迭代状态：Active
> 更新日期：2026-09-22

| Task | 状态 | Owner | 交付 |
| --- | --- | --- | --- |
| TASK-0068-01 | done | Cursor | sidecar 白名单放行 `POST /v1/tasks/skill.dsl.run/async`；`/v1/skills/.../invoke` 与同步 `skill.dsl.run` 仍拒绝。白名单单测已通过 |
| TASK-0068-02 | done | Cursor | 新任务增加「稳定性测试」：包名校验、确认文案、固定提交 `app.stability_test@1.1.0`，沿用既有执行与报告 |
| TASK-0068-03 | in-progress | Cursor | desktop `tsc`、oxlint 与 sidecar 白名单单测已通过。真机桌面点击未做 |
