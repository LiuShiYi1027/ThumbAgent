"""真机 E2E：ITER-0066 空 UI 树观察回归（device_e2e，不进 make check）。

A. 设置页 Agent 任务（RuleBasedPlanner，无真实模型）必须 succeeded。
B. 设置页 Observation 的 locatable_node_count > 0。
C. 启动京东后分类 hierarchy：若持续空树，再跑一轮 Agent 观察路径，
   终态必须是 failed + UI_TREE_EMPTY（不是 NO_PROGRESS）。本 ROM 若京东
   首页有可定位节点，C 记为未复现，不以 Fake 宣称真机空树通过。

用法（仓库根目录）：
  PYTHONPATH=runtime python3.11 scripts/e2e/e2e_iter0066.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "runtime"))

from mobile_agent.devices.adapters.android import AdbRunner, AndroidDeviceAdapter
from mobile_agent.devices.adapters.android.parser import extract_ui_xml
from mobile_agent.domain.errors import MobileAgentError
from mobile_agent.evidence.artifacts import ArtifactStore
from mobile_agent.runtime import RuntimeService
from mobile_agent.ui.hierarchy import locatable_node_count, semantic_candidate_count
from mobile_agent.ui.parser import UiHierarchyParser

OUTPUT_DIR = Path(__file__).resolve().parents[2] / "e2e-output"
JD_APP_ID = "com.jingdong.app.mall"
GOAL = "进入显示和亮度页面"
ACCEPTANCE = {
    "foreground_app_id": "com.android.settings",
    "expected_selector": {"strategy": "text", "value": "显示", "match": "contains"},
}


def _classify(xml_bytes: bytes) -> dict[str, int | bool]:
    nodes = UiHierarchyParser().parse(xml_bytes)
    locatable = locatable_node_count(nodes)
    return {
        "node_count": len(nodes),
        "semantic_candidate_count": semantic_candidate_count(nodes),
        "locatable_node_count": locatable,
        "empty": locatable == 0,
    }


async def _dump_classify(runner: AdbRunner, serial: str) -> dict | None:
    result = await runner.run("-s", serial, "exec-out", "uiautomator", "dump", "/dev/tty")
    xml = extract_ui_xml(result.stdout)
    if not xml:
        return None
    return _classify(xml)


async def _observe_with_retries(
    runtime: RuntimeService, device_id: str, attempts: int = 2, delay: float = 2.0
) -> dict:
    last: MobileAgentError | None = None
    for attempt in range(1, attempts + 1):
        try:
            return await runtime.observe(device_id)
        except MobileAgentError as exc:
            last = exc
            print(f"    observe {attempt}/{attempts}: {exc.code} {exc.message}")
            if attempt < attempts:
                await asyncio.sleep(delay)
    assert last is not None
    raise last


async def main() -> int:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = OUTPUT_DIR / f"iter0066-{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    artifacts = ArtifactStore(out_dir / "artifacts")
    runner = AdbRunner()
    adapter = AndroidDeviceAdapter(runner)
    runtime = RuntimeService(adapter, artifacts)

    devices = await runtime.list_devices()
    if not devices:
        print("FAIL: 无在线设备")
        return 1
    device_id = devices[0]["device_id"]
    serial = device_id.removeprefix("adb:")
    print(f"[0] 设备: {device_id} model={devices[0]['model']} os={devices[0]['os_version']}")
    print("[pre] 回到桌面，避开 FLAG_SECURE 页")
    await adapter.press_home(device_id)
    await asyncio.sleep(1.5)

    print(f"[A] 设置页任务: {GOAL}")
    started = datetime.now()
    task = await runtime.run_agent_task(
        device_id,
        GOAL,
        confirmed=True,
        max_rounds=8,
        acceptance=ACCEPTANCE,
        deadline_seconds=180.0,
    )
    elapsed = (datetime.now() - started).total_seconds()
    status = task["status"]
    error = task.get("error") or {}
    print(f"    终态: {status} ({elapsed:.0f}s) source={task.get('completion_source')}")
    if error:
        print(f"    error: {error.get('code')} {error.get('message')}")
    (out_dir / "settings-task.json").write_text(
        json.dumps(task, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if status != "succeeded":
        print("FAIL: 设置页任务未成功")
        return 1

    obs = await runtime.observe(device_id)
    ui_path = artifacts.resolve(obs["ui_tree"]["artifact"]["relative_path"])
    settings_cls = _classify(ui_path.read_bytes())
    print(f"[B] 设置页 hierarchy: {settings_cls}")
    if settings_cls["empty"]:
        print("FAIL: 设置页被误判为空树")
        return 1

    jd_fg: dict | None = None
    jd_cls: dict | None = None
    jd_dump_cls: dict | None = None
    empty_tree_result = "not_reproduced"
    try:
        print(f"[C] 启动 {JD_APP_ID} 并分类 Observation")
        await adapter.launch_app(device_id, JD_APP_ID)
        await asyncio.sleep(5.0)
        try:
            jd_obs = await _observe_with_retries(runtime, device_id, attempts=2)
        except MobileAgentError as exc:
            dump_cls = await _dump_classify(runner, serial)
            jd_dump_cls = dump_cls
            empty_tree_result = "jd_observe_failed"
            print(f"    京东观察失败（不阻断设置页回归）: {exc.code} {exc.message}")
            print(f"    dump 分类: {dump_cls}")
            (out_dir / "jd-classify.json").write_text(
                json.dumps(
                    {
                        "error": {"code": exc.code, "message": exc.message},
                        "dump_classify": dump_cls,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        else:
            jd_fg = jd_obs["foreground_app"]
            jd_path = artifacts.resolve(jd_obs["ui_tree"]["artifact"]["relative_path"])
            jd_cls = _classify(jd_path.read_bytes())
            print(f"    前台: {jd_fg['app_id']} {jd_fg['activity']}")
            print(f"    hierarchy: {jd_cls}")
            (out_dir / "jd-classify.json").write_text(
                json.dumps(
                    {"foreground": jd_fg, "classify": jd_cls},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            if jd_cls["empty"]:
                print("    京东页为空树，走 Agent 观察路径验收 UI_TREE_EMPTY")
                empty_task = await runtime.run_agent_task(
                    device_id,
                    GOAL,
                    confirmed=True,
                    max_rounds=3,
                    deadline_seconds=60.0,
                )
                empty_error = empty_task.get("error") or {}
                print(f"    终态: {empty_task['status']} code={empty_error.get('code')}")
                (out_dir / "empty-tree-task.json").write_text(
                    json.dumps(empty_task, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                if (
                    empty_task["status"] != "failed"
                    or empty_error.get("code") != "UI_TREE_EMPTY"
                ):
                    print("FAIL: 空树未以 UI_TREE_EMPTY 失败")
                    return 1
                empty_tree_result = "ui_tree_empty"
    finally:
        await adapter.press_home(device_id)

    summary = {
        "device_id": device_id,
        "model": devices[0]["model"],
        "settings_status": status,
        "settings_classify": settings_cls,
        "jd_foreground": jd_fg,
        "jd_classify": jd_cls,
        "jd_dump_classify": jd_dump_cls,
        "empty_tree_result": empty_tree_result,
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n产物: {out_dir}")
    print(f"empty_tree_result={empty_tree_result}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
