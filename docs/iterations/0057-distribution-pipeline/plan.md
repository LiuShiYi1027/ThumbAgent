# ITER-0057 Distribution Pipeline (Sign / Notarize / Release)

> 文档状态：Completed
> 迭代状态：Active
> 更新日期：2026-08-20

## 产品结果

ThumbAgent 的 macOS 分发从「本机 ad-hoc 包」升级为「签名 + 公证 + 可发布」的流水线：
本机可用真实 Developer ID 证书产出签名 dmg；打 tag 后 GitHub Actions 自动构建、
签名、公证并发布到 GitHub Release。其他 Mac 安装不再触发 Gatekeeper 拦截。

## 范围

- `tauri.conf.json` 签名配置：Developer ID identity、hardened runtime、entitlements。
- `scripts/release-local.sh` / `scripts/notarize.sh`：本地签名构建、公证、staple。
- `.github/workflows/release.yml`：tag 触发的 macOS 构建-签名-公证-发布流水线。
- `docs/engineering/distribution.md`：证书导出、secret 清单、发布操作手册。
- 本机签名构建实测；公证在本机凭据到位后实测（凭据需用户提供）。

## 非目标

- 不做 Windows/Linux 打包与签名。
- 不做自动版本号策略（semver 由发布人决定）；不做自动更新器（updater）。
- 不把任何证书、私钥、密码写入仓库、日志或测试快照。

## 设计决策

1. 证书：本机已有 `Developer ID Application: guoqing liu (JRDVQ57V39)`（Team ID
   JRDVQ57V39），CI 侧通过 base64 p12 + 密码的 secret 导入 runner 临时 keychain。
2. 公证优先 App Store Connect API Key（`--key/--key-id/--issuer`），兼容
   Apple ID + app-specific password；本机凭据以 notarytool keychain-profile 保存，
   名称固定 `thumbagent-notary`，不入库。
3. entitlements 最小化：只保留 JIT/无签名内存等 Tauri/WebView 必需项，网络访问
   不需要 entitlement（macOS 出站默认允许）。
4. Release workflow 仅在 tag `v*` 触发；CI 的常规 push 检查不引入签名步骤。
5. 密钥材料一律经 GitHub Secrets / 本机 Keychain，不落盘入库（AGENTS.md §5）。

## 风险

- 公证凭据未就位前，本机只能验证签名不能验证公证：验收记录为 deferred，并在
  distribution.md 给出精确补凭据步骤。
- p12 导出与 secret 填写涉及人工操作，文档必须零歧义，避免私钥误传。
