# ITER-0046 Retrospective

> 文档状态：Final
> 迭代状态：Completed
> 更新日期：2026-07-26

## 实际交付

- 新增应用运行状态、确定性启动、受确认保护的停止和两阶段清除数据。
- REST、MCP、CLI/Web 报告共享统一 Runtime、TaskRun 和风险策略。
- Android Adapter 仅使用固定命令参数，公共结果不包含 PID 或原始平台输出。

## 验证结果

- focused tests 通过。
- `make check` 通过：lint、类型标注检查、324 个测试。
- 真机 `adb:A6TG025A13002156` 广告并通过 `app.state.inspect@1`、`app.stop@1` 和
  `app.data.clear@1` 能力验收。
- 测试应用安装任务 `task_936a5f29056648eda2d0d3dbbc9f0122` 成功并验证版本
  `2.2.0 (25)`。
- 启动任务 `task_953d00939c3c4b1292dcbec3ccc93c8b` 成功，后置状态为
  `foreground=true`、`process_present=true`、`stopped=false`。
- 停止任务 `task_f8dccbfe8421422f810deebff96ffa7a` 成功，后置状态为
  `foreground=false`、`process_present=false`、`stopped=true`。
- 数据清除任务 `task_2391c0e720ff4042b785faf5ea3f8190` 在独立确认后成功；应用保持安装且
  版本不变，`data_cleared=true`，最终运行状态验证通过。

## 效率指标

- 按产品结果合并为一个迭代，6 个 Task 连续完成开发与确定性验证。
- 开发期间使用 focused tests，候选稳定后只运行一次完整 `make check`。
- 真机验证脚本改为 Keychain 复用模型 Key 和稳定 Runtime token，并只安全停止旧 Mobile Agent
  Runtime，消除每轮关闭 Codex、手动清端口和重复输入 Key 的等待。

## 已知限制

- Android 的 process-present 是包级 `pidof` 快照，不等同于业务活跃度。
- package stopped flag 在部分系统输出中可能未知，此时返回 `null`，不做推断。
- 真机清除数据为永久动作，必须独立展示预检摘要并取得新确认。
