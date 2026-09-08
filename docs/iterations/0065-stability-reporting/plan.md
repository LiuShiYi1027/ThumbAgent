# ITER-0065 Stability Reporting（稳定性报告呈现与崩溃判定）

> 文档状态：Draft
> 迭代状态：Planned
> 创建日期：2026-09-08
> 关联：[ITER-0063 复盘（跟进项 2/3）](../0063-dsl-observation-skills/retrospective.md) · [ITER-0062 复盘](../0062-declarative-skill-dsl/retrospective.md)

## 背景

稳定性测试链路（ITER-0062/0063）已能确定性执行并采集证据，但报告层只呈现
「采了 N 次」的计数：性能采样序列不可读，崩溃/ANR 需人读日志 Artifact。
本迭代把稳定性产出从「原始 Artifact」升级为「一眼可读的结论」。

## 目标

- **采样序列呈现**：DSL 稳定性任务的性能采样以紧凑序列进入 TaskRun
  evidence_summary（`evidence_summary` 是自由 object，无需 Schema 变更）；
  报告 CLI 渲染趋势表；Desktop 报告页加时间序列视图（mono 主题）。
- **崩溃/ANR 判定**：device.logs.collect 结果新增可选字段（兼容性新增）
  携带签名判定（`FATAL EXCEPTION`/`ANR in <package>` 等固定模式、脱敏后摘要）；
  判定沿 DSL step_records → evidence_summary 进入报告。
- **操作手册**：新 ROM 验收的 Helper IME 安装/启用步骤（含 ColorOS 人工确认）
  写入 scripts/e2e 说明（ITER-0064 跟进项 1 并入）。

## 非目标

- 不做实时告警/阈值告警系统；判定只是签名提取与呈现。
- 不做任意日志正则配置（签名模式是代码常量，同 DSL 白名单治理逻辑）。
- 不做官方 1.1.0 全程 10 分钟测量（运维窗口事项，不阻塞本迭代）。
- 不改 DSL 解释器语义。

## 兼容性

- `device-log-capture-result.schema.json` 增加可选字段（兼容性新增流程：
  Schema → 生成类型 → 消费者 → 契约测试）。
- 既有报告渲染对缺省字段优雅降级。

## 风险与应对

- **签名模式的 ROM 差异**：模式集合是保守子集（AOSP 标准签名），
  未命中不等于无崩溃——报告措辞为「未检测到签名」而非「无崩溃」。
- **脱敏顺序**：签名提取必须在脱敏后的文本上进行，不得把原始日志行带进报告。

## 测试与验收要点

- 签名提取：固定样本（含/不含 crash/ANR 行、脱敏后内容）单测。
- 报告渲染：CLI 快照测试；Desktop 组件渲染（tsc + 构建）。
- 契约：新字段正负样本 + TS 同步。
- 真机 E2E：跑 stability_probe 变体，报告含采样序列与崩溃判定字段。
