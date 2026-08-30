# ITER-0060 Tasks

> 文档状态：Final
> 迭代状态：Completed
> 更新日期：2026-08-30

| Task | 状态 | Owner | 交付 |
| --- | --- | --- | --- |
| TASK-0060-01 | done | Kimi | unicode IME 真机加固：手搓 Modified UTF-7 解码器（对齐参考实现）+ hint 感知读回验证（d9b2b47）；注入丢失竞态修复——settle + 整体丢失判别有界重试（eed04a8） |
| TASK-0060-02 | done | Kimi | 本地推理服务兼容：Provider `response_format` 可配置（本地降级 text）+ 解析器退化 bounds 容忍（429e522） |
| TASK-0060-03 | done | Kimi | E2E Suite 入库：dogfood 脚本收编为显式 device_e2e suite（3e74ac9）；真机模型驱动场景脚本 + iter0059 路径回归修复（033f77c）；夸克 unicode 输入模型循环预设 + `--device` 选择器（11b6231） |
| TASK-0060-04 | done | Kimi | hint 选择器策略：Contract Schema + Locator + Observation 摘要暴露 + Planner prompt，回归/Contract 测试与 TS 再生成同步（27a0a69） |
| TASK-0060-05 | done | Kimi | 集中全量验证（`make check` 497 tests OK）+ 真机验收：夸克中文场景 3 轮 succeeded、runtime_acceptance 唯一命中 EditText、IME 正确恢复；验收选择器误伤修正（8ec8b9e） |
