"""真机 E2E：真实模型驱动的 Agent 主链路狗食（device_e2e，稳定验收候选）。

目标：验证「自然语言意图 → 模型规划 → 设备动作 → Runtime 终态验证」完整链路。
模型来自 local/model-provider.json（gitignored；当前指向 LM Studio 本地服务，
response_format=text）。无真实模型配置时脚本直接报错退出，不会静默降级。

场景：让 Agent 打开显示设置页面。验收由 Runtime 持有（非模型自评）：
前台为系统设置 且 页面存在「显示」语义节点。
产物写入 e2e-output/（不入库）。
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "runtime"))

from mobile_agent.devices.adapters.android import AdbRunner, AndroidDeviceAdapter
from mobile_agent.evidence.artifacts import ArtifactStore
from mobile_agent.providers.config import (
    EnvironmentSecretResolver,
    build_planner_from_settings,
    load_model_provider_settings,
)
from mobile_agent.runtime import RuntimeService

OUTPUT_DIR = Path(__file__).resolve().parents[2] / "e2e-output"
MODEL_CONFIG = Path(__file__).resolve().parents[2] / "local" / "model-provider.json"
GOAL = "打开手机的显示设置页面"
ACCEPTANCE = {
    "foreground_app_id": "com.android.settings",
    "expected_selector": {"strategy": "text", "value": "显示", "match": "contains"},
}
# 英文 ROM（如默认 locale 的模拟器）：python3 .../e2e_live_agent_settings.py --en
EN_GOAL = "Open the Display settings page"
EN_ACCEPTANCE = {
    "foreground_app_id": "com.android.settings",
    "expected_selector": {"strategy": "text", "value": "Display", "match": "contains"},
}
# 强制走模型循环（绕开导航捷径词表）的 GUI 任务：设置里找 Battery 并进入。
# 验收用页面内唯一的精确文本（"Battery" contains 会命中多个节点导致 TARGET_AMBIGUOUS）。
EN_BATTERY_GOAL = "In Settings, find and open the Battery page"
EN_BATTERY_ACCEPTANCE = {
    "foreground_app_id": "com.android.settings",
    "expected_selector": {"strategy": "text", "value": "Battery usage", "match": "exact"},
}
# 中文模型循环 + unicode 输入组合：夸克搜索「你好」。考模型规划（启动/找框）
# 与 input.unicode_text skill（Helper IME 切换、读回验证、IME 恢复）。
QUARK_GOAL = "打开夸克浏览器，在搜索框里输入你好"
# 验收必须锁定输入框本身：夸克搜索页有大量含「你好」的热搜推荐词
#（真机实测 text+contains 命中 9 个节点 → TARGET_AMBIGUOUS）。
# exact + clickable 只命中输入后的 EditText（推荐词 TextView 均 clickable=false）。
QUARK_ACCEPTANCE = {
    "foreground_app_id": "com.quark.browser",
    "expected_selector": {
        "strategy": "text",
        "value": "你好",
        "match": "exact",
        "clickable": True,
    },
}
# Agent 内核（scratchpad + answer）驱动场景（ITER-0061）：京东搜索 iPhone 17 并
# 带回价格。验收只断言前台到达京东（UI 状态）；answer 正确性由人工核对报告，
# 不做数据自动断言（V1 语义，见迭代 plan）。
JD_GOAL = "打开京东，搜索 iPhone 17，把 iPhone 17 的价格带回来"
# 带回答案类场景必须 acceptance=None：前台/UI 断言会在 run_skill 成功后短路任务
# （runtime_acceptance 提前判完成），模型来不及 finish 携带 answer。
# 完成判定改由 planner_finish（模型 finish 携带 expected_selector + answer），
# answer 正确性由人工核对报告（V1 不做数据自动断言，见 ITER-0061 plan）。
JD_ACCEPTANCE = None
# 内核等价替代场景：夸克搜索「iPhone 17 价格」并带回答案。京东搜索结果页
# （ProductListActivity）在部分 ROM 上使 uiautomator dump 持续返回空（实测
# 小米 2509FPN0BC），内核验收改用页面结构更简单的夸克；京东场景保留待
# Observation 健壮性跟进（见 ITER-0061 复盘）。
QUARK_PRICE_GOAL = "打开夸克浏览器，搜索 iPhone 17 价格，把找到的价格带回来"
QUARK_PRICE_ACCEPTANCE = None


def _arg_value(flag: str, default: str) -> str:
    return (
        sys.argv[sys.argv.index(flag) + 1]
        if flag in sys.argv and sys.argv.index(flag) + 1 < len(sys.argv)
        else default
    )


async def main() -> int:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = OUTPUT_DIR / stamp
    artifacts = ArtifactStore(out_dir / "artifacts")

    settings = load_model_provider_settings(MODEL_CONFIG)
    if not settings.enabled:
        print(f"FAIL: 模型未启用，检查 {MODEL_CONFIG}")
        return 1
    planner = build_planner_from_settings(settings, EnvironmentSecretResolver())
    print(f"[0] 模型: {settings.model} @ {settings.base_url} (format={settings.response_format})")

    runtime = RuntimeService(
        AndroidDeviceAdapter(AdbRunner()), artifacts, planner=planner
    )
    devices = await runtime.list_devices()
    if not devices:
        print("FAIL: 无在线设备")
        return 1
    wanted = _arg_value("--device", "")
    if wanted:
        match = next(
            (d for d in devices if wanted in d["device_id"]), None
        )
        if match is None:
            print(f"FAIL: 找不到设备 {wanted!r}，在线: {[d['device_id'] for d in devices]}")
            return 1
        device_id = match["device_id"]
    else:
        device_id = devices[0]["device_id"]
    print(f"[1] 设备: {device_id}")

    started = datetime.now()
    if "--jd" in sys.argv:
        goal, acceptance = JD_GOAL, JD_ACCEPTANCE
    elif "--quark-price" in sys.argv:
        goal, acceptance = QUARK_PRICE_GOAL, QUARK_PRICE_ACCEPTANCE
    elif "--quark" in sys.argv:
        goal, acceptance = QUARK_GOAL, QUARK_ACCEPTANCE
    elif "--battery" in sys.argv:
        goal, acceptance = EN_BATTERY_GOAL, EN_BATTERY_ACCEPTANCE
    elif "--en" in sys.argv:
        goal, acceptance = EN_GOAL, EN_ACCEPTANCE
    else:
        goal, acceptance = GOAL, ACCEPTANCE
    print(f"    goal: {goal}")
    task = await runtime.run_agent_task(
        device_id,
        goal,
        confirmed=True,
        max_rounds=int(_arg_value("--rounds", "6")),
        acceptance=acceptance,
        deadline_seconds=float(_arg_value("--deadline", "600")),
    )
    elapsed = (datetime.now() - started).total_seconds()

    print(f"[2] 终态: {task['status']} ({elapsed:.0f}s)")
    result_payload = task.get("result")
    if isinstance(result_payload, dict) and result_payload.get("answer"):
        print(f"    answer: {result_payload['answer']}")
    if task.get("error"):
        print(f"    error: {task['error'].get('code')} {task['error'].get('message')}")
    for step in task.get("steps", []):
        result = step.get("result") or {}
        decision = result.get("decision") or {}
        error = step.get("error") or {}
        line = (
            f"    round {result.get('round', step.get('sequence'))}: "
            f"{decision.get('decision_type')} "
            f"{decision.get('tool_id') or decision.get('skill_id') or step.get('name')} "
            f"latency={decision.get('provider_latency_ms')}ms -> {step.get('status')}"
        )
        if error:
            line += f" ({error.get('code')})"
        print(line)

    report_path = out_dir / "task-report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(task, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n产物目录: {out_dir}")
    return 0 if task["status"] == "succeeded" else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
