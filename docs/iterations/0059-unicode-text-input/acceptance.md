# ITER-0059 Acceptance

> 文档状态：Final
> 迭代状态：Completed
> 更新日期：2026-08-25

## 功能验收

- [x] `input.unicode_text` 接受 CJK、空格与常见标点，长度有界（≤256）；纯 ASCII
  （`[A-Za-z0-9._-]{1,64}`）仍走现有快路径，不触发 IME 切换（Tool 层重定向为
  `INVALID_ARGUMENT` 提示改用 `input.text`）。
- [x] 验证码（4–8 位数字）、手机号（11+ 位数字）等敏感形态在 Tool 层拒绝
  （`ACTION_REJECTED_BY_POLICY`），先于任何设备动作（测试断言 `actions == []`）。
- [x] IME 切换前记录原默认输入法，完成后恢复；恢复失败返回 `IME_RESTORE_FAILED`
  （不可重试）并显著上报。真机验证：搜狗 IME 全程恢复成功。
- [x] 输入后读回目标输入框内容验证，追加语义（期望 = 输入前字段文本 + 目标文本，
  NFC 精确比对）；不一致返回 `TEXT_INPUT_NOT_VERIFIED`，不自动重试。
- [x] helper 未安装返回 `IME_HELPER_NOT_INSTALLED`，引导经 `app.install` 两阶段流程
  安装；安装后包扫描竞态由一次有界重试吸收（真机实测，见下）。
- [x] 不存在广播通道与任何接受原始 Intent extras 的代码路径；helper 仅实现
  `InputMethodService.commitText` 解码上屏，输入走既有固定 argv `input text`
  （远端 shell 参数经单引号引用）。
- [x] REST 与 MCP 入口不直接访问 ADB；MCP 只暴露 `mobile_input_unicode_text` Skill
  级入口，inputSchema 自包含（无文件级 `$ref`）。

## 工程验收

- [x] ADR-0019 已创建并 Accepted，记录 helper 分发信任模型、IME 切换/恢复语义与
  读回验证容差；真机结论已补入 Follow-up。
- [x] Contract 正向、反向与无效样本测试通过（`test_unicode_input_contract.py`）；
  `contracts/generated` 与 Schema 一致（`generate_ts_contracts.py --check`）。
- [x] 默认测试、类型检查、格式检查与 Contract 形状回归全部通过：一次集中
  `make check`，480 tests OK。
- [x] capability-model.md、technical-design-v1.md §11.4、error-handling.md 与
  迭代索引已同步。

## 真机 E2E（2026-08-25，MagicOS BKQ-AN10 / A6TG025A13002156）

执行 `scripts/e2e/e2e_iter0059.py`，六场景全部 PASS：

1. Helper APK 登记摘要校验：PASS（设备端 SHA-256 与登记值
   `6db9fd86…0ccd` 一致）。
2. Helper 两阶段安装：PASS（首次安装经 `app.install` High 授权；二次运行复用
   已安装状态）。
3. 未确认拦截：PASS（`CONFIRMATION_REQUIRED`，设备无动作）。
4. 敏感数字拦截：PASS（`ACTION_REJECTED_BY_POLICY`，设备无动作）。
5. 设置搜索框中文输入「你好世界」：PASS（读回一致，结束后恢复搜狗 IME）。
   目标控件为 `AutoCompleteTextView`（`search_src_text`）。
6. Helper 卸载还原：PASS（卸载后设备无 helper 残留，默认 IME 仍为搜狗）。

真机发现的三个问题均已修复并带回归测试（提交 6bd2016）：

- **远端 shell 拼接**：adb 将 argv 拼为远端 sh 命令行，UTF-7 编码中的 `&` 被当作
  后台操作符（exit 127）。修复：`input text` 远端参数统一单引号引用。
- **追加语义**：`commitText` 是追加而非覆盖（实测字段读出三次叠加文本）。修复：
  读回验证期望改为 输入前字段文本 + 目标文本。
- **安装后包扫描竞态**：MagicOS 上安装后 `ime enable` 立即执行会报
  "Unknown input method"，数秒后成功。修复：helper 解析加一次有界重试（1s 间隔）。

「自然语言中文任务经模型循环完成输入步骤」由 Fake Adapter 集成测试覆盖
（`test_agent_runner.py::test_agent_executes_unicode_input_skill_via_planner`、
`test_mcp_integration.py::test_mcp_inputs_unicode_text_through_local_api`）；
真机模型循环未重复执行（与迭代计划一致，E2E 聚焦设备通道本身）。
