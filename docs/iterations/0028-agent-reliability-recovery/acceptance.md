# ITER-0028 Acceptance

> 状态：Completed
> 更新日期：2026-07-13

- [x] 蓝牙页面文本匹配歧义会产生 failed round 并允许收紧 Selector 后成功。
- [x] `finish` 可同时验证前台 app/activity 和 UI Selector。
- [x] 屏幕顶部系统区和底部手势区的点击在 Adapter 调用前被拒绝。
- [x] 可恢复错误的 failed step 保留 Decision、Observation、Error 和 feedback。
- [x] Provider 错误包含脱敏 `failure_kind`，密钥和响应体不进入详情。
- [x] retryable 模型请求最多自动重试一次，不调用设备。
- [x] Web/CLI 显示 Provider 重试次数。
- [x] Web/CLI 只显示无效 Selector 的字段级脱敏诊断。
- [x] 模型省略 `reason` 时生成固定审计说明，不触发修复请求。
- [x] 失败 `payload_summary` 不保存 Selector `value`。
- [x] `make check` 通过。
- [x] 真机简短目标“显示和亮度”与“蓝牙”复测通过。
- [x] 重启加载最终修复后，详细“显示和亮度”复测通过。

## 验证命令

```bash
make check
```

真机 E2E 必须显式运行，不进入默认测试集。
