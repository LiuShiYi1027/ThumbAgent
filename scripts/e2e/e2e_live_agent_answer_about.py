"""真机 E2E：answer 带回最小确定性场景（device_e2e，ITER-0061 验收补证）。

目标：模型经「关于手机」页面观察设备型号并 finish 带回 answer。
选择「关于手机」的原因：内容确定（ro.product.model 可读回人工核对），且目标含
结果类谓词「带回来」——同时活体验证 M6 修复（导航捷径必须让位给模型循环，
不能因为命中「关于手机」关键词就在第 0 轮秒成功而无 answer）。

验收由人工核对：任务 succeeded、completion_source=planner_finish（非
runtime_shortcut）、TaskRun.result.answer 包含设备型号。

用法：MOBILE_AGENT_MODEL_SECRET_LOCAL=local python3.11 scripts/e2e/e2e_live_agent_answer_about.py
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
GOAL = "打开关于手机页面，把设备型号带回来"


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
    device_id = devices[0]["device_id"]
    print(f"[1] 设备: {device_id}")

    started = datetime.now()
    task = await runtime.run_agent_task(
        device_id,
        GOAL,
        confirmed=True,
        max_rounds=6,
        acceptance=None,
        deadline_seconds=900.0,
    )
    elapsed = (datetime.now() - started).total_seconds()

    print(f"[2] 终态: {task['status']} ({elapsed:.0f}s)")
    print(f"    completion_source: {task.get('completion_source')}")
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

    # 人工核对辅助：设备真实型号
    answer = (result_payload or {}).get("answer") or ""
    model_ok = task["status"] == "succeeded" and task.get("completion_source") == "planner_finish"
    print(f"[3] 内核验收: completion_source=planner_finish -> {'PASS' if model_ok else 'FAIL'}")
    print(f"    answer 含型号需人工核对（adb shell getprop ro.product.model）")
    return 0 if model_ok and answer else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
