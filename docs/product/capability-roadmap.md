# Mobile Agent 能力路线图（候选清单与分级治理）

> 文档状态：Draft
> 更新日期：2026-08-25
> 关联：[产品定位](./positioning.md) · [Capability 模型](../architecture/capability-model.md) · [ADR-0018](../adr/0018-programmatic-navigation-shortcuts.md) · [ITER-0058 复盘](../iterations/0058-programmatic-navigation/retrospective.md)

## 1. 目的

回答一个问题：**平台该支持哪些设备动作，按什么顺序接入？**

本文档把 ADB 及平台层可做的动作整理为候选清单，按价值与风险分级，作为后续迭代的排期依据。
它不做实现承诺；任何候选进入开发前仍须走完完整评审链路（见 §5）。

## 2. 治理原则

1. **需求拉动，不提前囤货。** 每个候选必须能指出真实任务场景；没有场景的不进 A 档。
   出现第二个真实实现需求时再提炼通用层，不为假想需求抽象。
2. **一能力一评审。** 每个能力独立完成 Contract Schema、Capability 风险定级、Policy 接入、
   后置验证设计、测试矩阵与真机 E2E；高风险能力另需独立 ADR（ADR-0016/0017/0018 模式）。
3. **逃生口红线不可谈判。** 任意 shell、原始 Intent 参数、任意 URI、pm 权限操作等
   永不成能力（C 档），任何迭代不得以"开发方便"为由开洞。
4. **精选优于全集。** 混合动作空间的价值来自高频路径程序化（StateAct：GUI 兜底约 1%），
   程序化捷径优先、GUI 动作兜底，而非动作数量堆积。
5. **ROM 差异是一等成本。** ITER-0058 真机 E2E 暴露的 MagicOS 差异（extras 脱敏、
   冷启动限制）说明：每个能力都要为厂商 ROM 变体预留验证与兼容预算。

## 3. 已交付基线（V1 现状）

```text
设备与观察    device.inspect@1 · screen.observe@1
GUI 动作      input.tap@1 · input.text@1（ASCII 快路径）· input.swipe@1
              input.unicode@1（Helper IME：CJK/Unicode，Medium 确认）
              navigation.back@1 · navigation.home@1
应用管理      app.launch@1 · app.inspect@1 · app.install@1（High）
              app.uninstall@1（High）· app.state.inspect@1 · app.stop@1
              app.data.clear@1（High）
诊断          logs.collect@1 · performance.snapshot@1 · device.diagnostics.bundle@1
程序化捷径    app.navigate@1（14 个系统设置页面枚举直达）
通知          notifications.read@1（有界脱敏快照）
Runtime 本地  local.data.cleanup（非设备 Capability）
```

## 4. 候选清单

### 4.1 A 档：需求明确、低/中风险，按序接入

| 候选 | 真实场景 | 风险预判 | 验证方式 | ROM 风险 |
| --- | --- | --- | --- | --- |
| CJK 文本输入 helper | Agent 填写中文表单、搜索词；当前 `input.text` 仅 ASCII，中文任务是硬阻塞 | Low（输入类） | 输入后读取输入框内容比对 | 输入法 APK 兼容性；备选 ADBKeyBoard/广播方案需评审 |
| 音量/亮度/媒体控制 | 「调低音量」「截图时避免满亮度」等设置类任务高频子步骤 | Low（状态可逆） | 读取 settings/dumpsys 状态前后比对 | 厂商设置项 key 差异 |
| 录屏快照（有界时长） | Bug 复现取证、任务执行证据增强（超越静态截图） | Medium（屏幕内容 PII） | 固定时长上限 + 文件大小校验 + Artifact 登记 | `screenrecord` 参数差异小，风险低 |
| 设置页面枚举扩充 | 真机使用中暴露的新高频页面（如电池、通知管理、默认应用） | Low | 沿用 ITER-0058 后置验证模板 | 各 ROM Activity token 采样 |
| 电池/网络聚合只读 | 「电量是否健康」「当前是否连 Wi-Fi」类诊断问答 | Low（safe 只读） | 聚合字段 Schema 校验 | dumpsys 字段差异（ITER-0058 已有教训） |

### 4.2 B 档：有价值，但需要专门的治理或信任设计

| 候选 | 真实场景 | 治理缺口 | 前置条件 |
| --- | --- | --- | --- |
| Deep Link / URI 白名单跳转 | 「打开微信扫一扫」「直达应用内页面」 | URI 白名单治理、scheme 风险分级、防钓鱼 | 独立迭代 + ADR（ITER-0058 已明确排除） |
| 剪贴板读取/写入 | 跨应用搬运文本、配合 CJK 输入 | 剪贴板含密码等敏感内容的脱敏与确认语义 | 数据分类策略；写入需确认 |
| 文件传输（push/pull） | 测试素材下发、日志回取 | 目录白名单、大小上限、路径遍历防护 | 作用域绑定 Approval（ADR-0016 模式） |
| 短信/来电只读检测 | 「验证码短信是否到达」类验证 | 通信内容 PII 分级、本地留存边界 | 隐私影响评估；可能只做"存在性"不取内容 |
| Wi-Fi/蓝牙等射频开关 | 网络状态切换类测试 | 设备写状态的用户确认与恢复语义 | 状态回滚验证设计 |

### 4.3 C 档：明确不做（逃生口与越界能力）

```text
任意 shell 命令执行
pm grant/revoke 等权限操作（绕过系统授权模型）
账号登录/支付/验证码绕过
恢复出厂、系统分区写入、root 相关操作
静默安装/卸载（绕过两阶段确认）
读取或转发通知正文、短信正文等内容级数据（默认丢弃，只保留元数据）
```

### 4.4 复合 Skill 与平台扩展候选

以下候选不是新设备动作，而是既有能力的组合方式与扩展形态，单独治理。

| 候选 | 类型 | 真实场景 | 治理缺口 | 前置条件 |
| --- | --- | --- | --- | --- |
| 应用稳定性测试 Skill（`app.stability_test`） | 官方内置 Skill，纯编排既有能力，无新设备原语 | 「打开京东搜索 iPhone 17，再做 5 分钟稳定性测试」类复合意图：时间盒内确定性遍历交互 + 崩溃/ANR 判定 + 性能曲线采样 + 结构化报告 | 时长与动作频次上限、报告模板、任务取消语义；日志 PII 沿用 `logs.collect@1` 脱敏边界 | 普通迭代（B 档治理粒度），确定性遍历优先于 Monkey 随机 |
| Skill 扩展与管理 | V2 平台元能力：agent 的技能生态与生命周期治理，「全能移动端操作 agent」的扩展形态 | 用户/第三方自定义复合技能（稳定性测试为首驱动场景），并对技能做注册/查看/启停/版本/卸载管理 | 双重信任边界：① 执行边界——禁止任意代码入 Runtime，声明式 DSL 由 Runtime 解释执行，只能引用已登记 Tool/Capability，风险等级从所编排能力派生，继承 Policy 授权与确认语义；② 管理边界——Skill Registry 从启动期装配改为持久化运行时状态，带审计与管理面 | 独立 ADR + DSL Contract Schema + Skill Registry 持久化与管理面（REST/Desktop）设计 |

## 5. 接入流程（每个候选的固定路径）

1. 在本文档确认场景与档位；A 档候选可直接进入迭代规划。
2. 迭代计划写明 Contract、Capability 风险定级、后置验证与 ROM 兼容预算。
3. 按「新 Capability 接入模板」实施（ITER-0058 已沉淀：枚举映射 / 固定 argv /
   后置验证 / 脱敏边界 / 错误码登记）。
4. 真机 E2E 集中一次执行；Medium 以上风险需用户明确授权。
5. 完成复盘并回填本文档基线表。

## 6. 近期排期建议

- ~~ITER-0059~~：CJK 文本输入 helper 已交付（`input.unicode@1`，UTF-7 Helper IME 路线，
  真机六场景全 PASS，见 [ITER-0059 复盘](../iterations/0059-unicode-text-input/retrospective.md)）。
- 其后按真实任务暴露的需求拉动：候选池见 §4（A 档设备动作与 §4.4 复合 Skill/平台扩展
  候选，含音量/亮度、录屏快照、设置枚举扩充、稳定性测试 Skill）；候选仅在真实场景
  重复出现时进入排期。
- 每次迭代接入 1–2 个候选，保持评审粒度。
