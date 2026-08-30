# ITER-0060 Retrospective

> 文档状态：Final
> 迭代状态：Completed
> 更新日期：2026-08-30

## 实际交付

- **unicode IME 真机加固**（d9b2b47、eed04a8）：手搓 Modified UTF-7 解码器与参考
  实现逐样本对齐；读回验证改为 hint 感知（空字段 text 是 hint 占位，用
  effective_text 剔除）；注入整体丢失的判别（读回=原文摘要）+ 有界重试一次，
  覆盖 Helper IME 冷启动静默丢字符的真机竞态。
- **本地推理服务兼容**（429e522）：Provider `response_format` 可配置，本地
  OpenAI 兼容服务降级为 text 模式；解析器容忍退化 bounds。
- **E2E Suite 入库**（3e74ac9、033f77c、11b6231）：dogfood 脚本收编为显式
  device_e2e suite；新增真机模型驱动场景（中文显示设置、英文电池页、夸克中文
  输入），支持 `--device`/`--rounds`/`--deadline` 预算控制。
- **hint 选择器策略**（27a0a69）：Contract → Locator → Observation 摘要 →
  Planner prompt 四层贯通；真机验证模型自主选用 hint 定位空搜索框。
- **验收选择器修正**（8ec8b9e）：夸克场景验收从 `text+contains` 收紧为
  `exact + clickable`，唯一命中输入后的 EditText。

## 验证结果

- 集中一次 `make check`：497 tests OK（含 hint 策略 Contract/Locator/摘要断言），
  类型检查、格式检查、TS Contract 同步检查全部通过。
- 真机验收（2026-08-30，MagicOS BKQ-AN10，LM Studio 本地模型 text 模式）：
  夸克中文场景 3 轮 succeeded（120s），`completion_source=runtime_acceptance`，
  verified_node 为 text="你好" 的 EditText；技能 IME 恢复 `restored: true`，
  收尾确认设备默认输入法为搜狗。
- 本窗口内其他真机场景成功：Display settings（英文）、Battery 页（英文）。

## 偏差与限制

- **TARGET_AMBIGUOUS 根因反转**：初次失败被怀疑为 hint 策略定位缺陷（曾考虑给
  框架加 editable 过滤）。对运行时留存的 UI 树快照做 ground truth 分析后确认：
  技能路径（定位→输入→读回→IME 恢复）全部正确，9 个候选中 8 个是热搜推荐词，
  失败完全由验收选择器 `text+contains` 误伤造成。框架未动，需求拉动纪律避免了
  一次提前抽象；验收标准有歧义时显式报错的设计被证明是对的。
- **夸克冷启动证书弹窗**：每次 force-stop 后出现，稳定吃掉 2 轮预算；模型能自行
  处理（点"是"无效后改点"否"），维持暂缓决策。
- **本地模型延迟波动**：单轮 13–87s，多轮场景多次顶穿验证窗口；本窗口 25 次
  真机运行中 13 次被中断且**无任何报告落盘**——任务中断时已完成的轮次证据
  （观察、决策、动作结果）全部丢失。识别为候选需求：轮次级证据增量落盘。
- **中断残留设备状态**：一次被 kill 的运行把 AdbKeyboard 留为默认输入法（
  进程被杀时 finally 中的 IME 恢复无法执行），收尾时发现并恢复搜狗。属环境
  清理问题，但也提示「Runtime 启动时检测 helper IME 残留并提示」值得记录。
- **敏感词子串误报**（"iPhone" 命中 "phone" 数字形态拦截）：已知，待产品拍板，
  本迭代未动。

## 效率指标

- 执行窗口：2026-08-25 → 2026-08-30（有效工作日约 3 天，含真机等待）。
- 计划 Task 5 个，全部完成；无取消；无范围扩张（根因反转后未改框架）。
- 提交 8 个（另有 3 个产品文档提交：路线图需求拉动修正 1befa98/f3558f5、
  测试场景盘点 00fad6b）。
- 完整 `make check`：集中 2 次（480 基线 → 497 终态）。
- 真机运行 25 次：场景成功 4、失败/超时 8、中断无报告 13；失败主因为验收
  选择器歧义（已修）与轮次/时间预算（环境性）。
- 人工确认 0 次新增（helper 安装授权在 ITER-0059 已完成）。

## 后续行动

- **轮次级证据增量落盘**（候选需求）：每轮结束即写中间态，中断不丢现场；
  进能力路线图评估。
- 敏感词子串误报修复（待产品拍板后快速通道处理）。
- V2 入口按路线图推进：Skill 扩展与管理能力（声明式 Skill DSL 候选）。
- Runtime 启动时检测 helper IME 残留并提示（随下一轮可靠性工作评估）。
