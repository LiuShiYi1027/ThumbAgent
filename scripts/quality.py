"""Dependency-free bootstrap quality checks for ITER-0001.

When Ruff and Pyright are added to the locked development environment, Makefile
targets will call them. Until then this script enforces formatting invariants,
AST validity, import boundaries, and complete function annotations.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOTS = [ROOT / "runtime/mobile_agent", ROOT / "runtime/tests", ROOT / "scripts"]


def python_files() -> list[Path]:
    return sorted(path for root in PYTHON_ROOTS for path in root.rglob("*.py"))


def format_check() -> list[str]:
    errors: list[str] = []
    for path in python_files():
        text = path.read_text(encoding="utf-8")
        if "\t" in text:
            errors.append(f"{path.relative_to(ROOT)}: tabs are not allowed")
        if any(line.rstrip() != line for line in text.splitlines()):
            errors.append(f"{path.relative_to(ROOT)}: trailing whitespace")
        if text and not text.endswith("\n"):
            errors.append(f"{path.relative_to(ROOT)}: missing final newline")
    return errors


def parse_all() -> tuple[dict[Path, ast.Module], list[str]]:
    trees: dict[Path, ast.Module] = {}
    errors: list[str] = []
    for path in python_files():
        try:
            trees[path] = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as error:
            errors.append(f"{path.relative_to(ROOT)}:{error.lineno}: {error.msg}")
    return trees, errors


def lint_check(trees: dict[Path, ast.Module]) -> list[str]:
    errors = format_check()
    domain_root = ROOT / "runtime/mobile_agent/domain"
    forbidden = ("fastapi", "sqlalchemy", "mobile_agent.devices", "mobile_agent.api")
    for path, tree in trees.items():
        if not path.is_relative_to(domain_root):
            continue
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                if name.startswith(forbidden):
                    errors.append(
                        f"{path.relative_to(ROOT)}:{node.lineno}: forbidden domain import {name}"
                    )
    return errors


def annotation_check(trees: dict[Path, ast.Module]) -> list[str]:
    errors: list[str] = []
    source_root = ROOT / "runtime/mobile_agent"
    for path, tree in trees.items():
        if not path.is_relative_to(source_root):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name.startswith("__") and node.name.endswith("__"):
                continue
            args = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
            for argument in args:
                if argument.arg in {"self", "cls"}:
                    continue
                if argument.annotation is None:
                    errors.append(
                        f"{path.relative_to(ROOT)}:{node.lineno}: {node.name} argument "
                        f"{argument.arg} lacks annotation"
                    )
            if node.returns is None:
                errors.append(
                    f"{path.relative_to(ROOT)}:{node.lineno}: {node.name} lacks return annotation"
                )
    return errors


def main() -> int:
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    trees, parse_errors = parse_all()
    errors = list(parse_errors)
    if command == "format":
        errors.extend(format_check())
    elif command == "lint":
        errors.extend(lint_check(trees))
    elif command == "typecheck":
        errors.extend(annotation_check(trees))
    else:
        print("usage: quality.py {format|lint|typecheck}", file=sys.stderr)
        return 2
    for error in errors:
        print(error, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

