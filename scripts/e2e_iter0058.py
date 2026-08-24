"""ITER-0058 真机 E2E：枚举制系统导航直达 + 有界脱敏通知读取。

四个验收场景对应 docs/iterations/0058-programmatic-navigation/acceptance.md。
需要已授权的真机在线（adb devices 可见）。
"""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime"))

from mobile_agent.devices.adapters.android import AdbRunner, AndroidDeviceAdapter
from mobile_agent.domain.errors import MobileAgentError
from mobile_agent.evidence.artifacts import ArtifactStore
from mobile_agent.runtime import RuntimeService


async def main() -> int:
    with tempfile.TemporaryDirectory() as directory:
        runtime = RuntimeService(
            AndroidDeviceAdapter(AdbRunner()), ArtifactStore(Path(directory))
        )
        devices = await runtime._adapter.list_devices()
        if not devices:
            print("FAIL: 无在线设备")
            return 1
        device_id = devices[0].device_id
        print(f"设备: {device_id} ({devices[0].model})")

        failures = 0

        # 场景 1：app.navigate 进入 Wi-Fi 设置页，前台验证通过
        try:
            result = await runtime.navigate_app(device_id, "settings.wifi")
            fg = result["foreground_app"]
            ok = (
                fg["app_id"] == "com.android.settings"
                and "wifi" in fg["activity"].lower()
            )
            print(f"场景1 导航 Wi-Fi 设置: {'PASS' if ok else 'FAIL'} -> {fg}")
            failures += 0 if ok else 1
        except MobileAgentError as error:
            print(f"场景1 导航 Wi-Fi 设置: FAIL -> {error.code} {error.message}")
            failures += 1

        # 场景 2：未登记枚举 ID，进程调用前拒绝
        try:
            await runtime.navigate_app(device_id, "settings.nonexistent")
            print("场景2 未知枚举拒绝: FAIL -> 未抛错")
            failures += 1
        except MobileAgentError as error:
            ok = error.code == "NAVIGATION_ACTION_UNKNOWN"
            print(f"场景2 未知枚举拒绝: {'PASS' if ok else 'FAIL'} -> {error.code}")
            failures += 0 if ok else 1

        # 场景 3a：通知读取未确认时要求 Medium 风险确认
        try:
            await runtime.read_device_notifications(device_id, confirmed=False)
            print("场景3a 未确认拦截: FAIL -> 未要求确认")
            failures += 1
        except MobileAgentError as error:
            ok = error.code == "CONFIRMATION_REQUIRED"
            print(f"场景3a 未确认拦截: {'PASS' if ok else 'FAIL'} -> {error.code}")
            failures += 0 if ok else 1

        # 场景 3b：确认后读取通知快照，结构符合脱敏 Contract
        try:
            result = await runtime.read_device_notifications(
                device_id, max_notifications=50, confirmed=True
            )
            notifications = result["notifications"]
            shape_ok = result["skill_id"] == "device.notifications.read" and all(
                set(item) <= {"package", "title", "posted_at"}
                and (item["title"] is None or len(item["title"]) <= 32)
                for item in notifications
            )
            print(
                f"场景3b 通知快照: {'PASS' if shape_ok else 'FAIL'} "
                f"-> {len(notifications)} 条, evidence={result.get('evidence_refs')}"
            )
            if notifications:
                print(f"  样例: {json.dumps(notifications[0], ensure_ascii=False)}")
            failures += 0 if shape_ok else 1
        except MobileAgentError as error:
            # 零通知是合法终态
            if error.code == "NOTIFICATIONS_READ_EMPTY":
                print("场景3b 通知快照: PASS（设备当前零通知，专用错误码）")
            else:
                print(f"场景3b 通知快照: FAIL -> {error.code} {error.message}")
                failures += 1

        # 场景 4：自然语言目标命中程序化捷径
        task = await runtime.run_agent_task(
            device_id, "进入 Wi-Fi 设置页面", confirmed=True
        )
        shortcut_hit = (
            task["status"] == "succeeded"
            and task.get("completion_source") == "runtime_shortcut"
            and task["evidence_summary"].get("rounds") == 0
        )
        print(
            f"场景4 自然语言捷径: {'PASS' if shortcut_hit else 'FAIL'} "
            f"-> status={task['status']}, source={task.get('completion_source')}, "
            f"rounds={task['evidence_summary'].get('rounds')}, "
            f"fg={task['evidence_summary'].get('final_foreground_app')}"
        )
        failures += 0 if shortcut_hit else 1

        print(f"\n汇总: {'全部通过' if failures == 0 else f'{failures} 项失败'}")
        return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
