from __future__ import annotations

import unittest

# 先装载 Application 层，避免单独跑本文件时踩到 ui.model ↔ domain.action 的环。
import mobile_agent.agent.runner  # noqa: F401

from mobile_agent.ui.hierarchy import (
    hierarchy_is_empty,
    is_locatable_node,
    is_semantic_candidate,
    semantic_candidate_count,
)
from mobile_agent.ui.model import UiNode
from mobile_agent.ui.parser import UiHierarchyParser


def _parse(xml: bytes) -> list[UiNode]:
    return UiHierarchyParser().parse(xml)


class HierarchyEmptinessTests(unittest.TestCase):
    def test_empty_hierarchy_document_is_empty(self) -> None:
        nodes = _parse(
            b'<?xml version="1.0" encoding="UTF-8"?><hierarchy rotation="0"></hierarchy>'
        )
        self.assertEqual([], nodes)
        self.assertTrue(hierarchy_is_empty(nodes))
        self.assertEqual(0, semantic_candidate_count(nodes))

    def test_unlabeled_root_frame_is_empty(self) -> None:
        nodes = _parse(
            b'<?xml version="1.0" encoding="UTF-8"?><hierarchy rotation="0">'
            b'<node text="" resource-id="" class="android.widget.FrameLayout" '
            b'package="com.example.app" clickable="false" enabled="true" '
            b'visible-to-user="true" bounds="[0,0][1080,2400]"/></hierarchy>'
        )
        self.assertEqual(1, len(nodes))
        self.assertFalse(is_semantic_candidate(nodes[0]))
        self.assertFalse(is_locatable_node(nodes[0]))
        self.assertTrue(hierarchy_is_empty(nodes))

    def test_resource_id_only_field_is_not_empty(self) -> None:
        nodes = _parse(
            b'<?xml version="1.0" encoding="UTF-8"?><hierarchy rotation="0">'
            b'<node text="" resource-id="search_box" class="EditText" '
            b'package="com.example.form" clickable="true" enabled="true" '
            b'visible-to-user="true" bounds="[0,0][100,50]"/></hierarchy>'
        )
        self.assertFalse(is_semantic_candidate(nodes[0]))
        self.assertTrue(is_locatable_node(nodes[0]))
        self.assertFalse(hierarchy_is_empty(nodes))

    def test_invisible_labeled_node_does_not_count(self) -> None:
        nodes = _parse(
            b'<?xml version="1.0" encoding="UTF-8"?><hierarchy rotation="0">'
            b'<node text="Hidden" resource-id="secret" class="TextView" '
            b'package="android" clickable="true" enabled="true" '
            b'visible-to-user="false" bounds="[0,0][100,50]"/></hierarchy>'
        )
        self.assertTrue(hierarchy_is_empty(nodes))

    def test_visible_text_is_not_empty(self) -> None:
        nodes = _parse(
            b'<?xml version="1.0" encoding="UTF-8"?><hierarchy rotation="0">'
            b'<node text="Display" resource-id="title" class="TextView" '
            b'package="android" clickable="false" enabled="true" '
            b'visible-to-user="true" bounds="[0,0][100,50]"/></hierarchy>'
        )
        self.assertFalse(hierarchy_is_empty(nodes))
        self.assertEqual(1, semantic_candidate_count(nodes))

    def test_content_description_or_hint_counts(self) -> None:
        described = _parse(
            b'<hierarchy><node text="" content-desc="Search" resource-id="q" '
            b'class="View" package="android" clickable="true" enabled="true" '
            b'visible-to-user="true" bounds="[0,0][100,50]"/></hierarchy>'
        )
        hinted = _parse(
            b'<hierarchy><node text="" hint="Search" resource-id="q" '
            b'class="EditText" package="android" clickable="true" enabled="true" '
            b'visible-to-user="true" bounds="[0,0][100,50]"/></hierarchy>'
        )
        self.assertFalse(hierarchy_is_empty(described))
        self.assertFalse(hierarchy_is_empty(hinted))
