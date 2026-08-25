"""ITER-0059 真机 E2E：受控 Helper IME 的 Unicode 文本输入。

验收场景对应 docs/iterations/0059-unicode-text-input/acceptance.md。
需要已授权的真机在线（adb devices 可见）。Helper APK 安装走既有
app.install@1 两阶段 High 风险授权链路，安装前校验登记 SHA-256。
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime"))

from mobile_agent.devices.adapters.android import AdbRunner, AndroidDeviceAdapter
from mobile_agent.domain.errors import MobileAgentError
from mobile_agent.domain.unicode_input import HELPER_APK_SHA256, HELPER_PACKAGE
from mobile_agent.evidence.artifacts import ArtifactStore
from mobile_agent.runtime import RuntimeService

HELPER_APK = (
    Path(__file__).resolve().parents[1]
    / "helpers"
    / "unicode-ime"
    / "dist"
    / "unicode-ime.apk"
)


async def _wait_task(runtime: RuntimeService, task_id: str) -> dict:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        execution = runtime.get_task_execution(task_id)
        if execution["status"] in {"succeeded", "failed"}:
            return runtime.get_task(task_id)
        await asyncio.sleep(0.2)
    raise AssertionError("task did not reach a terminal state")


async def main() -> int:
    with tempfile.TemporaryDirectory() as directory:
        artifacts = ArtifactStore(Path(directory) / "artifacts")
        runtime = RuntimeService(
            AndroidDeviceAdapter(AdbRunner()), artifacts
        )
        devices = await runtime._adapter.list_devices()
        if not devices:
            print("FAIL: 无在线设备")
            return 1
        device_id = devices[0].device_id
        print(f"设备: {device_id} ({devices[0].model})")

        failures = 0

        # 场景 1：登记摘要校验（安装信任锚点）
        digest = hashlib.sha256(HELPER_APK.read_bytes()).hexdigest()
        ok = digest == HELPER_APK_SHA256
        print(f"场景1 Helper APK 登记摘要: {'PASS' if ok else 'FAIL'} -> {digest[:16]}…")
        failures += 0 if ok else 1
        if not ok:
            print("摘要不符，中止（不得安装未登记的 Helper）")
            return 1

        # 场景 2：两阶段授权安装（已安装则复用）
        installed = HELPER_PACKAGE in await runtime._adapter.list_installed_apps(device_id)
        if installed:
            print("场景2 Helper 安装: PASS（设备已安装，复用）")
        else:
            inbox = Path(directory) / "apks"
            inbox.mkdir(parents=True, exist_ok=True)
            shutil.copy2(HELPER_APK, inbox / HELPER_APK.name)
            try:
                approval = await runtime.prepare_apk_install(
                    device_id, str(inbox / HELPER_APK.name), HELPER_PACKAGE
                )
                submitted = runtime.submit_apk_install_task(
                    approval["approval_id"],
                    confirmed=True,
                    idempotency_key=f"e2e-0059-{int(time.time())}",
                )
                report = await _wait_task(runtime, submitted["task_id"])
                ok = report["status"] == "succeeded"
                print(f"场景2 Helper 两阶段安装: {'PASS' if ok else 'FAIL'} -> {report['status']}")
                failures += 0 if ok else 1
            except MobileAgentError as error:
                print(f"场景2 Helper 两阶段安装: FAIL -> {error.code} {error.message}")
                failures += 1
        helper_visible = any(
            HELPER_PACKAGE in ime
            for ime in await runtime._adapter.installed_input_methods(device_id)
        )
        if not helper_visible:
            print("FAIL: Helper 安装后未出现在 ime list -a，中止后续场景")
            return 1

        # 场景 3：未确认时 Medium 风险确认拦截（无任何设备动作）
        try:
            await runtime.unicode_text_input(
                device_id,
                {"strategy": "resource_id", "value": "search_box"},
                "你好",
                confirmed=False,
            )
            print("场景3 未确认拦截: FAIL -> 未要求确认")
            failures += 1
        except MobileAgentError as error:
            ok = error.code == "CONFIRMATION_REQUIRED"
            print(f"场景3 未确认拦截: {'PASS' if ok else 'FAIL'} -> {error.code}")
            failures += 0 if ok else 1

        # 场景 4：敏感数字形态在 Tool 层先于设备动作拒绝
        try:
            await runtime.unicode_text_input(
                device_id,
                {"strategy": "resource_id", "value": "search_box"},
                "123456",
                confirmed=True,
            )
            print("场景4 敏感数字拦截: FAIL -> 未拒绝")
            failures += 1
        except MobileAgentError as error:
            ok = error.code == "ACTION_REJECTED_BY_POLICY"
            print(f"场景4 敏感数字拦截: {'PASS' if ok else 'FAIL'} -> {error.code}")
            failures += 0 if ok else 1

        # 场景 5：设置搜索框中文输入 + 读回验证 + IME 恢复
        # MagicOS 设置首页常驻搜索框（AutoCompleteTextView, rid=search_src_text）。
        previous_ime = await runtime._adapter.current_input_method(device_id)
        print(f"  当前 IME: {previous_ime}")
        try:
            await runtime.navigate_app(device_id, "settings.home")
            await asyncio.sleep(1.0)
            observation = await runtime._adapter.observe(device_id, artifacts)
            nodes_path = artifacts.resolve(observation.ui_tree.artifact.relative_path)
            from mobile_agent.ui.parser import UiHierarchyParser

            parser = UiHierarchyParser()
            nodes = [n.to_dict() for n in parser.parse(nodes_path.read_bytes())]
            field = next(
                (
                    n
                    for n in nodes
                    if str(n.get("resource_id", "")).endswith("search_src_text")
                    and n.get("enabled")
                    and n.get("visible")
                ),
                None,
            )
            if field is None:
                print("场景5 中文输入: FAIL -> 设置首页未找到搜索框（MagicOS 界面差异）")
                failures += 1
            else:
                result = await runtime.unicode_text_input(
                    device_id,
                    {"strategy": "resource_id", "value": field["resource_id"]},
                    "你好世界",
                    confirmed=True,
                )
                restored_ime = await runtime._adapter.current_input_method(device_id)
                ok = (
                    result["success"]
                    and result["ime"]["restored"]
                    and restored_ime == previous_ime
                )
                print(
                    f"场景5 中文输入: {'PASS' if ok else 'FAIL'} "
                    f"-> length={result['text_length']}, restored_to={restored_ime}"
                )
                failures += 0 if ok else 1
        except MobileAgentError as error:
            print(f"场景5 中文输入: FAIL -> {error.code} {error.message}")
            failures += 1

        # 场景 6：卸载 Helper 恢复设备原状（两阶段授权）
        try:
            removal = await runtime.prepare_app_removal(device_id, HELPER_PACKAGE)
            submitted = runtime.submit_app_removal_task(
                removal["approval_id"],
                confirmed=True,
                idempotency_key=f"e2e-0059-rm-{int(time.time())}",
            )
            report = await _wait_task(runtime, submitted["task_id"])
            ok = report["status"] == "succeeded"
            print(f"场景6 Helper 卸载还原: {'PASS' if ok else 'FAIL'} -> {report['status']}")
            failures += 0 if ok else 1
        except MobileAgentError as error:
            print(f"场景6 Helper 卸载还原: FAIL -> {error.code} {error.message}")
            failures += 1

        print(f"\n汇总: {'全部通过' if failures == 0 else f'{failures} 项失败'}")
        return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
