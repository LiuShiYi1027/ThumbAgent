# ITER-0063 Retrospective

> 文档状态：Final
> 迭代状态：Completed
> 更新日期：2026-09-02

## 实际交付

- **ADR-0021 Amendment 1**：DSL 可引用白名单内置观察类 Skill
  （`device.performance.snapshot`、`device.logs.collect`）；白名单为编译期常量，
  不接受文档或 REST 扩展。
- **skill_step 契约**（b13aa75）：兼容性新增；控制体接受工具与 Skill 引用步骤；
  解析器/生成类型/契约测试同步。
- **解释器 Skill 引用执行**（9bf0317）：`skill_invoker` 注入；缺失即 preflight
  拒绝；步骤记录携带 skill_id；on_step 回调覆盖。
- **任务链路接线**（9bf0317）：`build_dsl_skill_invoker` 白名单映射闭包（严格
  参数校验）；`*_under_task_lease` 薄封装解决嵌套设备租约 DEVICE_LOCKED。
- **app.stability_test@1.1.0**：循环内每迭代性能采样 + 收尾日志崩溃/ANR 证据；
  1.0.0 版本不可变保留。

## 验证结果

- 全量门禁：665 tests OK，契约/类型/格式/TS 同步全过。
- 真机（2026-09-02，OnePlus PLG110，Android 16）：
  - `app.stability_probe`（1.1.0 结构的 2 分钟盒变体）**succeeded**（151s）：
    32 步——launch×2、swipe×14、back×7、性能采样×7（每迭代一次）、
    logs.collect×1，0 失败，goal=`skill_id@version`，证据摘要含文档哈希。
  - 管理面沿用 0062 证据；本次新设备注册、派生风险 medium、confirmed 门均正常。

## 偏差与限制

- **官方 1.1.0 全程未跑**：循环天花板 600s/200iter 超出会话窗口；A5 以等价
  短变体完成机制验收。完整 10 分钟行为（发热/内存爬升）仍未测量。
- **崩溃/ANR 判定是证据采集而非断言**：logs.collect 保存脱敏日志 Artifact，
  是否崩溃由人读报告判断；自动崩溃检测留给真实需求拉动。
- **验收中途换机**：Honor BKQ-AN10 掉线后改用 OnePlus PLG110——旧 device_id
  任务正确失败（DEVICE_NOT_FOUND），无误报；DSL 链路在第二台 ROM 上首次通过，
  顺带提供了跨 ROM 证据。
- invoker 返回值目前不校验（契约未要求）；采样结果的结构化呈现（性能曲线
  视图）属后续呈现层工作。

## 效率指标

- 迭代窗口：2026-09-02 当天立项到关闭。
- 提交：2 个 feature 提交；测试净增 14 条（651→665）。
- 真机运行：3 次任务（旧设备 id 正确失败 1 次、探针 succeeded 1 次、
  另有 0062 遗留窗口 1 次），全部可解释。

## 后续行动

1. **官方文档全程测量**：在有充电/控温条件的窗口跑 `app.stability_test@1.1.0`
   完整 10 分钟时间盒，记录长时行为。
2. **采样结果呈现**：性能采样序列在报告/Desktop 的时间序列视图。
3. **崩溃/ANR 自动判定**：从日志 Artifact 提取 crash/ANR 签名进入报告字段
   （真实需求拉动）。
4. 沿用 0062 跟进项：Desktop 管理页、MCP 只读清单。
