# ITER-0064 Retrospective

> 文档状态：Final
> 迭代状态：Completed
> 更新日期：2026-09-08

## 实际交付

- **M4 响应式控制探针**（b0bb7df）：Provider decide 经 `asyncio.to_thread` 移出
  事件循环，Runner 等待期间以 `asyncio.wait` 事件驱动轮询取消/暂停/deadline
  （0.5s 间隔，快乐路径零额外延迟）；放弃等待的线程已验证为纯 HTTP 读、无设备
  副作用、无共享状态写入。
- **unicode 读回时机**（b0bb7df）：节点缺席（match_count=0/actual null）settle
  0.5s 后只读重读一次；与 tamper（内容不一致）严格区分；重读预算与丢失重注入
  预算各 ≤1 不叠加。
- **queued 可暂停**（b0bb7df）：queued→paused 立即生效（无轮次边界），执行器
  跳过 parked 项；resume 回 queued 重新入队；queued-paused 取消立即收尾；重启
  恢复 TASK_INTERRUPTED。
- **M5 捷径证据链**（b0bb7df）：shortcut_step 先落盘再验收；
  TARGET_NOT_FOUND/AMBIGUOUS 回退模型主循环，观察故障/取消仍立即终止；
  步骤序号顺延保持单调唯一。
- **Web UI 稳定幂等键**（b0bb7df）：内嵌 JS 经 WebCrypto 与服务端
  `stable_idempotency_key` 同算法派生（webui- 前缀）；5 个提交点接入；
  非安全上下文退化为随机键（能力不降级）。

## 验证结果

- 集中全量验证：685 tests OK（净增 20），契约/类型/格式同步全过。
- 真机（2026-09-08，OnePlus PLG110，Android 16/ColorOS）：
  - **暂停延迟 1.3s**（模型调用进行中）；修复前同窗口延迟为整个模型调用时长。
  - 事件链完整：queued→started→pause_requested→paused→resumed→cancel_requested
    →cancelled。
  - unicode 中文输入场景 succeeded（2 轮 90s），Runtime 验收锁定 EditText 内容；
    Helper IME 在 ColorOS 上首次安装启用成功。
- 单测复现矩阵：9 条新测试全部有「修复前失败、修复后通过」记录。

## 偏差与限制

- **取消在设备动作窗口仍按轮次边界生效**：真机实测取消落在 observe/动作阶段的
  延迟约 20-25s（adb 子进程不可中断是设计内行为）；M4 只覆盖模型调用窗口。
  文档已明确，未扩大范围。
- **验收设备再次更换**：Honor → OnePlus。Helper IME 需要人工确认安装
  （ColorOS InstallGuideActivity）——这是设计内的安全边界，不绕过；多 ROM
  验收的 IME 安装步骤值得写入 E2E 操作手册。
- queued-paused 期间 deadline 不计时（从 running 起算），与既有 queued 语义
  一致，已文档化。
- Web UI 幂等键在非安全上下文退化为随机键；本地 Web UI 场景可接受。

## 效率指标

- 迭代窗口：2026-09-02 立项 → 2026-09-08 关闭（含等待设备安装窗口）。
- 提交：1 个立项 + 1 个实现批次；测试净增 20 条。
- 真机运行：2 次 Agent 任务 + 1 次 unicode 场景，全部产生可解释终态。

## 后续行动

1. **E2E 操作手册补充**：新 ROM 验收时的 Helper IME 安装/启用步骤
   （含 ColorOS 人工确认）写入 docs 或 scripts/e2e README。
2. **设备动作窗口的取消粒度**（观察项）：adb 子进程超时中断是否值得引入，
   待真实「长动作卡顿」场景出现再评估。
3. 下一迭代：ITER-0065（0063 跟进项——采样呈现 + 崩溃/ANR 判定 + 全程测量）。
