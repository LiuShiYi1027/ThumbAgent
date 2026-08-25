"""真机 E2E：基础原语在真实商业 App 上的表现（device_e2e，需已授权真机在线）。

阶段 A（无模型依赖）：设备检查 → 启动目标 App → Observation →
导出 UI Tree 交互节点摘要与截图路径，供后续输入/点击决策。
前置与恢复约束见 scripts/e2e/README.md。产物写入 e2e-output/（不入库）。
"""

from __future__ import annotations

import asyncio
import json
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "runtime"))

from mobile_agent.devices.adapters.android import AdbRunner, AndroidDeviceAdapter
from mobile_agent.evidence.artifacts import ArtifactStore
from mobile_agent.runtime import RuntimeService

OUTPUT_DIR = Path(__file__).resolve().parents[2] / "e2e-output"


def _summarize_ui_tree(xml_bytes: bytes) -> list[dict[str, object]]:
    """提取可交互节点（可点击/可编辑/带文本），保持有界输出。"""
    root = ET.fromstring(xml_bytes)
    nodes: list[dict[str, object]] = []
    for node in root.iter("node"):
        clickable = node.get("clickable") == "true"
        text = (node.get("text") or "").strip()
        desc = (node.get("content-desc") or "").strip()
        cls = node.get("class") or ""
        editable = cls.endswith("EditText") or cls.endswith("AutoCompleteTextView")
        if not (clickable or editable or text or desc):
            continue
        nodes.append(
            {
                "text": text[:40],
                "desc": desc[:40],
                "rid": (node.get("resource-id") or "").split("/")[-1],
                "class": cls.rsplit(".", 1)[-1],
                "clickable": clickable,
                "editable": editable,
                "bounds": node.get("bounds"),
            }
        )
    return nodes


async def main() -> int:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    artifacts = ArtifactStore(OUTPUT_DIR / stamp / "artifacts")
    runtime = RuntimeService(AndroidDeviceAdapter(AdbRunner()), artifacts)

    devices = await runtime.list_devices()
    if not devices:
        print("FAIL: 无在线设备")
        return 1
    device_id = devices[0]["device_id"]
    print(f"[1] 设备: {device_id} model={devices[0]['model']}")

    readiness = await runtime.readiness()
    print(f"[2] readiness: {json.dumps(readiness, ensure_ascii=False)[:300]}")

    inspection = await runtime.inspect_device(device_id)
    caps = inspection.get("capabilities", {})
    avail = [k for k, v in caps.items() if v == "available"] if isinstance(caps, dict) else caps
    print(f"[3] 能力可用数: {len(avail)}")

    target_app = sys.argv[1] if len(sys.argv) > 1 else "com.jingdong.app.mall"
    launch = await runtime.open_app(device_id, target_app)
    print(f"[4] 启动 {target_app}: {json.dumps(launch, ensure_ascii=False)[:200]}")

    await asyncio.sleep(4.0)  # 等待启动动画/弹窗稳定
    obs = await runtime.observe(device_id)
    fg = obs["foreground_app"]
    print(f"[5] 前台: {fg['app_id']} {fg['activity']}")
    print(f"    截图: {obs['screen']['screenshot']['relative_path']}")

    ui_path = artifacts.resolve(obs["ui_tree"]["artifact"]["relative_path"])
    nodes = _summarize_ui_tree(ui_path.read_bytes())
    print(f"[6] 交互节点数: {len(nodes)}")
    summary_path = OUTPUT_DIR / stamp / "ui-nodes.json"
    summary_path.write_text(
        json.dumps(nodes, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"    节点摘要: {summary_path}")

    interesting = [
        n for n in nodes
        if any(k in (n["text"] + n["desc"] + n["rid"]) for k in ("搜索", "search", "Search"))
    ][:8]
    print(f"[7] 搜索相关节点: {json.dumps(interesting, ensure_ascii=False, indent=2)}")
    print(f"\n产物目录: {OUTPUT_DIR / stamp}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
