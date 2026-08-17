"""Generate TypeScript contract types from JSON Schemas for the desktop app.

Schemas under contracts/schemas/ are the single source of truth. This script
emits deterministic TypeScript files into contracts/generated/typescript/ for
the desktop workbench. Use `--check` in gates to fail on drift between the
schemas and the committed generated files.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS_DIR = ROOT / "contracts" / "schemas"
OUT_DIR = ROOT / "contracts" / "generated" / "typescript"

# Desktop-consumed subset, in deterministic emission order.
SCHEMA_NAMES = (
    "action-result",
    "agent-action-feedback",
    "agent-decision",
    "agent-goal-acceptance",
    "agent-goal-spec",
    "agent-observation-summary",
    "agent-step-result",
    "apk-install-result",
    "app-inspection-result",
    "app-lifecycle-result",
    "app-removal-result",
    "app-runtime-state",
    "artifact",
    "device",
    "device-log-capture-result",
    "device-performance-snapshot",
    "device-performance-snapshot-result",
    "diagnostic-bundle-result",
    "local-data-cleanup-result",
    "navigation-result",
    "observation",
    "runtime-readiness",
    "skill-result",
    "task-event",
    "task-execution",
    "task-run",
    "ui-match",
    "ui-node",
    "ui-selector",
)

HEADER = (
    "/**\n"
    " * Generated from contracts/schemas/{name}.schema.json by\n"
    " * scripts/generate_ts_contracts.py. Do not edit manually;\n"
    " * run `make contracts` and commit the result.\n"
    " */\n"
)


def pascal_case(name: str) -> str:
    """Convert snake/kebab/space-separated identifiers to PascalCase type names."""

    parts = re.split(r"[^0-9A-Za-z]+", name)
    return "".join(part[:1].upper() + part[1:] for part in parts if part)


def literal_ts(value: Any) -> str:
    """Render a JSON literal as a TypeScript literal."""

    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return repr(value)
    return json.dumps(value, ensure_ascii=False)


def quote_key(key: str) -> str:
    """Quote object keys that are not plain TypeScript identifiers."""

    if key.replace("_", "a").replace("$", "a").isalnum() and not key[:1].isdigit():
        return key
    return json.dumps(key)


class FileContext:
    """Track cross-file imports while rendering one output file."""

    def __init__(self, own_name: str) -> None:
        self.own_name = own_name
        self.imports: dict[str, set[str]] = {}

    def add_import(self, module: str, type_name: str) -> None:
        """Record an external type import for the file header."""

        self.imports.setdefault(module, set()).add(type_name)


def ref_type(ref: str, ctx: FileContext) -> str:
    """Resolve a local $defs or sibling-schema $ref to a type name."""

    if ref.startswith("#/$defs/"):
        return pascal_case(ref.rsplit("/", 1)[1])
    if ref.endswith(".schema.json"):
        target = ref[: -len(".schema.json")]
        type_name = pascal_case(target)
        ctx.add_import(f"./{target}", type_name)
        return type_name
    raise ValueError(f"unsupported $ref: {ref}")


def ts_type(schema: dict[str, Any], ctx: FileContext, indent: int) -> str:
    """Map a JSON Schema node to a TypeScript type expression."""

    if "$ref" in schema:
        return ref_type(schema["$ref"], ctx)
    if "const" in schema:
        return literal_ts(schema["const"])
    if "enum" in schema:
        return " | ".join(literal_ts(item) for item in schema["enum"])
    for combiner in ("oneOf", "anyOf"):
        if combiner in schema:
            return " | ".join(ts_type(item, ctx, indent) for item in schema[combiner])
    if "allOf" in schema:
        # $ref + local constraint refinement (e.g. a stricter selector). The
        # intersection keeps the referenced type; items that carry no
        # renderable shape (unknown) or conditional if/then branches are
        # dropped rather than degrading the whole type.
        parts = [
            ts_type(item, ctx, indent) for item in schema["allOf"] if "if" not in item
        ]
        parts = [part for part in parts if part != "unknown"]
        if parts:
            return " & ".join(parts)
        return "unknown"

    kind = schema.get("type")
    if isinstance(kind, list):
        return " | ".join(
            ts_type({**schema, "type": item}, ctx, indent) for item in kind
        )
    if kind == "string":
        return "string"
    if kind in {"integer", "number"}:
        return "number"
    if kind == "boolean":
        return "boolean"
    if kind == "null":
        return "null"
    if kind == "array":
        item = ts_type(schema.get("items", {}), ctx, indent)
        if " | " in item or item.startswith("{"):
            return f"Array<{item}>"
        return f"{item}[]"
    if kind == "object":
        if "properties" not in schema:
            return "Record<string, unknown>"
        return render_object(schema, ctx, indent)
    if kind is None:
        return "unknown"
    raise ValueError(f"unsupported schema type: {kind}")


def render_object(schema: dict[str, Any], ctx: FileContext, indent: int) -> str:
    """Render an object schema as a multi-line TypeScript object literal."""

    required = set(schema.get("required", []))
    lines = ["{"]
    pad = " " * (indent + 2)
    for key, prop in schema["properties"].items():
        optional = "" if key in required else "?"
        lines.append(f"{pad}{quote_key(key)}{optional}: {ts_type(prop, ctx, indent + 2)};")
    lines.append(" " * indent + "}")
    return "\n".join(lines)


def render_interface(name: str, schema: dict[str, Any], ctx: FileContext) -> str:
    """Render a named exported interface for a root or $defs object schema."""

    if schema.get("type") != "object" or "properties" not in schema:
        raise ValueError(f"{name} must be an object schema with properties")
    lines: list[str] = []
    description = schema.get("description")
    if isinstance(description, str) and description.strip():
        lines.append(f"/** {description.strip()} */")
    body = render_object(schema, ctx, 0)
    lines.append(f"export interface {name} {body}")
    return "\n".join(lines)


def generate_file(name: str, schema: dict[str, Any]) -> str:
    """Generate the full TypeScript module text for one schema."""

    ctx = FileContext(name)
    sections: list[str] = []
    # The file name is the canonical type name: cross-file $ref imports resolve
    # from file names, and several schema titles ("APK Install Result") would
    # otherwise diverge from what importers expect.
    root_name = pascal_case(name)
    for def_key, def_schema in schema.get("$defs", {}).items():
        sections.append(render_interface(pascal_case(def_key), def_schema, ctx))
    sections.append(render_interface(root_name, schema, ctx))

    header = HEADER.format(name=name)
    imports = "".join(
        f'import type {{ {", ".join(sorted(types))} }} from "{module}";\n'
        for module, types in sorted(ctx.imports.items())
    )
    body = "\n\n".join(sections)
    return f"{header}{imports}\n{body}\n"


def expected_files() -> dict[Path, str]:
    """Generate all expected output files in memory."""

    outputs: dict[Path, str] = {}
    for name in SCHEMA_NAMES:
        schema_path = SCHEMAS_DIR / f"{name}.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        outputs[OUT_DIR / f"{name}.ts"] = generate_file(name, schema)
    return outputs


def write_files(outputs: dict[Path, str]) -> None:
    """Write generated files, creating the output directory as needed."""

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for path, content in outputs.items():
        path.write_text(content, encoding="utf-8")


def check_files(outputs: dict[Path, str]) -> list[str]:
    """Return drift errors when committed files differ from generated output."""

    errors: list[str] = []
    for path, content in sorted(outputs.items()):
        if not path.is_file():
            errors.append(f"{path.relative_to(ROOT)}: missing generated file")
        elif path.read_text(encoding="utf-8") != content:
            errors.append(f"{path.relative_to(ROOT)}: out of date, run `make contracts`")
    if OUT_DIR.is_dir():
        extras = sorted(
            path.relative_to(ROOT)
            for path in OUT_DIR.rglob("*.ts")
            if path not in outputs
        )
        for extra in extras:
            errors.append(f"{extra}: unknown file in generated directory")
    return errors


def main() -> int:
    """Generate or verify TypeScript contract types."""

    check = "--check" in sys.argv[1:]
    outputs = expected_files()
    if check:
        errors = check_files(outputs)
        for error in errors:
            print(error, file=sys.stderr)
        return 1 if errors else 0
    write_files(outputs)
    for path in sorted(outputs):
        print(f"generated {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
