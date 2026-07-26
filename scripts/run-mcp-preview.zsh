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
readonly KEYCHAIN_ACCOUNT="${USER:-mobile-agent}"
readonly RUNTIME_KEYCHAIN_SERVICE="mobile-agent.preview.runtime.${MCP_NAME}"
readonly REGISTRATION_STAMP="${DATA_DIR}/.mcp-preview-registration"

CHECK_ONLY=false
OPEN_CODEX=true
REFRESH_MCP=false
FORGET_SECRETS=false
MCP_REGISTRATION_CHANGED=false
RUNTIME_PID=""

usage() {
  print -r -- "Usage: ${SCRIPT_NAME} [--check] [--no-open] [--refresh-mcp] [--forget-secrets]"
  print -r -- ""
  print -r -- "  --check           Validate prerequisites without reading secrets or changing state."
  print -r -- "  --no-open         Do not open Codex when it is not already running."
  print -r -- "  --refresh-mcp     Re-register MCP configuration without rotating stored tokens."
  print -r -- "  --forget-secrets  Delete preview secrets from macOS Keychain, then exit."
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

keychain_read() {
  /usr/bin/security find-generic-password \
    -a "$KEYCHAIN_ACCOUNT" -s "$1" -w 2>/dev/null
}

keychain_write() {
  /usr/bin/security add-generic-password \
    -a "$KEYCHAIN_ACCOUNT" -s "$1" -w "$2" -U >/dev/null
}

keychain_delete() {
  /usr/bin/security delete-generic-password \
    -a "$KEYCHAIN_ACCOUNT" -s "$1" >/dev/null 2>&1 || true
}

base_url_port() {
  "$1" - "$BASE_URL" <<'PY'
import sys
from urllib.parse import urlparse

parsed = urlparse(sys.argv[1])
print(parsed.port or 80)
PY
}

stop_existing_runtime() {
  local port_number="$1"
  local listener_output
  local -a listener_pids
  local listener_pid
  local listener_command

  listener_output="$(/usr/sbin/lsof -nP -tiTCP:"${port_number}" -sTCP:LISTEN 2>/dev/null || true)"
  [[ -n "$listener_output" ]] || return
  listener_pids=("${(@f)listener_output}")

  for listener_pid in "${listener_pids[@]}"; do
    listener_command="$(/bin/ps -p "$listener_pid" -o command= 2>/dev/null || true)"
    if [[ "$listener_command" != *"mobile_agent.api.server"* ]]; then
      fail "port ${port_number} is used by another process (pid ${listener_pid}); refusing to stop it"
    fi
  done

  print -r -- "Stopping previous Mobile Agent Runtime on port ${port_number}..."
  for listener_pid in "${listener_pids[@]}"; do
    kill -TERM "$listener_pid" >/dev/null 2>&1 || true
  done
  for attempt in {1..40}; do
    local any_alive=false
    for listener_pid in "${listener_pids[@]}"; do
      if kill -0 "$listener_pid" >/dev/null 2>&1; then
        any_alive=true
        break
      fi
    done
    if ! $any_alive && \
      ! /usr/sbin/lsof -nP -tiTCP:"${port_number}" -sTCP:LISTEN >/dev/null 2>&1; then
      return
    fi
    sleep 0.1
  done
  fail "previous Mobile Agent Runtime did not stop within 4 seconds"
}

registration_fingerprint() {
  "$1" - "$PROJECT_ROOT" "$BASE_URL" "$RESOLVED_PYTHON" "$MCP_NAME" <<'PY'
import hashlib
import sys
from pathlib import Path

root = Path(sys.argv[1])
catalog_files = (
    root / "runtime/mobile_agent/mcp/api_client.py",
    root / "runtime/mobile_agent/mcp/server.py",
    root / "runtime/mobile_agent/mcp/tools.py",
    root / "contracts/schemas/mcp-tool-inputs.schema.json",
)
digest = hashlib.sha256()
for value in sys.argv[1:]:
    digest.update(value.encode())
    digest.update(b"\0")
for path in catalog_files:
    digest.update(path.relative_to(root).as_posix().encode())
    digest.update(b"\0")
    digest.update(path.read_bytes())
    digest.update(b"\0")
print(digest.hexdigest())
PY
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
    --refresh-mcp)
      REFRESH_MCP=true
      ;;
    --forget-secrets)
      FORGET_SECRETS=true
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
require_executable /usr/bin/security
require_executable /usr/sbin/lsof
[[ -f "$MODEL_CONFIG" ]] || fail "model config not found: $MODEL_CONFIG"
[[ "$BASE_URL" == "http://127.0.0.1:"* || "$BASE_URL" == "http://localhost:"* ]] || \
  fail "MCP base URL must use HTTP loopback"
readonly MODEL_SECRET_ENV_NAME="$(validate_model_config "$RESOLVED_PYTHON")"
readonly MODEL_KEYCHAIN_SERVICE="mobile-agent.preview.model.${MCP_NAME}.${MODEL_SECRET_ENV_NAME}"

if $CHECK_ONLY; then
  print -r -- "Mobile Agent MCP preview prerequisites are ready."
  print -r -- "Project: $PROJECT_ROOT"
  print -r -- "Model config: $MODEL_CONFIG"
  print -r -- "ADB: $ADB_PATH"
  print -r -- "Codex: $CODEX_BIN"
  exit 0
fi

if $FORGET_SECRETS; then
  keychain_delete "$MODEL_KEYCHAIN_SERVICE"
  keychain_delete "$RUNTIME_KEYCHAIN_SERVICE"
  [[ ! -f "$REGISTRATION_STAMP" ]] || /bin/rm -f "$REGISTRATION_STAMP"
  print -r -- "Removed Mobile Agent preview secrets from macOS Keychain."
  exit 0
fi

MODEL_SECRET="${(P)MODEL_SECRET_ENV_NAME-}"
if [[ -z "$MODEL_SECRET" ]]; then
  MODEL_SECRET="$(keychain_read "$MODEL_KEYCHAIN_SERVICE" || true)"
fi
if [[ -z "$MODEL_SECRET" ]]; then
  [[ -t 0 ]] || fail "${MODEL_SECRET_ENV_NAME} is absent from the environment and macOS Keychain"
  print -r -- "The model API key will be stored in your macOS login Keychain."
  read -r -s "MODEL_SECRET?Model API key (${MODEL_SECRET_ENV_NAME}): "
  print
  [[ -n "$MODEL_SECRET" ]] || fail "model API key cannot be empty"
  keychain_write "$MODEL_KEYCHAIN_SERVICE" "$MODEL_SECRET"
fi
[[ -n "$MODEL_SECRET" ]] || fail "model API key cannot be empty"
export "${MODEL_SECRET_ENV_NAME}=${MODEL_SECRET}"
unset MODEL_SECRET

RUNTIME_API_TOKEN="$(keychain_read "$RUNTIME_KEYCHAIN_SERVICE" || true)"
if [[ -z "$RUNTIME_API_TOKEN" ]]; then
  RUNTIME_API_TOKEN="$("$RESOLVED_PYTHON" -c 'import secrets; print(secrets.token_urlsafe(32))')"
  keychain_write "$RUNTIME_KEYCHAIN_SERVICE" "$RUNTIME_API_TOKEN"
  REFRESH_MCP=true
fi
readonly RUNTIME_API_TOKEN

/bin/mkdir -p "$DATA_DIR"
/bin/chmod 700 "$DATA_DIR"
readonly EXPECTED_REGISTRATION="$(registration_fingerprint "$RESOLVED_PYTHON")"
CURRENT_REGISTRATION=""
if [[ -f "$REGISTRATION_STAMP" ]]; then
  CURRENT_REGISTRATION="$(<"$REGISTRATION_STAMP")"
fi

if ! "$CODEX_BIN" mcp get "$MCP_NAME" >/dev/null 2>&1; then
  REFRESH_MCP=true
fi

if [[ "$CURRENT_REGISTRATION" != "$EXPECTED_REGISTRATION" ]]; then
  REFRESH_MCP=true
fi

if $REFRESH_MCP; then
  if "$CODEX_BIN" mcp get "$MCP_NAME" >/dev/null 2>&1; then
    "$CODEX_BIN" mcp remove "$MCP_NAME" >/dev/null
  fi
  "$CODEX_BIN" mcp add "$MCP_NAME" \
    --env "PYTHONPATH=${PROJECT_ROOT}/runtime" \
    --env "MOBILE_AGENT_MCP_BASE_URL=${BASE_URL}" \
    --env "MOBILE_AGENT_API_TOKEN=${RUNTIME_API_TOKEN}" \
    -- "$RESOLVED_PYTHON" -m mobile_agent.mcp >/dev/null
  print -r -- "$EXPECTED_REGISTRATION" >| "$REGISTRATION_STAMP"
  /bin/chmod 600 "$REGISTRATION_STAMP"
  MCP_REGISTRATION_CHANGED=true
  print -r -- "Registered Codex MCP server: $MCP_NAME"
else
  print -r -- "Reusing existing Codex MCP registration and stable Runtime token."
fi

readonly BASE_PORT="$(base_url_port "$RESOLVED_PYTHON")"
stop_existing_runtime "$BASE_PORT"
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
  if codex_is_running; then
    if $MCP_REGISTRATION_CHANGED; then
      print -r -- "Codex is running with a cached MCP environment."
      print -r -- "Restart Codex once, then create a new thread. Later Runtime restarts reuse the stable token."
    else
      print -r -- "Codex is already running; no application restart is required."
    fi
  else
    /usr/bin/open -a ChatGPT
    print -r -- "Codex opened."
  fi
fi
print -r -- "Keep this terminal open. Press Ctrl+C to stop Runtime."

wait "$RUNTIME_PID"
RUNTIME_PID=""
