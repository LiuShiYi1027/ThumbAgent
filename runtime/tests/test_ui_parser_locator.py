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
