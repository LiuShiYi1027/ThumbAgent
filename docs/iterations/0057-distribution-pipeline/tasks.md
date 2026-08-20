# ITER-0057 Tasks

> 文档状态：Completed
> 迭代状态：Completed
> 更新日期：2026-08-20

| Task | 状态 | Owner | 交付 |
| --- | --- | --- | --- |
| TASK-0057-01 | done | Kimi | 迭代四份文档；现状盘点：Developer ID 证书在机（JRDVQ57V39），公证凭据缺失（用户提供，plan.md 决策 2） |
| TASK-0057-02 | done | Kimi | tauri.conf.json 签名配置（signingIdentity + hardenedRuntime + entitlements）+ entitlements.plist（最小集）；本机签名构建通过，codesign/TeamID/runtime flag 实测正确 |
| TASK-0057-03 | done | Kimi | scripts/release-local.zsh + scripts/notarize.zsh（keychain-profile `thumbagent-notary`）；公证实测 deferred（凭据待用户提供，见 acceptance #4） |
| TASK-0057-04 | done | Kimi | .github/workflows/release.yml（tag `v*`：临时 keychain 导入 p12 → 签名构建 → 校验 → 公证 → staple → gh release 上传 dmg）；docs/engineering/distribution.md 操作手册 |
| TASK-0057-05 | done | Kimi | make check + make check-desktop 全绿；release.yml YAML 校验；验收记录与复盘；收尾提交 |
