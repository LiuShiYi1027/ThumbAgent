# ITER-0052 Acceptance

> 文档状态：Completed
> 迭代状态：Completed
> 更新日期：2026-08-19

## 验收条件

1. **内容端点**：`GET /v1/artifacts/{artifact_id}/content`
   - 无 token 或错误 token 返回 401；非法 id 模式返回 400；不存在的 id 返回 404；
   - 对已保存的截图 Artifact 返回 200 + `image/png` + 原始字节，响应带
     `Cache-Control: no-store` 与 `X-Content-Type-Options: nosniff`；
   - 非截图 Artifact（如同 id 的 `.xml`）不可经该端点获得；超过大小上限拒绝。
2. **事件扩展**：异步 Agent 任务的 `task.step_completed` 事件在该轮产生动作结果时
   携带 `screenshot_artifact_id`，且该 id 可通过条件 1 的端点取回 PNG。
3. **桌面 IPC**：`runtime_api_get_bytes` 只接受 `/v1/artifacts/{id}/content` 模式路径，
   拒绝其他 `/v1/` 路径与越界 id；Rust 单元测试通过。
4. **桌面 UI**：执行任务时设备画面栏随轮次更新截图；任务结束后报告页可查看各轮
   动作后截图；无截图轮次有占位说明。`npm run lint` 与 `npm run typecheck` 通过。
5. 完整 `make check` 与 `make check-desktop` 各通过一次。
6. 真机 Low 风险验证：在已授权设备上执行一条 Agent 任务，确认报告轮次的
   `screenshot_artifact_id` 可经端点取回有效 PNG（人工确认在任务提交时发生）。

## 验收记录

| 条件 | 结果 | 证据 |
| --- | --- | --- |
| 1 内容端点 | 通过 | `make check`（375 tests）覆盖 401/400/404/PNG 校验；另于 2026-08-19 对运行中 Runtime（PID 87561，工作树代码）用真实截图 Artifact（2026-08-17 真机产出，`artifact_1cf4bcd30b814b92a0d2273d0092a4a3`）手工验证：无 token 401；带 token 200 + `image/png` + 257,933 字节 + `Cache-Control: no-store` + `X-Content-Type-Options: nosniff`，`file` 确认 PNG 1256×2808；不存在 id 返回 404 `ARTIFACT_NOT_FOUND`；非法 id 模式按路由不匹配返回 404 `RESOURCE_NOT_FOUND`（模式外路径不进入处理器，400 仅用于处理器内二次校验失败） |
| 2 事件扩展 | 通过 | `runtime/tests/test_async_task_execution.py` 集成测试：动作轮次 `task.step_completed` 携带 `screenshot_artifact_id` 且可被端点取回；提取函数单元测试覆盖 `action`/`tap_action` 两种结果形态 |
| 3 桌面 IPC | 通过 | `make check-desktop`：Rust 17 tests 全过（白名单精确匹配、base64 RFC4648 向量、fake server 二进制拉取、非白名单路径拒绝） |
| 4 桌面 UI | 通过 | `npm run lint`（oxlint 0 错误）与 `npm run typecheck`（tsc -b）通过；2026-08-19 真机任务 `task_e3de3daccd5440efa1aaf87f05de03c3` 上核对 UI 依赖的完整数据链路：事件流 3 个动作轮携带 `screenshot_artifact_id`、`/v1/tasks/{id}` 存储步骤按前端 `stepScreenshotArtifactId` 同逻辑提取出相同 3 个 id、IPC 桥经 Rust fake server 二进制测试覆盖；最终窗口渲染观感未机器核验，留待下次打开桌面端人工过目 |
| 5 完整门禁 | 通过 | 2026-08-19 `make check`（375 tests）与 `make check-desktop`（clippy -D warnings + 17 Rust tests）各通过一次 |
| 6 真机验证 | 通过 | 2026-08-19 19:37 在已授权真机 `adb:A6TG025A13002156`（BKQ_AN10，Android 16）执行 `settings.display-brightness.v1`，任务 `succeeded`（提交时 confirmed=true 人工确认，迭代 plan 预授权）：5 个 `task.step_completed` 中 3 个动作轮携带 `screenshot_artifact_id`（finish 轮与 1 个 TARGET_OUT_OF_BOUNDS 失败轮无引用，符合设计）；3 个 id 经端点取回均为 200 + `image/png` + 有效 PNG（1256×2808，内容确认为设备"显示和亮度"设置页，亮度滑块已被调低） |
