# ITER-0060 Acceptance

> 文档状态：Final
> 迭代状态：Completed
> 更新日期：2026-08-30

| 编号 | 验收条件 | 验证方式 | 结果 |
| --- | --- | --- | --- |
| A1 | 集中全量验证通过 | `make check`：497 tests OK，类型/格式检查、TS Contract 同步检查（`generate_ts_contracts.py --check`）全部通过 | PASS |
| A2 | 真机模型驱动中文任务闭环 | 夸克场景「打开夸克浏览器，在搜索框里输入你好」：模型全程在线规划，3 轮完成（app.launch → tap 搜索框 → input.unicode_text），`completion_source=runtime_acceptance`，产物 `e2e-output/20260830-221126/` | PASS |
| A3 | 验收唯一命中目标节点 | verified_node 为 text="你好" 的 `android.widget.EditText`；页面上 8 个含「你好」的热搜推荐词（clickable=false TextView）全部被排除，无 TARGET_AMBIGUOUS | PASS |
| A4 | IME 状态卫生 | 技能执行后恢复原 IME（`restored: true`）；测试收尾后设备默认输入法恢复为搜狗，helper 包无残留 | PASS |
| A5 | hint 策略契约与类型同步 | hint 策略 Contract 测试 + Locator 单测 + 摘要暴露断言随 27a0a69 入库；TS 类型再生成一致 | PASS |
| A6 | 真机场景不进默认测试集 | E2E 脚本显式触发（`scripts/e2e/`，`--device` 指定真机），普通单元/集成测试无真实设备、网络、模型依赖 | PASS |
