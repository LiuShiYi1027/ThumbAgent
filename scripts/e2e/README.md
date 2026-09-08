# 真机 E2E 套件（device_e2e）

本目录是显式标记的真实设备 E2E 场景集，对应 `docs/engineering/testing.md`
第 5 节的 `device_e2e` marker 约定。**不进默认快速测试集**，`make check`
不会运行这里的任何脚本；CI 使用独立受控流水线执行。

## 运行前提

- 已授权的真机在线（`adb devices` 可见，USB 调试已授权）。
- 除特别说明外，脚本只通过 RuntimeService 的登记 Tool 动作，不直接拼 ADB 命令。
- 涉及 unicode 输入的场景要求 Helper IME 已安装（`e2e_iter0059.py` 场景 6
  会验证卸载还原，因此套件跑完后 helper 处于未安装状态，属预期）。

### Helper IME 多 ROM 安装步骤（unicode 场景前置）

1. `adb install -r helpers/unicode-ime/dist/unicode-ime.apk`
2. **ROM 差异**：ColorOS（OnePlus/OPPO）会弹出人工安装确认页
   （`InstallGuideActivity`），必须在设备屏幕上手动确认，`adb install` 才会
   返回；MagicOS（荣耀）无此步骤。该确认是系统安全边界，不要试图绕过。
3. 启用：`adb shell ime enable com.thumbagent.unicodeime/.UnicodeImeService`
   （注意组件名是 `.UnicodeImeService`，不是 `.UnicodeIme`）。
4. 验证：`adb shell ime list -s | grep thumbagent` 有输出即可。

## 场景清单

| 脚本 | 类型 | 场景 | 主要前置 | 设备状态恢复 |
| --- | --- | --- | --- | --- |
| `e2e_iter0059.py` | 稳定验收 | Helper IME unicode 输入六场景（登记摘要、两阶段安装、确认拦截、敏感数字拦截、中文输入、卸载还原） | 真机在线 | 脚本内卸载 helper 还原 |
| `e2e_settings_unicode_input.py` | 稳定验收 | 设置搜索框 unicode 输入回归：空格短块 / 孤立单字符 / 纯 CJK | Helper IME 已安装启用 | 结束清空字段、退出搜索页、IME 由工具自身恢复 |
| `e2e_device_recon.py` | 稳定验收 | 设备检查 + 启动目标 App + Observation 原语（默认京东，可传包名） | 目标 App 已安装 | 无写动作 |
| `e2e_saucedemo_login_unicode.py` | 稳定验收 | SauceDemo fixture 应用登录表单 unicode 输入 | 已装 `com.saucelabs.mydemoapp.android`、Helper IME | IME 由工具自身恢复 |
| `e2e_dialog_handling.py` | 探索性 | 京东更新弹窗处理（只点「取消」，绝不点「立即体验」） | 京东已安装；弹窗形态随版本变化 | 无残留写动作 |
| `e2e_jd_search.py` | 探索性 | 京东搜索「iPhone 17」完整链路 | 京东已安装；**已知受登录墙阻塞**，策略拒绝向手机号框输入即符合预期 | Helper 复用不卸载 |
| `e2e_live_agent_settings.py` | 稳定验收 | 真实模型 Agent 主链路：自然语言目标 → 模型规划 → 设备动作 → Runtime 终态验证 | `local/model-provider.json`（gitignored）+ 密钥环境变量；默认中文目标（中文 ROM），`--en` 走捷径英文目标，`--battery` 强制模型循环；`--rounds`/`--deadline` 可调预算 | 无残留写动作 |
| `e2e_live_agent_answer_about.py` | 稳定验收 | Agent 内核 answer 带回确定性场景（关于手机 → 型号），同时是捷径谓词守卫的活体探针 | 同上模型配置 | 无残留写动作 |

「稳定验收」场景应与代码同步维护，失败视为回归；「探索性」场景依赖
特定商业 App 版本，失败先核对 App 改版，不直接视为产品回归。

## 运行方式

```bash
# 单场景（仓库根目录）
python3 scripts/e2e/e2e_settings_unicode_input.py

# 京东链路可指定入口描述与输入文本
python3 scripts/e2e/e2e_jd_search.py 搜索框 "iPhone 17"
```

退出码 0 为通过，非 0 为失败；产物（截图、UI Tree、节点摘要）写入
`e2e-output/<时间戳>/`，该目录已 gitignore，不入库。

## 恢复与安全约束

- 脚本结束后必须恢复可恢复状态（输入法、字段内容、页面层级），
  禁止清除用户数据（testing.md §5）。
- 高风险动作（APK 安装）只走 `app.install@1` 两阶段授权链路。
- 永远不点「立即体验/同意协议/授权登录」一类按钮；遇到协议页或
  登录墙，记录并停止，由人决策。
