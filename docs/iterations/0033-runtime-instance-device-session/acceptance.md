# ITER-0033 Acceptance

> 状态：Completed
> 更新日期：2026-07-14

- [x] 同一数据目录的第二个 Runtime 在创建服务前收到 RUNTIME_ALREADY_RUNNING。
- [x] Runtime 退出释放锁，后续 Runtime 可以启动；锁文件权限为 0600。
- [x] 设备连续在线时保持 Session，消失或离线后重连生成新 Session。
- [x] Task/Tool/Skill 在动作和 Observation 前校验绑定 Session。
- [x] 旧任务遇到重连以 DEVICE_SESSION_CHANGED 停止，且不派发该动作。
- [x] Device、TaskRun 和 TaskExecution Contract 记录会话身份。
- [x] Web/CLI 报告展示设备会话，不显示密钥或未过滤模型内容。
- [x] 全量质量检查和隔离双进程 Runtime 冒烟通过。
