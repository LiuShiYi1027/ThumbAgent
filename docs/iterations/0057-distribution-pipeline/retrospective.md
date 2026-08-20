# ITER-0057 Retrospective

> 文档状态：Completed
> 迭代状态：Completed
> 更新日期：2026-08-20

## 实际交付

- `apps/desktop/src-tauri/tauri.conf.json`：`bundle.macOS` 固定签名身份、
  hardened runtime 与 entitlements；新增 `entitlements.plist`（仅
  `allow-jit` + `allow-unsigned-executable-memory`）。
- 本机签名构建实测通过：app 与 dmg 均 `codesign -vvv --deep --strict`
  有效，Team ID `JRDVQ57V39`，runtime flag 正确。
- `scripts/release-local.zsh`（构建+签名验证，可选 `--notarize`）与
  `scripts/notarize.zsh`（submit+staple+spctl）。
- `.github/workflows/release.yml`：tag `v*` 触发的完整 CI 发布流水线。
- `docs/engineering/distribution.md`：证书导出、secret 清单、本机/CI
  发布手册。

## 验证指标

- Active → Verifying 耗时：约 1 小时（含一次完整 release 构建）
- 计划 Task 数 / 新增 / 取消：5 / 0 / 0
- `make check` / `make check-desktop` 执行次数：各 1 次，均一次通过
- 签名实测次数：1 次构建，app+dmg 双重 codesign/spctl 验证
- 公证实测次数：1 次通过（submit → staple → `spctl accepted source=Notarized Developer ID`）

## 偏差与限制

- 公证凭据由用户在迭代收尾后提供（复用既有团队级 API Key），已补测通过，
  验收条件 #4 闭环。
- release.yml 未经真实 tag 触发验证（需 GitHub Secrets 先配置）；语法经 Ruby
  YAML 解析校验，本机无 actionlint。
- 仅覆盖 macOS aarch64；Windows/Linux 打包不在 V1 范围。

## 后续行动

1. 配置 GitHub Secrets（distribution.md §3.1，`APPLE_API_KEY` 用
   `base64 -i ~/Desktop/AuthKey.p8 | pbcopy`）→ 打 `v0.1.0` tag 做首次
   CI 正式发布。
