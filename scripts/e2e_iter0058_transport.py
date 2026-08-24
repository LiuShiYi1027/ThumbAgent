"""ITER-0058 真机 E2E（传输层）：经真实 REST 与 MCP stdio 链路调用新能力。

对应 acceptance.md 真机 E2E 第 1、2、3 条（MCP 导航、MCP 未知枚举拒绝、
REST 通知快照与确认流程）。需要已授权真机在线。脚本结束时自动停止 Runtime。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PORT = 8879
BASE = f"http://127.0.0.1:{PORT}"
TOKEN = "e2e-iter0058-token"


def rest(path: str, body: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        f"{BASE}{path}",
        data=data,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST" if body is not None else "GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


class McpClient:
    """Minimal newline-delimited stdio JSON-RPC client for E2E."""

    def __init__(self) -> None:
        env = {
            **os.environ,
            "PYTHONPATH": str(ROOT / "runtime"),
            "MOBILE_AGENT_MCP_BASE_URL": BASE,
            "MOBILE_AGENT_API_TOKEN": TOKEN,
        }
        self.process = subprocess.Popen(
            [sys.executable, "-m", "mobile_agent.mcp"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            env=env,
            text=True,
        )
        self._next_id = 0

    def call(self, method: str, params: dict | None = None) -> dict:
        self._next_id += 1
        message = {"jsonrpc": "2.0", "id": self._next_id, "method": method}
        if params is not None:
            message["params"] = params
        assert self.process.stdin is not None and self.process.stdout is not None
        self.process.stdin.write(json.dumps(message) + "\n")
        self.process.stdin.flush()
        while True:
            line = self.process.stdout.readline()
            if not line:
                raise RuntimeError("MCP server 意外退出")
            reply = json.loads(line)
            if reply.get("id") == self._next_id:
                return reply

    def notify(self, method: str) -> None:
        assert self.process.stdin is not None
        self.process.stdin.write(
            json.dumps({"jsonrpc": "2.0", "method": method}) + "\n"
        )
        self.process.stdin.flush()

    def close(self) -> None:
        self.process.terminate()
        self.process.wait(timeout=10)


def main() -> int:
    data_dir = tempfile.mkdtemp(prefix="mobile-agent-e2e-")
    env = {
        **os.environ,
        "PYTHONPATH": str(ROOT / "runtime"),
        "MOBILE_AGENT_DATA_DIR": data_dir,
        "MOBILE_AGENT_API_TOKEN": TOKEN,
    }
    server = subprocess.Popen(
        [sys.executable, "-m", "mobile_agent.api.server", "--port", str(PORT)],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    failures = 0
    try:
        for _ in range(50):
            if server.poll() is not None:
                print("FAIL: Runtime 启动失败")
                return 1
            try:
                status, payload = rest("/v1/devices")
                if status == 200:
                    break
            except OSError:
                time.sleep(0.2)
        else:
            print("FAIL: Runtime 未就绪")
            return 1

        devices = payload["devices"]
        if not devices:
            print("FAIL: 无在线设备")
            return 1
        device_id = devices[0]["device_id"]
        print(f"设备: {device_id} ({devices[0]['model']})")

        # 场景 3（REST）：未确认拦截 + 确认后脱敏快照
        status, payload = rest(
            "/v1/skills/device.notifications.read/invoke",
            {"device_id": device_id, "max_notifications": 10, "confirmed": False},
        )
        ok = status == 403 and payload["error"]["code"] == "CONFIRMATION_REQUIRED"
        print(f"场景3a REST 未确认拦截: {'PASS' if ok else 'FAIL'} -> {status}")
        failures += 0 if ok else 1

        status, payload = rest(
            "/v1/skills/device.notifications.read/invoke",
            {"device_id": device_id, "max_notifications": 10, "confirmed": True},
        )
        if status == 200:
            items = payload["result"]["notifications"]
            ok = all(
                set(item) <= {"package", "title", "posted_at"}
                and (item["title"] is None or len(item["title"]) <= 32)
                for item in items
            )
            print(
                f"场景3b REST 通知快照: {'PASS' if ok else 'FAIL'} -> {len(items)} 条"
            )
            failures += 0 if ok else 1
        else:
            ok = payload["error"]["code"] == "NOTIFICATIONS_READ_EMPTY"
            print(
                f"场景3b REST 通知快照: {'PASS（零通知）' if ok else 'FAIL'} -> "
                f"{payload['error']['code']}"
            )
            failures += 0 if ok else 1

        # 场景 1/2（MCP stdio）：导航 Wi-Fi 设置 + 未知枚举拒绝
        mcp = McpClient()
        try:
            mcp.call(
                "initialize",
                {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": {"name": "e2e", "version": "0.1"},
                },
            )
            mcp.notify("notifications/initialized")

            reply = mcp.call(
                "tools/call",
                {
                    "name": "mobile_navigate_to_system_page",
                    "arguments": {"device_id": device_id, "target": "settings.wifi"},
                },
            )
            text = reply["result"]["content"][0]["text"]
            parsed = json.loads(text)
            fg = parsed["result"]["foreground_app"]
            ok = (
                not reply["result"].get("isError")
                and fg["app_id"] == "com.android.settings"
                and "wifi" in fg["activity"].lower()
            )
            print(f"场景1 MCP 导航 Wi-Fi 设置: {'PASS' if ok else 'FAIL'} -> {fg}")
            failures += 0 if ok else 1

            reply = mcp.call(
                "tools/call",
                {
                    "name": "mobile_navigate_to_system_page",
                    "arguments": {
                        "device_id": device_id,
                        "target": "settings.nonexistent",
                    },
                },
            )
            text = reply["result"]["content"][0]["text"]
            ok = "INVALID_ARGUMENT" in text
            print(
                f"场景2a MCP 未知枚举 Schema 拦截: {'PASS' if ok else 'FAIL'} -> "
                f"{text[:120]}"
            )
            failures += 0 if ok else 1
        finally:
            mcp.close()

        # 场景 2b（REST）：未登记枚举由 Domain 边界拒绝，设备无动作
        status, payload = rest(
            "/v1/skills/app.navigate/invoke",
            {"device_id": device_id, "target": "settings.nonexistent"},
        )
        ok = payload.get("error", {}).get("code") == "NAVIGATION_ACTION_UNKNOWN"
        print(
            f"场景2b REST 未知枚举领域拒绝: {'PASS' if ok else 'FAIL'} -> "
            f"{status} {payload.get('error', {}).get('code')}"
        )
        failures += 0 if ok else 1

        print(f"\n汇总: {'全部通过' if failures == 0 else f'{failures} 项失败'}")
        return 0 if failures == 0 else 1
    finally:
        server.terminate()
        server.wait(timeout=10)


if __name__ == "__main__":
    sys.exit(main())
