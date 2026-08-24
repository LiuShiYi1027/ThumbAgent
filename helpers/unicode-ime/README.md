# ThumbAgent Unicode IME Helper

受控输入法 Helper：为 `input.unicode@1` 能力提供 Unicode 文本输入通道。
设计决策与信任模型见 [ADR-0019](../../docs/adr/0019-unicode-input-ime-helper.md)。

## 工作原理

1. 主机侧把目标文本编码为 Modified UTF-7（纯 ASCII，RFC 3501 变体，
   空格与 `%` 也进入 base64 块，规避 `input text` 的解析歧义）。
2. 编码文本经既有固定 argv 管道 `adb shell input text <encoded>` 注入。
3. 本 IME 在 `onKeyDown` 中识别 `&...-` 移位块，用平台内置
   `x-IMAP-mailbox-name` 字符集解码并 `commitText` 上屏。
4. Runtime 完成 UI Tree 读回验证后恢复原输入法。

Helper 无广播接收器、无 IPC 端点、无键盘 UI；输入内容不写入 logcat。

## 目录

```text
AndroidManifest.xml                     # 仅声明一个 BIND_INPUT_METHOD 服务
res/                                    # label 与 IME subtype 配置
src/com/thumbagent/unicodeime/          # 单文件 InputMethodService
keystore.jks                            # 固定签名密钥（构建 fixture，无外部安全语义）
build.sh                                # 免 Gradle 构建：aapt2 + javac + d8 + apksigner
dist/unicode-ime.apk                    # 登记产物
dist/SHA256SUMS.txt                     # 登记摘要，安装前校验的唯一依据
```

## 构建

依赖：Android SDK（`build-tools` + `platforms`）与 JDK 17+（`brew install openjdk@17`）。

```bash
helpers/unicode-ime/build.sh
```

同一工具链下构建可复现（两次构建 SHA-256 一致）。产物或摘要的任何变化
都意味着源码或工具链变化，必须重新评审并同步更新 Runtime 登记值。

## 签名与摘要

- 当前登记 SHA-256：见 `dist/SHA256SUMS.txt`。
- `keystore.jks` 是仓库内固定 fixture（口令 `thumbagent-unicode-ime`，公开），
  作用仅是保证重复构建与重装时签名一致；完整性锚点是登记摘要 + 源码评审，
  不是签名身份。

## 安装

不新开安装通道：一律经 Runtime 既有 `app.install@1` 两阶段 High 风险授权，
安装前校验 SHA-256，不符即拒绝。

## 许可与归属

基于 TOYAMA Sumio 的 Unicode Input Helper（Appium 项目 `io.appium.settings`
维护的版本）修改，Apache License 2.0，见 `NOTICE`。本仓库内的修改同样以
Apache-2.0 提供。
