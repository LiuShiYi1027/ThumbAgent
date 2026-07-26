#!/bin/zsh

set -eu
unsetopt XTRACE

readonly PROJECT_ROOT="${0:A:h:h}"
readonly MCP_NAME="${MOBILE_AGENT_MCP_NAME:-mobile-agent}"
readonly CODEX_CONFIG="${CODEX_HOME:-${HOME}/.codex}/config.toml"
readonly PYTHON_BIN="${MOBILE_AGENT_PYTHON_BIN:-python3.11}"

if (( $# == 0 )); then
  print -u2 -r -- "Usage: ${0:t} --suite <suite.json> --task <scenario_id=task_id> [...]"
  exit 2
fi

[[ -f "$CODEX_CONFIG" ]] || {
  print -u2 -r -- "Codex config not found: $CODEX_CONFIG"
  exit 1
}

readonly RESOLVED_PYTHON="$(command -v "$PYTHON_BIN")"
readonly CONFIG_VALUES="$($RESOLVED_PYTHON - "$CODEX_CONFIG" "$MCP_NAME" <<'PY'
import sys
import tomllib
from pathlib import Path

path = Path(sys.argv[1])
name = sys.argv[2]
config = tomllib.loads(path.read_text(encoding="utf-8"))
server = config.get("mcp_servers", {}).get(name, {})
environment = server.get("env", {}) if isinstance(server, dict) else {}
token = environment.get("MOBILE_AGENT_API_TOKEN", "")
base_url = environment.get("MOBILE_AGENT_MCP_BASE_URL", "http://127.0.0.1:8765")
if not isinstance(token, str) or not token:
    raise SystemExit(f"MCP server {name!r} has no MOBILE_AGENT_API_TOKEN")
if base_url not in {"http://127.0.0.1:8765", "http://localhost:8765"}:
    raise SystemExit("MCP Runtime URL must be the supported loopback preview endpoint")
print(token)
print(base_url)
PY
)"

readonly RUNTIME_API_TOKEN="${CONFIG_VALUES%%$'\n'*}"
readonly BASE_URL="${CONFIG_VALUES#*$'\n'}"

MOBILE_AGENT_API_TOKEN="$RUNTIME_API_TOKEN" \
PYTHONPATH="${PROJECT_ROOT}/runtime" \
  "$RESOLVED_PYTHON" -m mobile_agent.cli.evaluation_suite_report \
  --base-url "$BASE_URL" "$@"
