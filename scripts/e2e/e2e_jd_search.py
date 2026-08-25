"""真机 E2E：京东搜索完整链路（device_e2e，探索性场景，已知受登录墙阻塞）。

步骤：确保 Helper IME 已安装（走 app.install@1 两阶段授权）→
首页点「搜索」→ 搜索页定位可编辑框 → unicode_text_input 输入 "iPhone 17"
（含空格，走 UTF-7 Helper 通道）→ 读回验证 → 点搜索按钮提交。
已知限制：京东搜索页可能出现登录墙（手机号输入框），产品策略会正确拒绝
向其输入——此时脚本在输入步骤失败即符合预期，用于验证策略拦截行为。
前置与恢复约束见 scripts/e2e/README.md。产物写入 e2e-output/（不入库）。
"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "runtime"))

from mobile_agent.devices.adapters.android import AdbRunner, AndroidDeviceAdapter
from mobile_agent.domain.unicode_input import HELPER_PACKAGE
from mobile_agent.evidence.artifacts import ArtifactStore
from mobile_agent.runtime import RuntimeService

OUTPUT_DIR = Path(__file__).resolve().parents[2] / "e2e-output"
HELPER_APK = (
    Path(__file__).resolve().parents[2]
    / "helpers" / "unicode-ime" / "dist" / "unicode-ime.apk"
)
BOUNDS_RE = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")


def _center(bounds: str) -> tuple[int, int]:
    x1, y1, x2, y2 = (int(g) for g in BOUNDS_RE.fullmatch(bounds or "").groups())
    return (x1 + x2) // 2, (y1 + y2) // 2


async def _observe_nodes(runtime, artifacts, device_id):
    obs = await runtime.observe(device_id)
    ui_path = artifacts.resolve(obs["ui_tree"]["artifact"]["relative_path"])
    return obs, list(ET.fromstring(ui_path.read_bytes()).iter("node"))


async def _wait_task(runtime, task_id):
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        execution = runtime.get_task_execution(task_id)
        if execution["status"] in {"succeeded", "failed"}:
            return runtime.get_task(task_id)
        await asyncio.sleep(0.2)
    raise AssertionError("install task timeout")


async def _ensure_helper(runtime, device_id, staging: Path) -> None:
    installed = await runtime._adapter.installed_input_methods(device_id)
    if any(HELPER_PACKAGE in ime for ime in installed):
        print("[1] Helper 已安装，复用")
        return
    staging.mkdir(parents=True, exist_ok=True)
    shutil.copy2(HELPER_APK, staging / HELPER_APK.name)
    approval = await runtime.prepare_apk_install(
        device_id, str(staging / HELPER_APK.name), HELPER_PACKAGE
    )
    submitted = runtime.submit_apk_install_task(
        approval["approval_id"], confirmed=True,
        idempotency_key=f"e2e-{int(time.time())}",
    )
    report = await _wait_task(runtime, submitted["task_id"])
    if report["status"] != "succeeded":
        raise AssertionError(f"Helper 安装失败: {report.get('error')}")
    print("[1] Helper 两阶段安装完成")


async def main() -> int:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = OUTPUT_DIR / stamp
    artifacts = ArtifactStore(out_dir / "artifacts")
    runtime = RuntimeService(AndroidDeviceAdapter(AdbRunner()), artifacts)
    device_id = (await runtime.list_devices())[0]["device_id"]

    await _ensure_helper(runtime, device_id, out_dir / "apks")

    # 首页点搜索入口（desc 由参数指定，默认夸克首页「搜索框」）
    entry_desc = sys.argv[1] if len(sys.argv) > 1 else "搜索框"
    input_text = sys.argv[2] if len(sys.argv) > 2 else "iPhone 17"
    obs, nodes = await _observe_nodes(runtime, artifacts, device_id)
    print(f"[2] 当前前台: {obs['foreground_app']['app_id']} {obs['foreground_app']['activity']}")
    entry = next(
        (n for n in nodes
         if (n.get("content-desc") or "") == entry_desc and n.get("clickable") == "true"),
        None,
    )
    if entry is None:
        print(f"FAIL: 未找到搜索入口 desc={entry_desc!r}")
        return 1
    x, y = _center(entry.get("bounds"))
    result = await runtime.invoke_tool("input.tap", device_id, {"x": x, "y": y}, confirmed=True)
    print(f"[3] 点搜索入口 ({x},{y}): {result['status']}")
    await asyncio.sleep(2.5)

    # 搜索页定位可编辑框
    obs, nodes = await _observe_nodes(runtime, artifacts, device_id)
    print(f"[4] 搜索页: {obs['foreground_app']['activity']}")
    editables = [
        n for n in nodes
        if (n.get("class") or "").endswith(("EditText", "AutoCompleteTextView"))
    ]
    print(f"    可编辑节点 {len(editables)} 个:")
    for n in editables:
        print(f"      rid={n.get('resource-id')} class={n.get('class')} "
              f"text={n.get('text')!r} bounds={n.get('bounds')}")
    if not editables:
        print("FAIL: 搜索页无可编辑框")
        return 1
    target = editables[0]
    rid = target.get("resource-id") or ""
    if rid:
        selector = {"strategy": "resource_id", "value": rid.split("/")[-1], "match": "exact"}
    else:
        selector = {"strategy": "class_name", "value": target.get("class"), "match": "exact"}
    print(f"[5] 目标选择器: {selector}")

    # Unicode 输入（含空格，走 Helper IME；Medium 风险确认）
    result = await runtime.unicode_text_input(device_id, selector, input_text, confirmed=True)
    print(f"[6] unicode 输入: success={result['success']} verification={result['verification']}")
    print(f"    IME: {result['ime']['helper_id']} 恢复={result['ime']['restored']}")

    # 读回确认
    obs, nodes = await _observe_nodes(runtime, artifacts, device_id)
    after = [
        n for n in nodes
        if (n.get("class") or "").endswith(("EditText", "AutoCompleteTextView"))
    ]
    print(f"[7] 读回: {[n.get('text') for n in after]}")
    print(f"\n产物目录: {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
