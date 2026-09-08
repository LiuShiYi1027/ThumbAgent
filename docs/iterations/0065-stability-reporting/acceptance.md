# ITER-0065 Acceptance

> 文档状态：Final
> 迭代状态：Completed
> 更新日期：2026-09-08

| 编号 | 验收条件 | 验证方式 | 结果 |
| --- | --- | --- | --- |
| A1 | 签名提取正确且脱敏 | 固定样本单测：含/不含 FATAL/ANR 行；提取内容不泄漏原始日志行 | 通过（3 条 Skill 测试 + 契约负向：summary 只含脱敏内容，邮箱以占位符出现） |
| A2 | 契约兼容新增 | 新字段可选、旧载荷兼容、TS 同步、契约测试 | 通过（crash_check 可选；generate_ts_contracts --check 无漂移） |
| A3 | 报告呈现 | CLI 快照测试含采样趋势与崩溃判定；缺省字段降级 | 通过（缺省报告逐字节不变钉死；畸形字段整块降级） |
| A4 | Desktop 视图 | tsc + npm build 通过；组件按 mono 主题渲染 | 通过（tsc/build 全绿、守卫 13 断言运行时冒烟）；**未实机渲染验证**——录屏权限限制 + 报告页数据走 Tauri IPC，已在复盘标注 |
| A5 | 真机 E2E | stability_probe 报告含采样序列与崩溃判定字段 | 通过（2026-09-08，OnePlus PLG110）：succeeded（141s），报告含 6 个真实采样点（CPU 7%→20% 爬升可见）与「未检测到崩溃/ANR 签名（检查 328 行）」判定行 |
| A6 | 集中全量验证 | 一次 make check 全绿 | 通过（685→711 tests OK） |
