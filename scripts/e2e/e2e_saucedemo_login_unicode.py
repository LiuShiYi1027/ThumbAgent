"""真机 E2E：SauceDemo 登录表单 unicode 输入（device_e2e，规范 rid 选择器路径）。

Sauce Labs MyDemoApp 是自动化测试专用 fixture 应用（无真实账号体系）。
流程：菜单 → Login → 用户名输入框（rid=nameET）→ unicode 输入 → 读回验证。
前置：设备已安装 com.saucelabs.mydemoapp.android；Helper IME 已安装。
其余前置与恢复约束见 scripts/e2e/README.md。产物写入 e2e-output/（不入库）。
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


def _center(bounds: str) -> tuple[int, int]:
    x1, y1, x2, y2 = (int(g) for g in BOUNDS_RE.fullmatch(bounds or "").groups())
    return (x1 + x2) // 2, (y1 + y2) // 2


async def _observe_nodes(runtime, artifacts, device_id):
    obs = await runtime.observe(device_id)
    ui_path = artifacts.resolve(obs["ui_tree"]["artifact"]["relative_path"])
    return obs, list(ET.fromstring(ui_path.read_bytes()).iter("node"))


async def _tap(runtime, device_id, x, y):
    result = await runtime.invoke_tool("input.tap", device_id, {"x": x, "y": y}, confirmed=True)
    return result["status"]


async def main() -> int:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = OUTPUT_DIR / stamp
    artifacts = ArtifactStore(out_dir / "artifacts")
    runtime = RuntimeService(AndroidDeviceAdapter(AdbRunner()), artifacts)
    device_id = (await runtime.list_devices())[0]["device_id"]

    await runtime.open_app(device_id, "com.saucelabs.mydemoapp.android")
    await asyncio.sleep(3.0)

    # 首次启动必现系统权限对话框：只点「禁止」，绝不点「始终允许」。
    obs, nodes = await _observe_nodes(runtime, artifacts, device_id)
    if "permissioncontroller" in obs["foreground_app"]["app_id"]:
        deny = next(
            (n for n in nodes if "permission_deny_button" in (n.get("resource-id") or "")),
            None,
        )
        if deny is None:
            print("FAIL: 权限对话框找不到「禁止」按钮"); return 1
        print(f"[0] 拒绝权限请求: {await _tap(runtime, device_id, *_center(deny.get('bounds')))}")
        await asyncio.sleep(1.5)

    obs, nodes = await _observe_nodes(runtime, artifacts, device_id)
    login_item = next((n for n in nodes if (n.get("text") or "") == "Log In"), None)
    if login_item is None:
        menu = next((n for n in nodes if (n.get("content-desc") or "") == "View menu"), None)
        if menu is None:
            print("FAIL: 找不到菜单按钮"); return 1
        print(f"[1] 打开菜单: {await _tap(runtime, device_id, *_center(menu.get('bounds')))}")
        await asyncio.sleep(1.5)
        obs, nodes = await _observe_nodes(runtime, artifacts, device_id)
        login_item = next((n for n in nodes if (n.get("text") or "") == "Log In"), None)
    if login_item is None:
        print("FAIL: 菜单里找不到 Log In"); return 1
    print(f"[2] 进入 Login: {await _tap(runtime, device_id, *_center(login_item.get('bounds')))}")
    await asyncio.sleep(1.5)

    obs, nodes = await _observe_nodes(runtime, artifacts, device_id)
    print(f"[3] 当前页: {obs['foreground_app']['activity']}")
    for n in nodes:
        cls = n.get("class") or ""
        if cls.endswith("EditText"):
            print(f"    EditText rid={n.get('resource-id')} bounds={n.get('bounds')}")

    selector = {"strategy": "resource_id", "value": "id/nameET", "match": "contains"}
    try:
        result = await runtime.unicode_text_input(
            device_id, selector, "iPhone 17", confirmed=True
        )
    except Exception as exc:  # E2E 脚本：打印完整错误码而非裸 traceback
        print(f"[4] unicode 输入: FAIL {type(exc).__name__} "
              f"code={getattr(exc, 'code', None)} details={getattr(exc, 'details', None)}")
        return 1
    print(f"[4] unicode 输入: success={result['success']} verification={result['verification']}")
    print(f"    IME restored={result['ime']['restored']} previous={result['ime']['previous_id']}")

    obs, nodes = await _observe_nodes(runtime, artifacts, device_id)
    name_node = next(
        (n for n in nodes if (n.get("resource-id") or "").endswith("nameET")), None
    )
    actual = name_node.get("text") if name_node is not None else None
    print(f"[5] 读回: {actual!r}")
    print(f"\n产物目录: {out_dir}")
    if not (result["success"] and result["verification"] == "verified" and actual == "iPhone 17"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
