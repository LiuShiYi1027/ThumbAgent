# ITER-0067 Acceptance

> 文档状态：Active
> 迭代状态：Completed
> 更新日期：2026-09-22

| 编号 | 验收条件 | 验证方式 | 结果 |
| --- | --- | --- | --- |
| A1 | 无 `submit` 时 Unicode 输入行为与 0059 一致 | 既有 `test_unicode_input` 成功路径仍通过，不发 Enter | 通过 |
| A2 | `submit=search` 在读回成功后、IME 恢复前发送一次 Enter | Fake：actions 含 `input.enter`，且位于最后一次 `input.ime.set` 之前 | 通过 |
| A3 | 非法 `submit` 在任何设备动作前拒绝 | Fake：`submit=go` / 非字符串 → `INVALID_ARGUMENT` 或 `MODEL_OUTPUT_INVALID`，actions 为空 | 通过 |
| A4 | Agent 可在结果页 finish 并持久化 answer | Fake：输入+提交后 ui 出现价格节点，任务 succeeded，`result.answer` 非空 | 通过 |
| A5 | 契约兼容 | 结果 Schema 可选 `submitted`；缺省样本仍合法；MCP 入参可选 `submit` | 通过 |
| A6 | 集中全量验证 | 一次 `make check` 全绿 | 通过（lint / typecheck / 729 tests / contracts --check） |
| A7 | 真机 | 夸克搜索并带回答案：`succeeded` + `planner_finish` + 非空 answer。京东不作为本迭代必过项 | **deferred**。`submit=search` 已在 OnePlus PLG110 真机第 5 轮成功；随后模型继续点击/滑动，15 分钟预算耗尽 `timed_out`，无 answer。不以本次运行宣称价格交卷通过 |
