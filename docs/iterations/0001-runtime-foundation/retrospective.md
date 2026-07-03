# ITER-0001 Retrospective

> 状态：Active  
> 更新日期：2026-07-03

## 实际交付

- Monorepo 基础目录、Makefile、Python 项目配置和忽略规则。
- Device JSON Schema 与 Python 领域模型。
- Runtime 健康检查和设备列表 HTTP 接口。
- Device Adapter Protocol 与 Fake Adapter。
- 无 shell、带参数校验、超时、取消和输出限制的 ADB Runner。
- Android `adb devices -l` 解析、设备映射和系统版本读取。
- 14 个无设备单元、Contract 和集成测试。

## 验收结果

- 全部必选验收通过。
- Runtime HTTP 健康检查通过。
- 本机真实 ADB daemon 与已授权 Android 16 真机通路通过，设备字段和 HTTP Contract 验证成功。

## 计划偏差

- 原技术方案要求 Python 3.12+，开发环境只有稳定可用的 Python 3.11，因此将最低版本调整为 3.11+。
- 为避免在工程骨架阶段引入网络和依赖阻塞，健康检查使用标准库 HTTP Server，FastAPI/Pydantic 延后到完整 API 迭代。
- ITER-0001 使用依赖无关质量脚本；Ruff/Pyright 尚未锁定进入开发环境。

## 有效做法

- Contract-first 让 Fake Adapter、Android Adapter 和 HTTP 输出共享同一数据形状。
- Process Runner 抽象使 ADB 行为无需真实设备即可测试。
- 先验证真实 ADB 空设备路径，确认了系统权限与沙箱差异。

## 问题与根因

- 沙箱不允许启动 ADB daemon 或监听 loopback，需要在受控的沙箱外执行这两项只读验收。
- `adb devices -l` 不直接提供 Android 系统版本，online 设备需要一次额外 `getprop` 查询。

## 长期文档回写

- 技术方案和工程规范的 Python 最低版本已更新为 3.11+。
- 贡献指南已登记当前唯一可信的开发命令。

## 后续行动

- 下一迭代实现标准 Observation：截图、前台应用和 UI hierarchy。
- 在引入第三方框架时建立锁文件，并用 Ruff/Pyright 替换 bootstrap 质量检查。
- 真机断连验收仍待补做；设备字段验收已完成。
