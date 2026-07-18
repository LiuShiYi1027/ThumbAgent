"""UI hierarchy domain values and selector validation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from mobile_agent.domain.errors import ErrorCategory, MobileAgentError


class SelectorStrategy(str, Enum):
    RESOURCE_ID = "resource_id"
    TEXT = "text"
    CONTENT_DESCRIPTION = "content_description"


class MatchMode(str, Enum):
    EXACT = "exact"
    CONTAINS = "contains"


@dataclass(frozen=True, slots=True)
class Bounds:
    left: int
    top: int
    right: int
    bottom: int

    def __post_init__(self) -> None:
        if self.left < 0 or self.top < 0 or self.right <= self.left or self.bottom <= self.top:
            raise ValueError("invalid bounds")

    @property
    def center(self) -> tuple[int, int]:
        return ((self.left + self.right) // 2, (self.top + self.bottom) // 2)

    def within(self, width: int, height: int) -> bool:
        return self.right <= width and self.bottom <= height

    def to_dict(self) -> dict[str, int]:
        return {
            "left": self.left,
            "top": self.top,
            "right": self.right,
            "bottom": self.bottom,
        }


@dataclass(frozen=True, slots=True)
class UiNode:
    node_id: str
    parent_id: str | None
    depth: int
    text: str
    resource_id: str
    content_description: str
    class_name: str
    package: str
    clickable: bool
    enabled: bool
    visible: bool
    bounds: Bounds
    schema_version: str = "1.0.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "node_id": self.node_id,
            "parent_id": self.parent_id,
            "depth": self.depth,
            "text": self.text,
            "resource_id": self.resource_id,
            "content_description": self.content_description,
            "class_name": self.class_name,
            "package": self.package,
            "clickable": self.clickable,
            "enabled": self.enabled,
            "visible": self.visible,
            "bounds": self.bounds.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class SelectorPredicate:
    strategy: SelectorStrategy
    value: str
    match: MatchMode = MatchMode.EXACT

    def to_dict(self) -> dict[str, str]:
        return {"strategy": self.strategy.value, "value": self.value, "match": self.match.value}


@dataclass(frozen=True, slots=True)
class UiSelector(SelectorPredicate):
    clickable: bool | None = None
    enabled: bool = True
    resolve_clickable_ancestor: bool = False
    ancestor_path: tuple[SelectorPredicate, ...] = ()
    package: str | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "UiSelector":
        allowed = {
            "strategy",
            "value",
            "match",
            "clickable",
            "enabled",
            "resolve_clickable_ancestor",
            "ancestor_path",
            "package",
        }
        unknown_fields = sorted(str(key) for key in set(payload) - allowed)
        if unknown_fields:
            cls._invalid("unknown_fields", unknown_fields=unknown_fields)
        try:
            strategy = SelectorStrategy(payload["strategy"])
            value = payload["value"]
            match = MatchMode(payload.get("match", "exact"))
        except (KeyError, ValueError, TypeError):
            cls._invalid("strategy_value_match")
        if not isinstance(value, str) or not value or len(value) > 1024:
            cls._invalid("value")
        clickable = payload.get("clickable")
        enabled = payload.get("enabled", True)
        resolve = payload.get("resolve_clickable_ancestor", False)
        package = payload.get("package")
        if clickable is not None and not isinstance(clickable, bool):
            cls._invalid("clickable")
        if not isinstance(enabled, bool) or not isinstance(resolve, bool):
            cls._invalid("enabled_or_resolve_clickable_ancestor")
        if package is not None and (
            not isinstance(package, str) or not package or len(package) > 255
        ):
            cls._invalid("package")
        raw_path = payload.get("ancestor_path", [])
        if not isinstance(raw_path, list) or len(raw_path) > 8:
            cls._invalid("ancestor_path")
        ancestors: list[SelectorPredicate] = []
        for item in raw_path:
            if not isinstance(item, dict) or set(item) - {"strategy", "value", "match"}:
                cls._invalid("ancestor_path_item")
            try:
                ancestor_value = item["value"]
                if (
                    not isinstance(ancestor_value, str)
                    or not ancestor_value
                    or len(ancestor_value) > 1024
                ):
                    raise ValueError
                ancestors.append(
                    SelectorPredicate(
                        SelectorStrategy(item["strategy"]),
                        ancestor_value,
                        MatchMode(item.get("match", "exact")),
                    )
                )
            except (KeyError, ValueError, TypeError):
                cls._invalid("ancestor_path_item")
        return cls(strategy, value, match, clickable, enabled, resolve, tuple(ancestors), package)

    def to_dict(self) -> dict[str, Any]:
        # NOTE: Cannot use zero-arg super() here.  @dataclass(slots=True)
        # returns a new class object, but the super() closure's __class__
        # cell still references the original (pre-slots) class, causing
        # TypeError: super(type, obj): obj must be an instance or subtype
        # of type.  Calling the parent method directly sidesteps this.
        payload: dict[str, Any] = SelectorPredicate.to_dict(self)
        payload.update(
            {
                "enabled": self.enabled,
                "resolve_clickable_ancestor": self.resolve_clickable_ancestor,
                "ancestor_path": [item.to_dict() for item in self.ancestor_path],
            }
        )
        if self.clickable is not None:
            payload["clickable"] = self.clickable
        if self.package is not None:
            payload["package"] = self.package
        return payload

    @staticmethod
    def _invalid(field: str, *, unknown_fields: list[str] | None = None) -> None:
        raise MobileAgentError(
            code="INVALID_ARGUMENT",
            category=ErrorCategory.VALIDATION,
            message=f"无效的 UI Selector：{field}",
            details={"field": field, "unknown_fields": unknown_fields or []},
        )


@dataclass(frozen=True, slots=True)
class UiMatch:
    selector: UiSelector
    matched_node: UiNode
    target_node: UiNode
    tap_x: int
    tap_y: int
    schema_version: str = "1.0.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "selector": self.selector.to_dict(),
            "matched_node": self.matched_node.to_dict(),
            "target_node": self.target_node.to_dict(),
            "tap_x": self.tap_x,
            "tap_y": self.tap_y,
        }
