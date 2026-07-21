#!/bin/zsh

set -eu
setopt pipe_fail
unsetopt BG_NICE XTRACE

readonly SCRIPT_NAME="${0:t}"
readonly PROJECT_ROOT="${0:A:h:h}"
readonly MCP_NAME="${MOBILE_AGENT_MCP_NAME:-mobile-agent}"
readonly BASE_URL="${MOBILE_AGENT_MCP_BASE_URL:-http://127.0.0.1:8765}"
readonly DATA_DIR="${MOBILE_AGENT_DATA_DIR:-/tmp/mobile-agent-demo}"
readonly MODEL_CONFIG="${MOBILE_AGENT_MODEL_CONFIG:-${PROJECT_ROOT}/local/model-provider.json}"
readonly ADB_PATH="${MOBILE_AGENT_ADB_PATH:-/usr/local/platform-tools/adb}"
readonly CODEX_BIN="${MOBILE_AGENT_CODEX_BIN:-/Applications/ChatGPT.app/Contents/Resources/codex}"
readonly PYTHON_BIN="${MOBILE_AGENT_PYTHON_BIN:-python3.11}"

CHECK_ONLY=false
OPEN_CODEX=true
RUNTIME_PID=""

usage() {
  print -r -- "Usage: ${SCRIPT_NAME} [--check] [--no-open]"
  print -r -- ""
  print -r -- "  --check    Validate local prerequisites without reading secrets or changing state."
  print -r -- "  --no-open  Start Runtime without opening the Codex desktop app."
}

fail() {
  print -u2 -r -- "Mobile Agent MCP preview: $1"
  exit 1
}

require_executable() {
  [[ -x "$1" ]] || fail "missing executable: $1"
}

resolve_python() {
  if [[ "$PYTHON_BIN" == */* ]]; then
    [[ -x "$PYTHON_BIN" ]] || fail "Python is not executable: $PYTHON_BIN"
    print -r -- "$PYTHON_BIN"
    return
  fi
  command -v "$PYTHON_BIN" 2>/dev/null || fail "Python is not available: $PYTHON_BIN"
}

validate_model_config() {
  "$1" - "$MODEL_CONFIG" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
try:
    payload = json.loads(path.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError) as error:
    raise SystemExit(f"invalid model config: {error}") from error

expected = {
    "enabled": True,
    "provider": "openai_compatible",
}
for key, value in expected.items():
    if payload.get(key) != value:
        raise SystemExit(f"model config must set {key}={value!r}")
if not isinstance(payload.get("base_url"), str) or not payload["base_url"].startswith(("http://", "https://")):
    raise SystemExit("model config must contain an HTTP(S) base_url")
if not isinstance(payload.get("model"), str) or not payload["model"].strip():
    raise SystemExit("model config must contain a non-empty model")
reference = payload.get("api_key_ref")
if not isinstance(reference, str) or not reference.startswith("env:MOBILE_AGENT_MODEL_SECRET_"):
    raise SystemExit("model config must use an allowed env:MOBILE_AGENT_MODEL_SECRET_* reference")
name = reference.removeprefix("env:")
if not name.replace("_", "").isalnum() or name.upper() != name:
    raise SystemExit("model config contains an invalid model secret environment name")
print(name)
PY
}

codex_is_running() {
  /usr/bin/pgrep -x ChatGPT >/dev/null 2>&1 || /usr/bin/pgrep -x Codex >/dev/null 2>&1
}

cleanup() {
  local exit_code=$?
  trap - EXIT INT TERM
  if [[ -n "$RUNTIME_PID" ]] && kill -0 "$RUNTIME_PID" >/dev/null 2>&1; then
    kill -INT "$RUNTIME_PID" >/dev/null 2>&1 || true
    wait "$RUNTIME_PID" >/dev/null 2>&1 || true
  fi
  exit "$exit_code"
}

while (( $# > 0 )); do
  case "$1" in
    --check)
      CHECK_ONLY=true
      ;;
    --no-open)
      OPEN_CODEX=false
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      usage >&2
      fail "unknown argument: $1"
      ;;
  esac
  shift
done

readonly RESOLVED_PYTHON="$(resolve_python)"
require_executable "$CODEX_BIN"
require_executable "$ADB_PATH"
[[ -f "$MODEL_CONFIG" ]] || fail "model config not found: $MODEL_CONFIG"
[[ "$BASE_URL" == "http://127.0.0.1:"* || "$BASE_URL" == "http://localhost:"* ]] || \
  fail "MCP base URL must use HTTP loopback"
readonly MODEL_SECRET_ENV_NAME="$(validate_model_config "$RESOLVED_PYTHON")"

if $CHECK_ONLY; then
  print -r -- "Mobile Agent MCP preview prerequisites are ready."
  print -r -- "Project: $PROJECT_ROOT"
  print -r -- "Model config: $MODEL_CONFIG"
  print -r -- "ADB: $ADB_PATH"
  print -r -- "Codex: $CODEX_BIN"
  exit 0
fi

if codex_is_running; then
  fail "fully quit Codex/ChatGPT, then run this script again so the rotated MCP token is loaded"
fi

MODEL_SECRET="${(P)MODEL_SECRET_ENV_NAME-}"
if [[ -z "$MODEL_SECRET" ]]; then
  [[ -t 0 ]] || fail "${MODEL_SECRET_ENV_NAME} is required in non-interactive mode"
  read -r -s "MODEL_SECRET?Model API key (${MODEL_SECRET_ENV_NAME}): "
  print
fi
[[ -n "$MODEL_SECRET" ]] || fail "model API key cannot be empty"
export "${MODEL_SECRET_ENV_NAME}=${MODEL_SECRET}"
unset MODEL_SECRET

readonly RUNTIME_API_TOKEN="$("$RESOLVED_PYTHON" -c 'import secrets; print(secrets.token_urlsafe(32))')"

if "$CODEX_BIN" mcp get "$MCP_NAME" >/dev/null 2>&1; then
  "$CODEX_BIN" mcp remove "$MCP_NAME" >/dev/null
fi

"$CODEX_BIN" mcp add "$MCP_NAME" \
  --env "PYTHONPATH=${PROJECT_ROOT}/runtime" \
  --env "MOBILE_AGENT_MCP_BASE_URL=${BASE_URL}" \
  --env "MOBILE_AGENT_API_TOKEN=${RUNTIME_API_TOKEN}" \
  -- "$RESOLVED_PYTHON" -m mobile_agent.mcp >/dev/null

print -r -- "Registered Codex MCP server: $MCP_NAME"
print -r -- "Starting Runtime at $BASE_URL"

trap cleanup EXIT INT TERM
MOBILE_AGENT_DATA_DIR="$DATA_DIR" \
MOBILE_AGENT_MODEL_CONFIG="$MODEL_CONFIG" \
MOBILE_AGENT_ADB_PATH="$ADB_PATH" \
MOBILE_AGENT_API_TOKEN="$RUNTIME_API_TOKEN" \
PYTHONPATH="${PROJECT_ROOT}/runtime" \
  "$RESOLVED_PYTHON" -m mobile_agent.api.server &
RUNTIME_PID=$!

runtime_ready=false
for attempt in {1..40}; do
  if ! kill -0 "$RUNTIME_PID" >/dev/null 2>&1; then
    wait "$RUNTIME_PID" || true
    fail "Runtime exited before becoming ready"
  fi
  if /usr/bin/curl --fail --silent --max-time 1 "${BASE_URL}/v1/readiness" >/dev/null 2>&1; then
    runtime_ready=true
    break
  fi
  sleep 0.25
done
$runtime_ready || fail "Runtime did not become ready within 10 seconds"

print -r -- "Runtime is ready. Web UI: ${BASE_URL}/ui"
if $OPEN_CODEX; then
  /usr/bin/open -a ChatGPT
  print -r -- "Codex opened with the refreshed MCP configuration."
  print -r -- "Create a new Codex thread; existing threads do not dynamically acquire newly registered MCP tools."
fi
print -r -- "Keep this terminal open. Press Ctrl+C to stop Runtime."

wait "$RUNTIME_PID"
RUNTIME_PID=""
