"""Bounded parser for untrusted UIAutomator XML."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from mobile_agent.domain.errors import ErrorCategory, MobileAgentError
from mobile_agent.ui.model import Bounds, UiNode


class UiHierarchyParser:
    MAX_BYTES = 5_242_880
    MAX_NODES = 10_000
    MAX_DEPTH = 64
    MAX_ATTRIBUTE_LENGTH = 1024
    _BOUNDS = re.compile(r"^\[(\d+),(\d+)\]\[(\d+),(\d+)\]$")

    def parse(self, data: bytes) -> list[UiNode]:
        if not data or len(data) > self.MAX_BYTES:
            self._invalid("UI hierarchy 大小无效")
        upper = data.upper()
        if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
            self._invalid("UI hierarchy 包含禁止的实体声明")
        try:
            root = ET.fromstring(data)
        except ET.ParseError as error:
            raise MobileAgentError(
                code="UI_TREE_INVALID",
                category=ErrorCategory.DEVICE,
                message="UI hierarchy XML 无法解析",
            ) from error
        nodes: list[UiNode] = []

        def visit(element: ET.Element, parent_id: str | None, depth: int, path: str) -> None:
            if depth > self.MAX_DEPTH or len(nodes) >= self.MAX_NODES:
                self._invalid("UI hierarchy 超过安全限制")
            if element.tag == "node":
                if self._is_degenerate(element.attrib):
                    # 真机/AOSP 实测：系统会给隐藏视图（如手势导航区）留下
                    # 零/负面积的退化 bounds（如 [0,2382][1080,2337]）。
                    # 这类节点不可见不可交互，跳过整棵子树而不是让整棵树失效。
                    return
                node_id = path
                nodes.append(self._node(element.attrib, node_id, parent_id, depth))
                current_parent = node_id
            else:
                current_parent = parent_id
            for index, child in enumerate(list(element)):
                visit(child, current_parent, depth + 1, f"{path}/{index}")

        visit(root, None, 0, "0")
        return nodes

    def _is_degenerate(self, attributes: dict[str, str]) -> bool:
        """bounds 合法但面积为零/负（含隐藏系统视图），区别于格式损坏。"""
        match = self._BOUNDS.fullmatch(attributes.get("bounds", ""))
        if not match:
            return False
        x1, y1, x2, y2 = (int(value) for value in match.groups())
        return x1 >= 0 and y1 >= 0 and (x2 <= x1 or y2 <= y1)

    def _node(
        self, attributes: dict[str, str], node_id: str, parent_id: str | None, depth: int
    ) -> UiNode:
        def text(name: str) -> str:
            value = attributes.get(name, "")
            return value[: self.MAX_ATTRIBUTE_LENGTH]

        match = self._BOUNDS.fullmatch(attributes.get("bounds", ""))
        if not match:
            self._invalid("UI 节点 bounds 无效")
        try:
            bounds = Bounds(*(int(value) for value in match.groups()))
        except ValueError as error:
            raise MobileAgentError(
                code="UI_TREE_INVALID",
                category=ErrorCategory.DEVICE,
                message="UI 节点 bounds 无效",
            ) from error
        return UiNode(
            node_id=node_id,
            parent_id=parent_id,
            depth=depth,
            text=text("text"),
            resource_id=text("resource-id"),
            content_description=text("content-desc"),
            hint=text("hint"),
            class_name=text("class"),
            package=text("package"),
            clickable=attributes.get("clickable") == "true",
            enabled=attributes.get("enabled", "true") == "true",
            visible=attributes.get("visible-to-user", "true") == "true",
            bounds=bounds,
        )

    @staticmethod
    def _invalid(message: str) -> None:
        raise MobileAgentError(
            code="UI_TREE_INVALID",
            category=ErrorCategory.DEVICE,
            message=message,
        )
