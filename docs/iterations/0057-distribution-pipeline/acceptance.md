# ITER-0057 Acceptance

> 文档状态：Completed
> 迭代状态：Completed
> 更新日期：2026-08-20

## 验收条件

1. `tauri build` 在本机产出以 `Developer ID Application: guoqing liu (JRDVQ57V39)`
   签名的 ThumbAgent.app / dmg：`codesign -vvv --deep --strict` 通过，
   `codesign -dv` 显示正确 Team ID 与 hardened runtime flags。
2. 仓库不含任何证书、私钥、密码；签名/公证脚本不打印密钥材料。
3. `release.yml` 在 tag `v*` 触发，包含导入证书、签名构建、公证、staple、
   上传 GitHub Release 完整步骤；所需 secret 在 distribution.md 逐一列出。
4. 公证：本机凭据（notarytool profile `thumbagent-notary`）到位后，
   `scripts/notarize.zsh` 完成 submit + staple，`spctl -a -vv --type install`
   显示 `accepted source=Notarized Developer ID`；凭据未到位则明确记录 deferred。
5. `make check-desktop` 通过；release workflow 语法经 actionlint 或等效检查。

## 验收记录

| # | 结果 | 证据 |
| --- | --- | --- |
| 1 | 通过 | 2026-08-20 本机构建：`codesign -vvv --deep --strict` 对 ThumbAgent.app 与 `ThumbAgent_0.1.0_aarch64.dmg` 均 `valid on disk / satisfies its Designated Requirement`；`codesign -dv` 显示 `Authority=Developer ID Application: guoqing liu (JRDVQ57V39)`、`TeamIdentifier=JRDVQ57V39`、`flags=0x10000(runtime)`。`spctl -a -vv --type execute` 为 `rejected source=Unnotarized Developer ID`——签名正确、公证未做，属预期（见 #4）。 |
| 2 | 通过 | `scripts/release-local.zsh` / `scripts/notarize.zsh` 只引用 keychain profile 名，不含密钥；release.yml 全部经 `${{ secrets.* }}` 读取且不回显；证书文件 CI 导入后即 `rm`。仓库无 p12/p8/pem 等材料。 |
| 3 | 通过 | `.github/workflows/release.yml`：on push tags `v*`；步骤覆盖临时 keychain 导入证书 → `npm run tauri build` 签名 → codesign/TeamID/runtime 校验 → 公证（API Key 或 Apple ID 二选一，未配置则 warning 跳过）→ staple → `spctl` 校验 → `gh release create` 上传 dmg。secret 清单见 `docs/engineering/distribution.md` §3.1。 |
| 4 | 通过（2026-08-20 补测） | 用户复用既有 App Store Connect API Key（team 级）配置 profile：`xcrun notarytool store-credentials thumbagent-notary --key ~/Desktop/AuthKey.p8 --key-id 2KBK5599QD --issuer 1a9717b6-…-11a9`，凭据验证通过存入钥匙串。`scripts/notarize.zsh` 实测：`notarytool submit --wait` 成功、`stapler staple` 成功、`spctl -a -vv --type install` 显示 `accepted source=Notarized Developer ID origin=Developer ID Application: guoqing liu (JRDVQ57V39)`。 |
| 5 | 通过 | `make check` 与 `make check-desktop` 全绿（见 retrospective 验证指标）；release.yml 经 Ruby YAML 解析校验通过（本机无 actionlint/yaml 模块，等效检查）。 |
