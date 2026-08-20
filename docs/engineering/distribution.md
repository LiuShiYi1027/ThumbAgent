# 分发与发布（Distribution）

> 文档状态：Active
> 更新日期：2026-08-20

本文档描述 ThumbAgent macOS 安装包的签名、公证与发布流程。
密钥与证书材料**一律不进入仓库**，只存在于本机 Keychain、Apple Developer
账户与 GitHub Secrets 中。

## 1. 签名资产

| 资产 | 位置 | 说明 |
| --- | --- | --- |
| `Developer ID Application: guoqing liu (JRDVQ57V39)` | 本机登录 Keychain / CI 临时 keychain | 应用与 dmg 签名身份 |
| Team ID `JRDVQ57V39` | Apple Developer 账户 | 公证与校验用 |
| `apps/desktop/src-tauri/entitlements.plist` | 仓库 | 最小权限集：仅 `allow-jit` 与 `allow-unsigned-executable-memory`（WKWebView 需要） |

签名配置固定在 `apps/desktop/src-tauri/tauri.conf.json` 的 `bundle.macOS`：
`signingIdentity` + `hardenedRuntime: true` + `entitlements`。

## 2. 本机发布

```sh
# 构建 + 签名验证（若已配置公证 profile，会提示后续命令）
scripts/release-local.zsh

# 构建 + 签名验证 + 公证 + 装订票据
scripts/release-local.zsh --notarize

# 单独公证某个 dmg
scripts/notarize.zsh apps/desktop/src-tauri/target/release/bundle/dmg/ThumbAgent_0.1.0_aarch64.dmg
```

验证命令（脚本已内置）：

```sh
codesign -vvv --deep --strict ThumbAgent.app   # 签名有效
codesign -dv --verbose=4 ThumbAgent.app        # TeamIdentifier=JRDVQ57V39，flags 含 runtime
spctl -a -vv --type install <dmg>              # 公证后应为 accepted
```

### 2.1 配置本机公证凭据（二选一）

App Store Connect API Key（推荐，CI 也用同一套）：

```sh
xcrun notarytool store-credentials thumbagent-notary \
  --key ~/AuthKey_<KEY_ID>.p8 --key-id <KEY_ID> --issuer <ISSUER_ID>
```

Apple ID + App 专用密码：

```sh
xcrun notarytool store-credentials thumbagent-notary \
  --apple-id <apple-id> --team-id JRDVQ57V39   # 交互输入专用密码
```

profile 名默认为 `thumbagent-notary`，可用环境变量
`THUMBAGENT_NOTARY_PROFILE` 覆盖。

## 3. CI 发布（GitHub Actions）

`.github/workflows/release.yml` 仅在推送 `v*` tag 时触发：

1. 在 runner 临时 keychain 中导入签名证书（job 结束即销毁）。
2. `npm run tauri build` 按 `tauri.conf.json` 完成签名。
3. 校验签名（`codesign` + Team ID + hardened runtime flag）。
4. 按已配置的 secret 自动选择公证方式并 `staple`。
5. `gh release create` 上传 dmg 并生成 Release Notes。

发布操作：

```sh
git tag v0.1.0
git push origin v0.1.0
```

### 3.1 需要的 GitHub Secrets

| Secret | 必需性 | 内容 |
| --- | --- | --- |
| `APPLE_CERTIFICATE` | 必需 | Developer ID 证书导出的 `.p12` 的 base64：`base64 -i Certificates.p12 \| pbcopy` |
| `APPLE_CERTIFICATE_PASSWORD` | 必需 | 导出 p12 时设置的密码 |
| `APPLE_API_KEY` | 方式一 | App Store Connect API Key `.p8` 的 base64 |
| `APPLE_API_KEY_ID` | 方式一 | API Key ID |
| `APPLE_API_ISSUER` | 方式一 | Issuer ID |
| `APPLE_ID` | 方式二 | Apple ID 邮箱 |
| `APPLE_APP_PASSWORD` | 方式二 | App 专用密码（appleid.apple.com 生成） |
| `APPLE_TEAM_ID` | 方式二 | `JRDVQ57V39` |

方式一（API Key）与方式二（Apple ID）二选一；两者都未配置时 workflow
发布**已签名但未公证**的包并给出 warning。

### 3.2 从 Keychain 导出 p12

1. 打开「钥匙串访问」→ 登录 → 我的证书。
2. 选中 `Developer ID Application: guoqing liu (JRDVQ57V39)` 及其私钥。
3. 右键导出为 `Certificates.p12`，设置导出密码（即 `APPLE_CERTIFICATE_PASSWORD`）。
4. `base64 -i Certificates.p12 | pbcopy` 粘贴到 `APPLE_CERTIFICATE` secret。
5. 删除本地 `Certificates.p12`。

## 4. 安全约束

- 证书、p12、p8、密码、专用密码一律只存在于 Keychain / Secrets，不进代码、
  日志、测试快照与文档。
- CI workflow 不回显任何 secret 值；证书文件导入后立即删除。
- 未公证的包可以发布（warning），但分发给最终用户前必须完成公证，
  否则 Gatekeeper 会拦截。
