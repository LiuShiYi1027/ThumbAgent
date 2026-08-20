# ITER-0054 Acceptance

> 文档状态：Done
> 迭代状态：Done
> 更新日期：2026-08-20

## 验收条件

1. **GET 配置**：`GET /v1/model-provider/config` 返回 enabled/provider/base_url/model/
   api_key_ref/timeout_seconds、config_file 路径与 env_override 标记；无配置文件时返回
   禁用默认值；不返回任何密钥值。
2. **POST 配置**：`POST /v1/model-provider/config`
   - 无 token 401；非法 base_url、超范围 timeout、enabled 缺字段、api_key_ref 不匹配
     `env:MOBILE_AGENT_MODEL_SECRET_*` 模式均 400；
   - 合法输入原子写入 `<data-dir>/model-provider.json`（0600），enabled=false 可随时保存；
   - 断言写入文件不含密钥值；响应带 restart_required。
3. **sidecar 密钥**：Keychain 存/取/删命令构造正确（固定 `/usr/bin/security` argv）；
   启动 Runtime 时在密钥存在时注入 `MOBILE_AGENT_MODEL_SECRET_DESKTOP`；
   `restart_runtime` 后子进程更换且旧进程终止；Rust 单测通过。
4. **设置页 UI**：展示 Provider 状态与当前配置；表单校验失败有提示；密钥可保存/清除；
   「保存并重启」前提示任务中断风险；重启完成自动刷新状态；数据目录路径可见且可
   在 Finder 打开。oxlint 与 tsc 通过。
5. 完整 `make check` 与 `make check-desktop` 各通过一次。
6. 真机验证：经 POST 端点写入真实模型配置（固定 `env:MOBILE_AGENT_MODEL_SECRET_DESKTOP`
   引用），注入密钥重启 Runtime 后 `GET` 显示生效且 status 为 configured；执行
   `settings.display-brightness.v1` 成功，证明真实模型经新配置面可用。

## 验收记录

验收日期：2026-08-20，真机 `adb:A6TG025A13002156`（荣耀 BKQ_AN10，Android 16）。

1. **GET 配置**：✅ `runtime/tests/test_model_provider_settings_api.py` 覆盖默认值/env_override；
   真机 Runtime 上 `GET /v1/model-provider/config`（无 token）返回完整非敏感视图，
   含 config_file 与 env_override=false。
2. **POST 配置**：✅ 无 token 真机实测 401；非法 ref（`sk-plain-value`）实测 400；
   单元/API 测试覆盖坏 URL、timeout 越界、enabled 缺字段、未知字段、缺 enabled 共 8 类 400；
   合法写入真机实测 `saved:true` + `restart_required:true`，文件权限实测 `600`，
   `grep -c "sk-"` 为 0（密钥值未落盘）。
3. **sidecar 密钥**：✅ Rust 单测 +4（argv 构造、密钥校验、data_dir 优先级、POST 白名单），
   共 21 例通过；真实 Keychain 按 `keychain_set_args` 相同 argv 写入
   `dev.thumbagent.desktop.model-secret`/`model-api-key` 成功，lookup 成功。
4. **设置页 UI**：✅ oxlint 0 警告、tsc 通过；表单校验（timeout 范围、启用必填、密钥前置）、
   中断确认对话框、env_override 提示、Finder 入口均实现。
5. **门禁**：✅ `make check`（402 测试）与 `make check-desktop`（lint/tsc/fmt/clippy/21 Rust 测试）
   各通过一次。
6. **真机验证**：✅ 经 POST 端点写入真实硅基流动配置（`env:MOBILE_AGENT_MODEL_SECRET_DESKTOP`），
   注入密钥重启后 status 为 `active`；`settings.display-brightness.v1` 场景
   execution=succeeded、rounds=1、evaluation passed=true
   （`local/eval-0051/results-iter54-display.json`）。
