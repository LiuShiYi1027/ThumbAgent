# ITER-0002 Acceptance

> 状态：Active  
> 更新日期：2026-07-03

## 必选验收

- [x] Observation 和 Artifact 具有 Schema 与 Contract 测试。
- [x] Observation 包含唯一 ID、设备 ID、采集时间和各部分独立时间戳。
- [x] Screenshot 为有效 PNG，并通过 Artifact 引用返回。
- [x] UI hierarchy 为可解析 XML，不通过 API 内嵌返回。
- [x] 能读取屏幕宽高、方向、前台应用和 Activity。
- [x] Artifact 使用系统生成文件名、相对引用、大小和 SHA-256。
- [x] Artifact 写入采用临时文件和原子替换，路径不能逃逸根目录。
- [x] Fake Adapter 能在无设备环境生成标准 Observation。
- [x] Android Adapter 对 offline、unauthorized 和采集失败返回结构化错误。
- [x] Runtime 提供 observe 接口且不在响应中内嵌截图或完整 UI 内容。
- [x] 默认测试集不依赖真实设备、网络或模型服务。
- [x] 质量门禁和全部自动化测试通过。

## 真机验收

- [x] 已授权 Android 真机可以生成完整 Observation。
- [x] Screenshot、UI hierarchy、前台应用和屏幕尺寸均有效。
- [x] 证据仅写入本地忽略目录，验收记录不保存 UI 内容和设备序列号。

## 验证记录

验证日期：2026-07-03  
环境：macOS arm64、Python 3.11、ADB 37.0.0、Android 16 真机

- `make check`：通过；23 个无设备测试全部通过。
- 真机 `screen.observe@1`：通过，生成 portrait Observation。
- Screenshot：PNG 有效，尺寸 1256×2808，大小和 SHA-256 已记录在本地 Artifact 元数据中。
- UI hierarchy：XML 有效，大小和 SHA-256 已记录；未写入验收文档正文。
- 前台应用：Android 16 厂商格式解析成功，返回 package 与 Activity。
- `POST /v1/devices/{device_id}/observe`：返回 Observation Contract，不内嵌截图和 XML。
- 证据路径：仓库 `data/` 本地忽略目录；Git 状态不包含证据文件。
- Device state 暂返回 `unknown`，因为本迭代没有实现可靠的锁屏/交互状态检测。
