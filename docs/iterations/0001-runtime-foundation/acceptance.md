# ITER-0001 Acceptance

> 状态：Active  
> 更新日期：2026-07-03

## 必选验收

- [x] 新环境能够按贡献指南安装并运行 Runtime。
- [x] 健康检查返回明确的 Runtime 版本和可用状态。
- [x] Device Contract 具有 Schema 和自动化 Contract 测试。
- [x] 默认测试集不依赖 ADB、真实设备、网络或模型密钥。
- [x] Fake Adapter 能返回至少一个 Android 测试设备。
- [x] ADB Runner 不使用 shell，并具备超时、取消和输出限制。
- [x] `adb devices -l` 的 online、offline、unauthorized 和空列表均有解析测试。
- [x] Android 设备发现统一映射为 Device Contract。
- [x] ADB 不存在时返回结构化错误，不产生未处理异常。
- [x] Format、Lint、类型检查、单元和 Contract 测试有统一命令。
- [x] 仓库不包含密钥、设备数据、用户路径或构建产物。

## 可选真实设备验收

- [x] 连接一台已授权 Android 设备后能返回设备 ID、型号、系统版本和 online 状态。
- [ ] 拔出设备后下一次发现结果不再报告 online。

真实设备不是默认 CI 的完成前提，但若环境可用应执行并记录结果。

## 验证记录

验证日期：2026-07-03  
环境：macOS arm64、Python 3.11、ADB 37.0.0

- `make check`：通过；基础 Lint、注解检查和 14 个无设备测试全部通过。
- `/v1/health`：返回 `status=ok`、Runtime `0.1.0`、API `v1`。
- `/v1/devices`：通过真实 ADB daemon 返回 HTTP 200；空设备和单台已授权真机两种路径均通过。
- 真机字段验收通过：正确返回 Android 平台、设备型号、Android 16、online 状态和 `device.inspect@1`；验收记录不保存设备序列号。
- 拔出设备验收未执行：本轮保持用户设备连接，不主动中断连接。

ITER-0001 的质量门禁为零外部依赖 bootstrap 检查器。后续锁定 Ruff 与 Pyright 依赖后，由其接管相同 Make targets。
