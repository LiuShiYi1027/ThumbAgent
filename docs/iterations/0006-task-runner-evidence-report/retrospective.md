# ITER-0006 Retrospective

> 状态：Active
> 更新日期：2026-07-08

## 实际交付

- 新增 `TaskRun` / `TaskStep` 领域对象。
- 新增 `contracts/schemas/task-run.schema.json`。
- 新增 `TaskRunner.run_settings_scroll_navigation`，将 `settings.scroll_navigate` 包装为一条可审计任务报告。
- RuntimeService 暴露同步任务运行方法。
- 本地 HTTP API 增加预览型同步端点 `POST /v1/tasks/settings.scroll_navigate/run`。
- README、技术方案和迭代索引已更新。

## 验收结果

- `runtime.tests.test_task_runner` 4 tests OK。
- `make check` 66 tests OK，lint/typecheck OK。
- `git diff --check` OK。

## 计划偏差

- 本迭代没有实现正式异步 `/v1/tasks` 队列。这个偏差是刻意收敛：先验证 TaskRun 报告形态，再进入持久化、事件和恢复语义。

## 有效做法

- 以已有确定性 Skill 作为第一条任务类型，避免同时引入模型规划和任务系统两类不确定性。
- 失败也返回结构化 TaskRun，使调用方可以展示“为什么没有执行”，而不是只看到异常。
- 保留 `CONFIRMATION_REQUIRED` 原始错误码，避免任务层吞掉安全策略。

## 问题与根因

- 当前 TaskRun 只保存在返回值中，没有持久化；Runtime 重启后无法查询历史任务。
- 预览端点是同步执行，不具备正式任务 API 的 pause/resume/cancel、事件流和幂等恢复能力。

## 长期文档回写

- 已在 V1 技术方案中标注预览型同步任务端点，明确它不替代未来正式异步任务队列。
- 本迭代未改变持久化、事件流或确认模型，不需要 ADR。

## 后续行动

- 下一步建议进入 Task Store / Event Log 迭代：让任务从“同步报告”变成“可查询、可恢复、可向桌面端展示进度”的产品能力。
