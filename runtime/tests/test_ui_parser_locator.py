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

        invalid = b'<hierarchy><node bounds="[10,10][5,5]"/></hierarchy>'
        with self.assertRaises(MobileAgentError) as bounds:
            self.parser.parse(invalid)
        self.assertEqual("UI_TREE_INVALID", bounds.exception.code)

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
