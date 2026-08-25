# ITER-0059 Retrospective

> 文档状态：Final
> 迭代状态：Completed
> 更新日期：2026-08-25

## 实际交付

- ADR-0019（Accepted）：UTF-7 编码 IME 路线、自构建分发信任模型、切换/恢复语义、
  读回验证容差。
- `helpers/unicode-ime/`：Java 源码（`UnicodeImeService`）、免 Gradle 可复现构建脚本
  （aapt2 + javac + d8 + apksigner）、APK 与 SHA256SUMS 入仓，登记摘要
  `6db9fd86…0ccd`。
- 新能力 `input.unicode@1`（Medium 风险、需确认）；Android Adapter 五个 IME 原语
  （current/installed/enabled/enable/set），全部固定 argv。
- `domain/unicode_input.py`：Modified UTF-7 编码器（与参考实现逐样本对齐）+
  对称解码器（仅供 Fake/诊断）、敏感数字形态拦截、NFC 归一化与摘要。
- Tool/Skill `input.unicode_text`：Session+Lease 内完成 记录原 IME → enable/set →
  编码输入 → 追加语义读回验证 → 强制恢复原 IME；REST
  `/v1/skills/input.unicode_text/invoke` 与 MCP `mobile_input_unicode_text`
  （自包含 inputSchema）；Agent `_ALLOWED_SKILLS` 接入，中文目标可经模型循环完成
  输入步骤。
- 错误码：IME_HELPER_NOT_INSTALLED / IME_SWITCH_FAILED / TEXT_INPUT_NOT_VERIFIED /
  IME_RESTORE_FAILED。
- `scripts/e2e/e2e_iter0059.py`：六场景真机 E2E 脚本（显式标记，不进默认测试集）。

## 验证结果

- 集中一次 `make check`：480 tests OK（含 30+ 新增 unicode 相关用例），类型检查、
  格式检查、TS Contract 同步检查全部通过。
- 真机 E2E（2026-08-25，MagicOS BKQ-AN10）：六场景全部 PASS；E2E 后抽查设备，
  默认输入法为搜狗、helper 包无残留。
- 契约与平台测试无真实设备/网络/模型依赖；真机路径全部在 E2E 脚本中显式触发。

## 偏差与限制

- **追加语义是计划外发现**：原设计假设读回内容等于目标文本。真机实测
  `commitText` 为追加语义，验证期望改为 原文 + 目标文本。代价：字段已含目标
  文本前缀形态时无法区分「本次输入」与「历史残留」，容差仍由 NFC 精确比对兜底。
- **远端 shell 引用**：adb argv 会经远端 sh 拼接，`&`/`'` 等字符必须引用；该约束
  现在固定在 Adapter 的 `_remote_shell_quote`，但其他未来走 `input` 命令的通道需要
  复用同一函数。
- **ROM 包扫描竞态**：MagicOS 安装后 `ime enable` 有短暂滞后，当前以一次 1s 有界
  重试吸收；若其他 ROM 滞后更久，需要在 `_resolve_helper` 扩展重试预算（届时
  重审而不是静默加等待）。
- 构建工具链依赖本机 Android SDK build-tools 与 JDK 17（免 Gradle）；CI 不构建
  helper，APK 变更走「重新构建 + 更新 SHA256SUMS + 评审」手动流程。
- 自然语言中文任务的真机模型循环未在 E2E 中重复执行（Fake 集成测试已覆盖决策
  链路）。

## 效率指标

- Active → Completed：2 天（2026-08-24 → 2026-08-25）。
- 计划 Task 5 个，全部完成；无取消；范围扩张 0（追加语义、shell 引用、竞态重试
  均为真机验证的必要修复，未引入新能力）。
- 提交 6 个：ADR 提案、契约、helper+Adapter、Tool/Skill、REST/MCP、E2E 修复。
- 完整 `make check` 次数：各 Task 聚焦测试多次 + 集中 2 次（修复前基线、收尾终态）。
- 真机 E2E 往返：3 次运行（两次暴露问题、一次全绿），六场景成功率 6/6。
- 人工确认/E2E 往返：安装授权 1 次（两阶段 High 确认按设计执行）。

## 后续行动

- 剪贴板 B 档治理迭代（候选下一迭代）：Android 10+ 后台限制下的读/写分离授权
  与脱敏策略。
- 录屏快照能力（B 档候选）。
- 设置页面枚举扩充（`app.navigate@1` 白名单增补，按真实任务需求驱动）。
- 更多 ROM 采样验证 helper 兼容性（ADR-0019 Follow-up 保留项）。
