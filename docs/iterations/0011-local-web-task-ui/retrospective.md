# ITER-0011 Retrospective

> 状态：Active
> 更新日期：2026-07-09

## 实际交付

- 新增 `runtime/mobile_agent/web/task_ui.py` 单文件本地 Web UI。
- Runtime HTTP Server 增加 `/ui` 和 `/ui/`。
- 页面可展示任务历史、任务概要、步骤、证据摘要、事件和失败原因。
- 页面只调用现有 GET API，不触发设备动作。
- 新增 Web UI 测试。

## 验收结果

- 定向测试 5 tests OK。
- 全量 `make check` 80 tests OK，lint/typecheck OK。
- `git diff --check` OK。

## 计划偏差

- 本迭代未引入桌面壳和前端构建，这符合范围收敛目标。`/ui` 先作为桌面端信息架构原型。

## 有效做法

- 使用单文件 UI，避免在产品形态尚未稳定时引入前端依赖。
- 复用已有任务列表和报告 API，没有新增写动作或设备风险。
- 报告视图继续保持摘要化，不展开完整 UI tree 或截图内容。

## 问题与根因

- GET API 目前依赖 loopback 边界，尚未为浏览器页面引入独立 token。后续若做桌面壳或更复杂 UI，需要重新审视本地访问策略。
- UI 还不能启动任务，只能查看历史和报告。

## 长期文档回写

- README 和 V1 技术方案已记录 `/ui` 入口。
- 未改变 Contract、持久化 Schema 或安全信任模型，不需要 ADR。

## 后续行动

- 下一步建议在 `/ui` 中增加安全 demo 任务启动入口，例如“打开设置并进入显示页”，并继续沿用 POST token/confirmation 约束。
