"""Deterministic semantic element matching."""

from __future__ import annotations

from mobile_agent.domain.errors import ErrorCategory, MobileAgentError
from mobile_agent.ui.model import MatchMode, SelectorPredicate, SelectorStrategy, UiMatch, UiNode, UiSelector


class UiLocator:
    def locate(
        self, nodes: list[UiNode], selector: UiSelector, screen_width: int, screen_height: int
    ) -> UiMatch:
        by_id = {node.node_id: node for node in nodes}
        matches = [
            node
            for node in nodes
            if self._matches(node, selector)
            and self._matches_ancestor_path(node, selector.ancestor_path, by_id)
        ]
        if not matches:
            raise MobileAgentError(
                code="TARGET_NOT_FOUND",
                category=ErrorCategory.DEVICE,
                message="未找到目标 UI 元素",
            )
        if len(matches) > 1:
            raise MobileAgentError(
                code="TARGET_AMBIGUOUS",
                category=ErrorCategory.DEVICE,
                message="目标 UI 元素匹配不唯一",
                details={"match_count": len(matches)},
            )
        matched = matches[0]
        target = matched
        if not target.clickable:
            if not selector.resolve_clickable_ancestor:
                raise MobileAgentError(
                    code="TARGET_NOT_CLICKABLE",
                    category=ErrorCategory.DEVICE,
                    message="目标 UI 元素不可点击",
                )
            target = self._nearest_clickable_ancestor(matched, by_id)
        if not target.enabled or not target.visible:
            raise MobileAgentError(
                code="TARGET_NOT_INTERACTABLE",
                category=ErrorCategory.DEVICE,
                message="目标 UI 元素当前不可交互",
            )
        if not target.bounds.within(screen_width, screen_height):
            raise MobileAgentError(
                code="TARGET_OUT_OF_BOUNDS",
                category=ErrorCategory.DEVICE,
                message="目标 UI 元素超出屏幕边界",
            )
        x, original_y = target.bounds.center
        # Tiny synthetic screens used by adapters/tests do not model system UI insets.
        system_margin = max(1, round(screen_height * 0.06)) if screen_height >= 100 else 0
        safe_top = system_margin
        safe_bottom = screen_height - system_margin
        if (not safe_top or original_y > safe_top) and original_y < safe_bottom:
            return UiMatch(selector, matched, target, x, original_y)
        safe_target_top = max(target.bounds.top, safe_top + 1)
        safe_target_bottom = min(target.bounds.bottom, safe_bottom)
        if safe_target_top >= safe_target_bottom and target.bounds.bottom <= safe_top + 1:
            raise MobileAgentError(
                code="TARGET_OUT_OF_BOUNDS",
                category=ErrorCategory.DEVICE,
                message="目标位于屏幕顶部系统区域",
                suggested_action="先滑动使目标进入安全可点击区域",
                details={"tap_y": original_y, "safe_top": safe_top},
            )
        if safe_target_top >= safe_target_bottom:
            raise MobileAgentError(
                code="TARGET_OUT_OF_BOUNDS",
                category=ErrorCategory.DEVICE,
                message="目标位于屏幕底部手势区域",
                suggested_action="先滑动使目标进入安全可点击区域",
                details={"tap_y": original_y, "safe_bottom": safe_bottom},
            )
        y = (safe_target_top + safe_target_bottom) // 2
        return UiMatch(selector, matched, target, x, y)

    def find_all(self, nodes: list[UiNode], selector: UiSelector) -> list[UiNode]:
        by_id = {node.node_id: node for node in nodes}
        return [
            node
            for node in nodes
            if self._matches(node, selector)
            and self._matches_ancestor_path(node, selector.ancestor_path, by_id)
        ]

    @staticmethod
    def _matches(node: UiNode, predicate: SelectorPredicate) -> bool:
        candidate = {
            SelectorStrategy.RESOURCE_ID: node.resource_id,
            SelectorStrategy.TEXT: node.text,
            SelectorStrategy.CONTENT_DESCRIPTION: node.content_description,
        }[predicate.strategy]
        semantic_match = (
            candidate == predicate.value
            if predicate.match is MatchMode.EXACT
            else predicate.value in candidate
        )
        if not semantic_match:
            return False
        if isinstance(predicate, UiSelector):
            if not node.visible:
                return False
            if predicate.package is not None and node.package != predicate.package:
                return False
            if predicate.clickable is not None and node.clickable is not predicate.clickable:
                return False
            if node.enabled is not predicate.enabled:
                return False
        return True

    def _matches_ancestor_path(
        self,
        node: UiNode,
        required: tuple[SelectorPredicate, ...],
        by_id: dict[str, UiNode],
    ) -> bool:
        if not required:
            return True
        ancestors: list[UiNode] = []
        parent_id = node.parent_id
        while parent_id is not None:
            parent = by_id.get(parent_id)
            if parent is None:
                break
            ancestors.append(parent)
            parent_id = parent.parent_id
        ancestors.reverse()
        position = 0
        for requirement in required:
            while position < len(ancestors) and not self._matches(ancestors[position], requirement):
                position += 1
            if position >= len(ancestors):
                return False
            position += 1
        return True

    @staticmethod
    def _nearest_clickable_ancestor(node: UiNode, by_id: dict[str, UiNode]) -> UiNode:
        parent_id = node.parent_id
        while parent_id is not None:
            parent = by_id.get(parent_id)
            if parent is None:
                break
            if parent.clickable:
                return parent
            parent_id = parent.parent_id
        raise MobileAgentError(
            code="TARGET_NOT_CLICKABLE",
            category=ErrorCategory.DEVICE,
            message="目标元素没有可点击祖先",
        )
