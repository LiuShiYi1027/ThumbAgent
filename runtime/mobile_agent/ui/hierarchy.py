"""Classify whether a parsed UI hierarchy is usable for semantic Agent actions.

A dump is empty when no visible node can be addressed by the locator:
it has no text, content description, hint, or resource id. That catches
skeleton FrameLayout dumps without treating a resource_id-only EditText
as empty. The model-facing ui_summary still filters to labeled nodes via
is_semantic_candidate.
"""

from __future__ import annotations

from mobile_agent.ui.model import UiNode


def is_semantic_candidate(node: UiNode) -> bool:
    """Return True when a node could appear in the model-facing UI summary."""

    if not node.visible:
        return False
    return bool(
        node.text.strip() or node.content_description.strip() or node.hint.strip()
    )


def is_locatable_node(node: UiNode) -> bool:
    """Return True when UiLocator could match this visible node."""

    if not node.visible:
        return False
    return bool(
        node.text.strip()
        or node.content_description.strip()
        or node.hint.strip()
        or node.resource_id.strip()
    )


def semantic_candidate_count(nodes: list[UiNode]) -> int:
    """Count visible nodes that carry at least one human-facing label."""

    return sum(1 for node in nodes if is_semantic_candidate(node))


def locatable_node_count(nodes: list[UiNode]) -> int:
    """Count visible nodes that a selector could address."""

    return sum(1 for node in nodes if is_locatable_node(node))


def hierarchy_is_empty(nodes: list[UiNode]) -> bool:
    """Return True when the hierarchy has no locatable nodes."""

    return locatable_node_count(nodes) == 0
