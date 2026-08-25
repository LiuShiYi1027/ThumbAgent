"""真机 E2E：设置搜索框 unicode 输入回归（device_e2e，稳定验收场景）。

回归对象：helper 手搓 UTF-7 解码（短载荷块）+ hint 感知读回验证。
三个用例（每个用例前先点清空按钮，从空字段 text==hint 状态开始）：
  1. "iPhone 17" —— 空格产生短载荷块（ART 内建解码器崩溃场景）
  2. "A你B"      —— 孤立单字符块
  3. "你好世界"  —— 纯 CJK 回归
流程：打开设置 → 点搜索入口 → 逐用例清空/输入/读回 → 结束清空字段并返回。
前置：Helper IME 已安装启用；其余约束见 scripts/e2e/README.md。
产物写入 e2e-output/（不入库）。
"""

from __future__ import annotations

import asyncio
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
SELECTOR = {"strategy": "resource_id", "value": "search_src_text", "match": "contains"}
CASES = ("iPhone 17", "A你B", "你好世界")


def _center(bounds: str) -> tuple[int, int]:
    x1, y1, x2, y2 = (int(g) for g in BOUNDS_RE.fullmatch(bounds or "").groups())
    return (x1 + x2) // 2, (y1 + y2) // 2


async def _observe_nodes(runtime, artifacts, device_id):
    obs = await runtime.observe(device_id)
    ui_path = artifacts.resolve(obs["ui_tree"]["artifact"]["relative_path"])
    return obs, list(ET.fromstring(ui_path.read_bytes()).iter("node"))


def _find(nodes, *, rid_part: str | None = None, desc: str | None = None):
    for node in nodes:
        if rid_part and rid_part in (node.get("resource-id") or ""):
            return node
        if desc and (node.get("content-desc") or "") == desc:
            return node
    return None


async def _tap(runtime, device_id, node) -> None:
    x, y = _center(node.get("bounds"))
    await runtime.invoke_tool("input.tap", device_id, {"x": x, "y": y}, confirmed=True)


async def _open_search_page(runtime, artifacts, device_id) -> bool:
    """从设置首页进入搜索页；已在搜索页则直接就绪。"""
    _, nodes = await _observe_nodes(runtime, artifacts, device_id)
    if _find(nodes, rid_part="search_src_text") is not None:
        return True
    entry = _find(nodes, desc="搜索") or _find(nodes, rid_part="search")
    if entry is None:
        return False
    await _tap(runtime, device_id, entry)
    await asyncio.sleep(2.0)
    _, nodes = await _observe_nodes(runtime, artifacts, device_id)
    field = _find(nodes, rid_part="search_src_text")
    if field is None:
        return False
    # 真机实测：刚进搜索页时面板仍在动画中，立即输入可能随焦点未就绪而丢失。
    # 显式点一次输入框建立输入连接并等待稳定。
    await _tap(runtime, device_id, field)
    await asyncio.sleep(1.0)
    return True


async def _clear_field(runtime, artifacts, device_id) -> None:
    """若清空按钮可见则点击，保证从空字段（text==hint）状态开始。"""
    _, nodes = await _observe_nodes(runtime, artifacts, device_id)
    close = _find(nodes, rid_part="search_close_btn")
    if close is not None:
        await _tap(runtime, device_id, close)
        await asyncio.sleep(1.0)


async def main() -> int:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = OUTPUT_DIR / stamp
    artifacts = ArtifactStore(out_dir / "artifacts")
    runtime = RuntimeService(AndroidDeviceAdapter(AdbRunner()), artifacts)
    device_id = (await runtime.list_devices())[0]["device_id"]

    await runtime.open_app(device_id, "com.android.settings")
    await asyncio.sleep(2.5)
    if not await _open_search_page(runtime, artifacts, device_id):
        print("FAIL: 设置首页找不到搜索入口（本脚本按 MagicOS 设置布局编写）")
        return 1
    print("[0] 已进入设置搜索页")

    failures = 0
    for index, text in enumerate(CASES, start=1):
        await _clear_field(runtime, artifacts, device_id)
        try:
            result = await runtime.unicode_text_input(
                device_id, SELECTOR, text, confirmed=True
            )
        except Exception as exc:  # E2E 脚本：打印完整错误后继续下一个用例
            print(f"[{index}] {text!r}: FAIL {type(exc).__name__} {exc}")
            failures += 1
            continue
        ok = result["success"] and result["verification"] == "verified"
        print(
            f"[{index}] {text!r}: success={result['success']} "
            f"verification={result['verification']} restored={result['ime']['restored']}"
        )
        if not ok:
            failures += 1
        # 独立读回确认真实上屏内容
        _, nodes = await _observe_nodes(runtime, artifacts, device_id)
        field = _find(nodes, rid_part="search_src_text")
        actual = field.get("text") if field is not None else None
        match = "OK" if actual == text else f"MISMATCH got {actual!r}"
        print(f"    读回: {match}")
        if actual != text:
            failures += 1

    # 恢复：清空字段并退出搜索页（输入法恢复由 unicode_text_input 自身保证）。
    await _clear_field(runtime, artifacts, device_id)
    await runtime.invoke_tool("navigation.back", device_id, {}, confirmed=True)
    print("\n[cleanup] 字段已清空，已退出搜索页")
    print(f"产物目录: {out_dir}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
