"""真机 E2E：处理京东更新弹窗，推进到首页并找搜索入口（device_e2e，探索性场景）。

策略固定（非模型循环）：观察 → 若前台是 InstallApkActivity 则点「取消」→
再观察 → 输出首页交互节点与搜索入口候选。所有坐标来自 UI Tree bounds，
不做任何硬编码像素假设。
注意：强依赖京东 App 版本与弹窗形态，属于探索性场景而非稳定验收。
前置与恢复约束见 scripts/e2e/README.md。产物写入 e2e-output/（不入库）。
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "runtime"))

from mobile_agent.devices.adapters.android import AdbRunner, AndroidDeviceAdapter
from mobile_agent.evidence.artifacts import ArtifactStore
from mobile_agent.runtime import RuntimeService

OUTPUT_DIR = Path(__file__).resolve().parents[2] / "e2e-output"
BOUNDS_RE = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")


def _nodes(xml_bytes: bytes) -> list[ET.Element]:
    return list(ET.fromstring(xml_bytes).iter("node"))


def _center(bounds: str) -> tuple[int, int]:
    match = BOUNDS_RE.fullmatch(bounds or "")
    if not match:
        raise ValueError(f"bad bounds: {bounds}")
    x1, y1, x2, y2 = (int(g) for g in match.groups())
    return (x1 + x2) // 2, (y1 + y2) // 2


async def _observe_nodes(runtime, artifacts, device_id):
    obs = await runtime.observe(device_id)
    ui_path = artifacts.resolve(obs["ui_tree"]["artifact"]["relative_path"])
    return obs, _nodes(ui_path.read_bytes())


async def main() -> int:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    artifacts = ArtifactStore(OUTPUT_DIR / stamp / "artifacts")
    runtime = RuntimeService(AndroidDeviceAdapter(AdbRunner()), artifacts)
    devices = await runtime.list_devices()
    device_id = devices[0]["device_id"]

    obs, nodes = await _observe_nodes(runtime, artifacts, device_id)
    fg = obs["foreground_app"]
    print(f"[1] 前台: {fg['app_id']} {fg['activity']}")

    if "InstallApkActivity" in fg["activity"]:
        cancel = next(
            (n for n in nodes if (n.get("text") or "") == "取消"), None
        )
        if cancel is None:
            print("FAIL: 更新页找不到取消按钮")
            return 1
        x, y = _center(cancel.get("bounds"))
        print(f"[2] 点「取消」({x},{y})，跳过自更新（绝不点立即体验）")
        result = await runtime.invoke_tool(
            "input.tap", device_id, {"x": x, "y": y}, confirmed=True
        )
        print(f"    tap: status={result['status']}")
        await asyncio.sleep(3.0)
        obs, nodes = await _observe_nodes(runtime, artifacts, device_id)
        fg = obs["foreground_app"]
        print(f"[3] 弹窗处理后台面前台: {fg['app_id']} {fg['activity']}")

    summary = []
    for n in nodes:
        text = (n.get("text") or "").strip()
        desc = (n.get("content-desc") or "").strip()
        cls = (n.get("class") or "").rsplit(".", 1)[-1]
        rid = (n.get("resource-id") or "").split("/")[-1]
        if not (n.get("clickable") == "true" or text or desc or "EditText" in cls):
            continue
        summary.append(
            {"text": text[:30], "desc": desc[:30], "rid": rid,
             "class": cls, "bounds": n.get("bounds"),
             "clickable": n.get("clickable") == "true"}
        )
    out = OUTPUT_DIR / stamp / "home-nodes.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[4] 首页交互节点 {len(summary)} 个 -> {out}")
    search_related = [
        s for s in summary
        if any(k in (s["text"] + s["desc"] + s["rid"]) for k in ("搜索", "search", "Search"))
    ]
    print(f"[5] 搜索入口候选: {json.dumps(search_related, ensure_ascii=False, indent=2)}")
    print(f"\n产物目录: {OUTPUT_DIR / stamp}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
