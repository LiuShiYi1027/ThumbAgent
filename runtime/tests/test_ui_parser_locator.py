from __future__ import annotations

import unittest

from mobile_agent.domain.errors import MobileAgentError
from mobile_agent.ui.locator import UiLocator
from mobile_agent.ui.model import UiSelector
from mobile_agent.ui.parser import UiHierarchyParser


XML = b'''<?xml version="1.0" encoding="UTF-8"?>
<hierarchy rotation="0">
  <node text="Settings" resource-id="root" class="View" package="android" clickable="false" enabled="true" visible-to-user="true" bounds="[0,0][100,200]">
    <node text="" resource-id="row_display" class="View" package="android" clickable="true" enabled="true" visible-to-user="true" bounds="[0,20][100,80]">
      <node text="Display" resource-id="title" class="TextView" package="android" clickable="false" enabled="true" visible-to-user="true" bounds="[10,30][80,60]"/>
    </node>
    <node text="Duplicate" resource-id="dup1" class="TextView" package="android" clickable="true" enabled="true" visible-to-user="true" bounds="[0,80][100,120]"/>
    <node text="Duplicate" resource-id="dup2" class="TextView" package="android" clickable="true" enabled="true" visible-to-user="true" bounds="[0,120][100,160]"/>
  </node>
</hierarchy>'''


class UiParserLocatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = UiHierarchyParser()
        self.nodes = self.parser.parse(XML)
        self.locator = UiLocator()

    def test_parses_standard_nodes_and_bounds(self) -> None:
        self.assertEqual(5, len(self.nodes))
        display = next(node for node in self.nodes if node.text == "Display")
        self.assertEqual("title", display.resource_id)
        self.assertEqual((45, 45), display.bounds.center)
        self.assertFalse(display.clickable)

    def test_hint_attribute_and_effective_text(self) -> None:
        """真机行为：空输入框的 text 等于 hint；effective_text 此时应视为空。"""
        xml = (
            b'<hierarchy>'
            b'<node text="\xe6\x90\x9c\xe7\xb4\xa2\xe8\xae\xbe\xe7\xbd\xae\xe9\xa1\xb9" '
            b'hint="\xe6\x90\x9c\xe7\xb4\xa2\xe8\xae\xbe\xe7\xbd\xae\xe9\xa1\xb9" '
            b'resource-id="search" class="EditText" package="android" clickable="true" '
            b'enabled="true" visible-to-user="true" bounds="[0,0][100,50]"/>'
            b'<node text="iPhone 17" hint="\xe6\x90\x9c\xe7\xb4\xa2" '
            b'resource-id="filled" class="EditText" package="android" clickable="true" '
            b'enabled="true" visible-to-user="true" bounds="[0,50][100,100]"/>'
            b'<node text="Plain" resource-id="plain" class="TextView" package="android" '
            b'clickable="false" enabled="true" visible-to-user="true" '
            b'bounds="[0,100][100,150]"/>'
            b'</hierarchy>'
        )
        nodes = self.parser.parse(xml)

        empty_field = next(n for n in nodes if n.resource_id == "search")
        self.assertEqual("搜索设置项", empty_field.hint)
        self.assertEqual("搜索设置项", empty_field.text)
        self.assertEqual("", empty_field.effective_text)

        filled = next(n for n in nodes if n.resource_id == "filled")
        self.assertEqual("iPhone 17", filled.effective_text)

        plain = next(n for n in nodes if n.resource_id == "plain")
        self.assertEqual("", plain.hint)
        self.assertEqual("Plain", plain.effective_text)
        self.assertEqual("Plain", plain.to_dict()["text"])

    def test_exact_contains_resource_and_ancestor_path(self) -> None:
        exact = UiSelector.from_dict(
            {"strategy": "text", "value": "Display", "resolve_clickable_ancestor": True}
        )
        match = self.locator.locate(self.nodes, exact, 100, 200)
        self.assertEqual("title", match.matched_node.resource_id)
        self.assertEqual("row_display", match.target_node.resource_id)
        self.assertEqual((50, 50), (match.tap_x, match.tap_y))

        contains = UiSelector.from_dict(
            {
                "strategy": "resource_id",
                "value": "title",
                "match": "contains",
                "ancestor_path": [
                    {"strategy": "text", "value": "Settings"},
                    {"strategy": "resource_id", "value": "row_display"},
                ],
                "resolve_clickable_ancestor": True,
            }
        )
        self.assertEqual("title", self.locator.locate(self.nodes, contains, 100, 200).matched_node.resource_id)

    def test_content_description_and_clickable_filter_are_supported(self) -> None:
        xml = b'''<hierarchy><node text="" resource-id="icon" content-desc="Open display" class="ImageButton" package="android" clickable="true" enabled="true" visible-to-user="true" bounds="[0,0][40,40]"/></hierarchy>'''
        nodes = self.parser.parse(xml)
        selector = UiSelector.from_dict(
            {
                "strategy": "content_description",
                "value": "display",
                "match": "contains",
                "clickable": True,
            }
        )
        match = self.locator.locate(nodes, selector, 100, 200)
        self.assertEqual("icon", match.target_node.resource_id)

    def test_not_found_ambiguous_not_clickable_and_bounds_are_explicit(self) -> None:
        with self.assertRaises(MobileAgentError) as missing:
            self.locator.locate(
                self.nodes,
                UiSelector.from_dict({"strategy": "text", "value": "Nope"}),
                100,
                200,
            )
        self.assertEqual("TARGET_NOT_FOUND", missing.exception.code)

        with self.assertRaises(MobileAgentError) as ambiguous:
            self.locator.locate(
                self.nodes,
                UiSelector.from_dict({"strategy": "text", "value": "Duplicate"}),
                100,
                200,
            )
        self.assertEqual("TARGET_AMBIGUOUS", ambiguous.exception.code)

        with self.assertRaises(MobileAgentError) as not_clickable:
            self.locator.locate(
                self.nodes,
                UiSelector.from_dict({"strategy": "text", "value": "Display"}),
                100,
                200,
            )
        self.assertEqual("TARGET_NOT_CLICKABLE", not_clickable.exception.code)

        with self.assertRaises(MobileAgentError) as outside:
            self.locator.locate(
                self.nodes,
                UiSelector.from_dict(
                    {
                        "strategy": "text",
                        "value": "Display",
                        "resolve_clickable_ancestor": True,
                    }
                ),
                50,
                200,
            )
        self.assertEqual("TARGET_OUT_OF_BOUNDS", outside.exception.code)

    def test_rejects_doctype_and_invalid_bounds(self) -> None:
        with self.assertRaises(MobileAgentError) as entity:
            self.parser.parse(b'<!DOCTYPE x [<!ENTITY x "bad">]><hierarchy/>')
        self.assertEqual("UI_TREE_INVALID", entity.exception.code)

        # 格式损坏（非法字符/缺失）仍是协议级错误。
        malformed = b'<hierarchy><node bounds="[10,10][5]"/></hierarchy>'
        with self.assertRaises(MobileAgentError) as bounds:
            self.parser.parse(malformed)
        self.assertEqual("UI_TREE_INVALID", bounds.exception.code)

    def test_degenerate_bounds_subtree_is_skipped_not_fatal(self) -> None:
        """AOSP 模拟器实测：手势导航区留下退化 bounds（[0,2382][1080,2337]），
        零/负面积节点不可交互，应连同子树跳过，而不是让整棵树 UI_TREE_INVALID。"""
        xml = (
            b'<hierarchy>'
            b'<node text="" resource-id="nav_bar" bounds="[0,2382][1080,2337]">'
            b'<node text="Hidden child" resource-id="nav_child" bounds="[63,2382][1038,2337]"/>'
            b'</node>'
            b'<node text="Display" resource-id="title" class="TextView" package="android" '
            b'clickable="true" enabled="true" visible-to-user="true" bounds="[0,0][100,50]"/>'
            b'</hierarchy>'
        )
        nodes = self.parser.parse(xml)

        self.assertEqual(["Display"], [node.text for node in nodes])
        match = self.locator.locate(
            nodes, UiSelector.from_dict({"strategy": "text", "value": "Display"}), 100, 50
        )
        self.assertEqual("title", match.target_node.resource_id)

    def test_hint_strategy_matches_placeholder_not_text(self) -> None:
        """hint 策略匹配占位文本：空字段 text==hint 场景下语义比 text 策略稳定。"""
        xml = (
            b'<hierarchy>'
            b'<node text="\xe6\x90\x9c\xe7\xb4\xa2\xe8\xae\xbe\xe7\xbd\xae\xe9\xa1\xb9" '
            b'hint="\xe6\x90\x9c\xe7\xb4\xa2\xe8\xae\xbe\xe7\xbd\xae\xe9\xa1\xb9" '
            b'resource-id="search" class="EditText" package="android" clickable="true" '
            b'enabled="true" visible-to-user="true" bounds="[0,0][100,50]"/>'
            b'<node text="Filled" hint="Type here" resource-id="filled" class="EditText" '
            b'package="android" clickable="true" enabled="true" visible-to-user="true" '
            b'bounds="[0,50][100,100]"/>'
            b'</hierarchy>'
        )
        nodes = self.parser.parse(xml)

        exact = self.locator.locate(
            nodes,
            UiSelector.from_dict({"strategy": "hint", "value": "搜索设置项"}),
            100,
            100,
        )
        self.assertEqual("search", exact.target_node.resource_id)

        contains = self.locator.locate(
            nodes,
            UiSelector.from_dict({"strategy": "hint", "value": "Type", "match": "contains"}),
            100,
            100,
        )
        self.assertEqual("filled", contains.target_node.resource_id)

        with self.assertRaises(MobileAgentError) as missing:
            self.locator.locate(
                nodes,
                UiSelector.from_dict({"strategy": "hint", "value": "Filled"}),
                100,
                100,
            )
        self.assertEqual("TARGET_NOT_FOUND", missing.exception.code)

    def test_hint_strategy_supported_in_ancestor_path(self) -> None:
        xml = (
            b'<hierarchy>'
            b'<node text="" hint="Section" resource-id="group" class="ViewGroup" '
            b'package="android" clickable="false" enabled="true" visible-to-user="true" '
            b'bounds="[0,0][100,100]">'
            b'<node text="Inner" resource-id="inner" class="TextView" package="android" '
            b'clickable="true" enabled="true" visible-to-user="true" bounds="[0,0][100,50]"/>'
            b'</node>'
            b'</hierarchy>'
        )
        nodes = self.parser.parse(xml)

        match = self.locator.locate(
            nodes,
            UiSelector.from_dict(
                {
                    "strategy": "text",
                    "value": "Inner",
                    "ancestor_path": [{"strategy": "hint", "value": "Section"}],
                }
            ),
            100,
            100,
        )
        self.assertEqual("inner", match.target_node.resource_id)

    def test_rejects_doctype_after_large_prefix(self) -> None:
        payload = b" " * 5000 + b"<!DOCTYPE hierarchy><hierarchy/>"
        with self.assertRaises(MobileAgentError) as raised:
            self.parser.parse(payload)
        self.assertEqual("UI_TREE_INVALID", raised.exception.code)

    def test_find_all_excludes_hidden_nodes_and_honors_package(self) -> None:
        xml = b'''<hierarchy>
        <node text="Hidden" resource-id="hidden" class="TextView" package="com.android.settings" clickable="false" enabled="true" visible-to-user="false" bounds="[0,0][10,10]"/>
        <node text="Title" resource-id="other" class="TextView" package="com.example.other" clickable="false" enabled="true" visible-to-user="true" bounds="[0,10][10,20]"/>
        </hierarchy>'''
        nodes = self.parser.parse(xml)
        hidden = UiSelector.from_dict({"strategy": "text", "value": "Hidden"})
        settings_only = UiSelector.from_dict(
            {
                "strategy": "text",
                "value": "Title",
                "package": "com.android.settings",
            }
        )
        self.assertEqual([], self.locator.find_all(nodes, hidden))
        self.assertEqual([], self.locator.find_all(nodes, settings_only))

    def test_selector_rejects_oversized_ancestor_value(self) -> None:
        with self.assertRaises(MobileAgentError) as raised:
            UiSelector.from_dict(
                {
                    "strategy": "text",
                    "value": "Target",
                    "ancestor_path": [
                        {"strategy": "text", "value": "x" * 1025}
                    ],
                }
            )
        self.assertEqual("INVALID_ARGUMENT", raised.exception.code)

    def test_rejects_tap_center_inside_bottom_gesture_margin(self) -> None:
        nodes = self.parser.parse(
            b'<hierarchy><node text="Bottom" resource-id="bottom" class="TextView" '
            b'package="android" clickable="true" enabled="true" '
            b'visible-to-user="true" bounds="[0,2696][1256,2808]"/></hierarchy>'
        )

        with self.assertRaises(MobileAgentError) as raised:
            self.locator.locate(
                nodes,
                UiSelector.from_dict({"strategy": "text", "value": "Bottom"}),
                1256,
                2808,
            )

        self.assertEqual("TARGET_OUT_OF_BOUNDS", raised.exception.code)
        self.assertEqual(2752, raised.exception.details["tap_y"])
        self.assertLess(raised.exception.details["safe_bottom"], 2752)

    def test_rejects_tap_center_inside_top_system_margin(self) -> None:
        nodes = self.parser.parse(
            b'<hierarchy><node text="Display and brightness" resource-id="android:id/title" '
            b'class="TextView" package="com.android.settings" clickable="true" enabled="true" '
            b'visible-to-user="true" bounds="[0,0][1256,112]"/></hierarchy>'
        )

        with self.assertRaises(MobileAgentError) as raised:
            self.locator.locate(
                nodes,
                UiSelector.from_dict(
                    {"strategy": "text", "value": "Display and brightness"}
                ),
                1256,
                2808,
            )

        self.assertEqual("TARGET_OUT_OF_BOUNDS", raised.exception.code)
        self.assertEqual(56, raised.exception.details["tap_y"])
        self.assertGreater(raised.exception.details["safe_top"], 56)

    def test_clamps_partially_obscured_target_to_safe_clickable_region(self) -> None:
        nodes = self.parser.parse(
            b'<hierarchy><node text="Bluetooth" resource-id="dashboard_tile" '
            b'class="LinearLayout" package="com.android.settings" clickable="true" '
            b'enabled="true" visible-to-user="true" bounds="[0,46][1256,214]"/>'
            b'</hierarchy>'
        )

        match = self.locator.locate(
            nodes,
            UiSelector.from_dict({"strategy": "text", "value": "Bluetooth"}),
            1256,
            2808,
        )

        self.assertEqual(628, match.tap_x)
        self.assertEqual(191, match.tap_y)
