# ITER-0041 Acceptance

> 状态：Completed
> 更新日期：2026-07-21

- [x] Provider 成功决策包含总耗时和尝试次数，且不包含请求正文、响应正文或密钥。
- [x] Provider 终态失败包含失败阶段、单次及总耗时、尝试次数、重试次数和已有 HTTP/timeout 信息。
- [x] 响应头等待超时、响应体读取超时、HTTP 状态和 JSON 解码失败有确定性测试。
- [x] 可点击容器与系统安全区部分重叠时，点击点被约束到 bounds 内的安全区域。
- [x] 完全位于顶部或底部系统安全区的目标仍以 `TARGET_OUT_OF_BOUNDS` 拒绝。
- [x] CLI 和 Web 报告展示 Provider 耗时、尝试次数和失败阶段。
- [x] Contract 变化通过正向和未知字段测试，默认测试不依赖网络、模型或设备。
- [x] `make check` 与 `git diff --check` 通过。
- [x] 真机复测使用一个异步任务完成目标并读取完整报告；若环境不可用，明确记录未执行。
