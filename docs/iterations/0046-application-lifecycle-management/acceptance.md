# ITER-0046 Acceptance

> 文档状态：Final
> 迭代状态：Completed
> 更新日期：2026-07-26

- [x] 状态检查只读返回安装状态、进程存在、前台和 stopped flag，不返回进程 ID 或原始平台输出。
- [x] 启动异步执行并验证目标应用进入前台。
- [x] 强制停止要求明确确认、拒绝系统应用，并验证目标应用非前台且进程不存在。
- [x] 清除数据 Prepare 零设备写动作并展示包名、版本、数据删除影响、Approval ID 和过期时间。
- [x] 清除数据只接受 claim 后的范围绑定 Approval，拒绝系统应用、过期和跨请求复用。
- [x] 清除后验证应用仍安装、非前台、进程不存在，并记录平台清除成功。
- [x] 超时或断连使用 unknown outcome，停止与清除数据均不自动重试。
- [x] REST/MCP 不暴露 Shell、任意 ADB 参数、系统应用绕过或批量操作。
- [x] focused tests 与最终 `make check` 通过。
- [x] 真机完成状态 → 启动 → 停止 → clear prepare → 独立确认 → clear → report 集中验收。
