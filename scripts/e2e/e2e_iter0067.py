"""真机 E2E：ITER-0067 真实 App 搜索并带回答案（device_e2e，不进 make check）。

目标：模型在夸克中搜索并 finish 带回 answer。京东因登录墙 / FLAG_SECURE 不是
本迭代必过项。验收：succeeded + planner_finish + 非空 answer；价格对错由人工核对。

用法（仓库根目录，需 local/model-provider.json）：
  MOBILE_AGENT_MODEL_SECRET_LOCAL=local PYTHONPATH=runtime \\
    python3.11 scripts/e2e/e2e_iter0067.py
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
GOAL = "打开夸克浏览器，搜索 iPhone 17 价格，把找到的价格带回来"


async def main() -> int:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = OUTPUT_DIR / f"iter0067-{stamp}"
    artifacts = ArtifactStore(out_dir / "artifacts")

    settings = load_model_provider_settings(MODEL_CONFIG)
    if not settings.enabled:
        print(f"FAIL: 模型未启用，检查 {MODEL_CONFIG}")
        return 1
    planner = build_planner_from_settings(settings, EnvironmentSecretResolver())
    print(f"[0] 模型: {settings.model} @ {settings.base_url} (format={settings.response_format})")

    adapter = AndroidDeviceAdapter(AdbRunner())
    runtime = RuntimeService(adapter, artifacts, planner=planner)
    devices = await runtime.list_devices()
    if not devices:
        print("FAIL: 无在线设备")
        return 1
    device_id = devices[0]["device_id"]
    print(f"[1] 设备: {device_id} model={devices[0]['model']}")
    print(f"    goal: {GOAL}")

    await adapter.press_home(device_id)
    await asyncio.sleep(1.0)

    started = datetime.now()
    task = await runtime.run_agent_task(
        device_id,
        GOAL,
        confirmed=True,
        max_rounds=12,
        acceptance=None,
        deadline_seconds=900.0,
    )
    elapsed = (datetime.now() - started).total_seconds()
    print(f"[2] 终态: {task['status']} ({elapsed:.0f}s)")
    print(f"    completion_source: {task.get('completion_source')}")
    result_payload = task.get("result")
    answer = result_payload.get("answer") if isinstance(result_payload, dict) else None
    if answer:
        print(f"    answer: {answer}")
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

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "task-report.json").write_text(
        json.dumps(task, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n产物: {out_dir}")
    ok = (
        task["status"] == "succeeded"
        and task.get("completion_source") == "planner_finish"
        and isinstance(answer, str)
        and bool(answer.strip())
    )
    await adapter.press_home(device_id)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
