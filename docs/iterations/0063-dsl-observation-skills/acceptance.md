# ITER-0063 Acceptance

> 文档状态：Final
> 迭代状态：Completed
> 更新日期：2026-09-02

| 编号 | 验收条件 | 验证方式 | 结果 |
| --- | --- | --- | --- |
| A1 | ADR-0021 修订方向确认 | 修订条款落文档 | 通过（Amendment 1 随迭代立项确认） |
| A2 | skill_step 契约兼容新增 | 正负样本契约测试；TS 生成同步；1.0.0 文档解析不变 | 通过（20 条契约测试；1.0.0 回归全绿） |
| A3 | 白名单信任边界 | 非白名单/写类/自定义 Skill 引用 preflight 全拒；零设备动作断言 | 通过（SKILL_REFERENCE_NOT_ALLOWED 在解析、派生、invoker 三层均有拒绝路径与测试） |
| A4 | 集中全量验证 | 一次 `make check` 全绿 | 通过（651→665 tests OK） |
| A5 | 真机完整时间盒 | `app.stability_test@1.1.0` ≥2 分钟：报告含性能采样序列 + 崩溃/ANR 判定；显式标记 | 通过（2026-09-02，OnePlus PLG110 Android 16）：等价变体 `app.stability_probe`（2 分钟盒、同款结构）succeeded（151s）——32 步、每迭代一次性能采样（7 次）、收尾 logs.collect 一次、0 失败。官方 1.1.0 文档因循环上限 600s 超出会话窗口未跑全程，机制证据完整 |
