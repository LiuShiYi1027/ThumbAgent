# ThumbAgent

> Local-first platform that gives AI agents a real thumb on mobile devices.
> 本地优先的移动设备 Skills 平台——给 AI 一只真正的「拇指」。

[![CI](https://github.com/LiuShiYi1027/ThumbAgent/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/LiuShiYi1027/ThumbAgent/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/LiuShiYi1027/ThumbAgent)](https://github.com/LiuShiYi1027/ThumbAgent/releases/latest)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](./LICENSE)
[![Platform](https://img.shields.io/badge/platform-macOS%20%C2%B7%20Android-black)]()

中文 | [English](./README.en.md)

---

用自然语言描述目标，ThumbAgent 的 Agent 在真实 Android 设备上自主完成
「观察 → 规划 → 操作 → 验证 → 恢复」的完整闭环，并产出可复现、可审计的执行报告：

```text
自然语言目标
    → 任务规划（LLM Planner）
    → 设备操作（经 Schema / Capability / Policy 三重校验）
    → 状态观察（截图 + UI Tree）
    → 结果验证与异常恢复
    → 日志、性能和截图等现场采集
    → 可复现、可审计的执行报告
```

所有数据留在本地：无云端账号、无遥测、密钥只进系统钥匙串。

![ThumbAgent 桌面工作台](./docs/assets/desktop-home.png)

## 快速开始

### 方式一：下载安装包（推荐）

从 [Releases](https://github.com/LiuShiYi1027/ThumbAgent/releases/latest) 下载
`ThumbAgent_x.x.x_aarch64.dmg`（macOS Apple Silicon，已签名 + 公证），拖入「应用程序」。

首次启动后在**设置页**填写模型 Provider（Base URL / 模型名称 / API Key）即可开始。
API Key 只存入 macOS 钥匙串，永不落盘。

**前提**：一台开启 USB 调试的 Android 设备 + 本机已安装 ADB。

### 方式二：从源码运行

```bash
git clone https://github.com/LiuShiYi1027/ThumbAgent.git
cd ThumbAgent

make check          # Python 门禁：lint / typecheck / 测试 / Contract 检查
make run            # 启动 Runtime（默认 127.0.0.1:8765）

cd apps/desktop
npm install
npm run tauri dev   # 桌面工作台
```

要求 Python 3.11+、Node 20+、Rust stable、ADB。

## 核心能力

- **自然语言任务**：桌面工作台输入目标，Agent 多轮决策自主执行
- **真实设备闭环**：设备发现、画面观察、点击/滑动/输入等基础动作、完成验证、瞬时故障有界重试
- **执行时间线与报告**：逐轮截图、决策、动作与结果完整留痕，随时回看
- **人工接管**：执行中在安全边界暂停 Agent，人工操作设备后恢复续跑，接管区间计入事件流
- **诊断证据**：脱敏日志、聚合性能快照、性能对比、一键诊断证据包（带 SHA-256 清单的本地 ZIP）
- **数据治理**：本地 Artifact 留存策略 + 两阶段授权清理
- **开放接口**：Local HTTP API + MCP Server，可接入 Codex 等外部 Agent

## 桌面工作台

Tauri 2 原生应用，mono 编辑风设计：自动拉起并认证本地 Runtime、统一就绪诊断、
设备列表与实时画面（手机框呈现）、任务提交与执行时间线、设置页开箱配置。

## 安全设计

- 所有设备动作经过 **Schema / Capability / Policy** 三层校验，绑定明确 `device_id`
- 中高风险动作默认需要**显式确认**；支付、验证码、权限绕过直接拒绝
- 无任意 Shell、无 ADB 透传、无隐藏逃生口；安装/卸载/清理均为两阶段 Approval 流程
- 模型输出一律视为不可信输入：结构化解析 + allowlist 二次校验
- 密钥、令牌只存在于系统钥匙串与进程环境，不进代码、数据库、日志

## 架构

```text
Clients / Interfaces（Desktop · CLI · MCP · Web）
        ↓
Application / Skills / Task Engine
        ↓
Domain / Policy / Contracts
        ↓
Device Gateway
        ↓
Platform Adapters（Android via ADB）
```

跨模块数据一律 Contract-first：`contracts/schemas/` 定义 Schema，再生成语言类型。
详见[架构边界](./docs/architecture/rules.md)。

## 文档

**产品**：[产品定位](./docs/product/positioning.md) · [V1 产品方案](./docs/product/solution-v1.md) · [技术设计](./docs/architecture/technical-design-v1.md)

**工程**：[开发规范](./docs/engineering/development.md) · [迭代索引](./docs/iterations/README.md) · [分发与发布](./docs/engineering/distribution.md) · [安全规范](./docs/engineering/security.md) · [ADR](./docs/adr/README.md)

**贡献**：[Agent 开发入口](./AGENTS.md) · [贡献指南](./CONTRIBUTING.md)

## 路线图

V1 聚焦单台 Android 设备的本地 AI-to-Device 闭环（已完成 v0.1.0）。
后续方向：更多设备能力、评测套件完善、iOS 适配探索。详见[迭代索引](./docs/iterations/README.md)。

## 许可证

[Apache-2.0](./LICENSE)
