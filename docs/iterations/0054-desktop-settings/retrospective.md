# ITER-0054 Retrospective

> 文档状态：Done
> 迭代状态：Done
> 更新日期：2026-08-20

## 实际交付

- Runtime：`GET/POST /v1/model-provider/config`。GET 返回磁盘配置的非敏感视图
  （含 config_file、env_override 标记），不要 token；POST 走既有 `_authorize_post`，
  拒绝未知字段、强制 `enabled` 必填、强制 `env:MOBILE_AGENT_MODEL_SECRET_*` 引用模式，
  enabled 时做完整校验，tmp + os.replace 原子写 0600。密钥值永不经过端点。
- Sidecar：Keychain 存/取/删（固定 `/usr/bin/security` argv，无新 crate），启动与
  `restart_runtime` 时把密钥注入子进程 `MOBILE_AGENT_MODEL_SECRET_DESKTOP`；
  `data_dir_path`/`reveal_data_dir`；POST 白名单放行配置保存路径。
- 设置页 UI：Provider 表单、密钥状态徽章与存/清、保存并重启（进行中任务弹中断确认）、
  env_override 警告、数据目录 Finder 入口；header 齿轮切视图。
- 测试：Python +14（单元 8 + API 6），Rust +4（共 21）。
- 规范同步：technical-design-v1.md 增加 ITER-0054 段，README 中英更新当前进展。

## 验证指标

- Active → Verifying 耗时：约 1 个工作日（同一会话内完成 4 个实现 Task）
- Verifying → Completed 耗时：约 30 分钟（真机一次通过）
- 计划 Task 数 / 新增 / 取消：5 / 0 / 0
- 完整 `make check` / `make check-desktop` 执行次数：2 / 2（含修复后重跑）
- 真机 E2E 往返次数：1
- 真机场景成功数与失败原因：1/1 成功（settings.display-brightness.v1，rounds=1，passed=true）

## 偏差与限制

- 密钥经 `/usr/bin/security -w` argv 传递，理论上同机其他进程在写入瞬间可经 `ps`
  看到参数。V1 接受该折衷（本机单用户、不引新 crate）；后续可用 Security framework
  binding 消除。
- 重启生效语义意味着 sidecar 重启会换端口与令牌，进行中的任务随旧进程终止；
  UI 已用确认对话框显式提示，不做任务迁移。
- 设置页仅在 macOS 验证（Keychain/Finder 均为 macOS 路径）；Windows/Linux 桌面端
  属于 V1 边界之外。
- GET 配置不要 token（与 status 端点一致），仅监听 loopback 且视图不含密钥值。

## 后续行动

- 打包分发（`tauri build`）前补一次签名/公证方案评估。
- 若引入更多 Provider 类型，考虑把设置页表单抽象为按 provider schema 驱动。
