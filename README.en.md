# ThumbAgent

> Local-first platform that gives AI agents a real thumb on mobile devices.

[中文](./README.md) | English

[![CI](https://github.com/LiuShiYi1027/ThumbAgent/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/LiuShiYi1027/ThumbAgent/actions/workflows/ci.yml)

> Note: the [Chinese README](./README.md) is the primary maintained version; this
> English translation may lag behind the latest iteration notes.

A local-first, cross-platform mobile-device Skills platform for AI agents.

## Current Progress

The project has completed ITER-0054 Desktop Settings & Model Provider Onboarding:
the settings page accepts Base URL, model name and timeout directly; the API key is
stored only in the system Keychain (the Runtime config file persists just the
`env:MOBILE_AGENT_MODEL_SECRET_DESKTOP` reference — the secret never touches disk or
any HTTP endpoint), and "Save & Restart" restarts the local Runtime to apply the
configuration, warning first when a task is in flight. The data directory opens in
Finder with one click. The Runtime gains `GET/POST /v1/model-provider/config`
(validated, atomic 0600 writes), while the desktop sidecar owns Keychain access,
child-environment secret injection, and `restart_runtime`.

Earlier, ITER-0053 Manual Takeover (Pause & Resume) shipped: a running agent
task can be paused at a round safe boundary (`POST /v1/task-executions/{task_id}/pause`)
so the user can take over the device directly, then resumed (`/resume`) so the agent
re-observes the current screen and keeps planning. While paused, no device actions are
dispatched and the device lease is retained; the deadline keeps ticking, and expiry or a
cancel request auto-resumes the task into its timeout/cancel path. The event stream gains
`task.pause_requested` / `task.paused` / `task.resumed` (with `takeover` and
`resume_reason`), and the desktop workbench offers pause/resume controls, a takeover
banner, a frozen device-screen panel during takeover, and takeover intervals in reports.

The desktop workbench (Tauri 2) automatically launches and authenticates against the
local Runtime. Its home page shows unified readiness diagnostics and discovered devices,
and supports natural-language task submission, an execution timeline, and full reports.
See [apps/desktop/README.md](./apps/desktop/README.md) for desktop development.
Python 3.11+:

```bash
make check
make run
```

The Runtime listens on `127.0.0.1:8765` by default and provides `/v1/health`,
`/v1/devices`, and `POST /v1/devices/{device_id}/observe`.

## MCP Skills Developer Preview

For local on-device acceptance with macOS + the Codex desktop app, use the one-shot
script:

```bash
./scripts/run-mcp-preview.zsh
```

On first run the script asks for the model key, and stores the model key and a stable
local Runtime token separately in the macOS login Keychain; later runs never ask again.
The script safely stops any old `mobile_agent.api.server` occupying the target port,
reuses unchanged MCP registration, and starts a new Runtime. A running Codex/ChatGPT app
does not need to be closed or reopened. Only on first registration, an explicit
`--refresh-mcp`, or an MCP configuration or Tool Catalog change does a running Codex
need one restart with a fresh task to refresh its cached MCP environment; ordinary
Runtime restarts do not require this.

The model key only enters the Keychain and the Runtime process environment — never the
repository or script output. The script runs in the foreground; press `Ctrl+C` to stop
the Runtime. To only check the Python, ADB, Codex, and model configuration paths without
reading secrets or modifying MCP registration, use:

```bash
./scripts/run-mcp-preview.zsh --check
```

To force-refresh the MCP registration or delete the preview secrets:

```bash
./scripts/run-mcp-preview.zsh --refresh-mcp
./scripts/run-mcp-preview.zsh --forget-secrets
```

Refreshing the registration does not rotate the Keychain token. If the target port is
held by another program, the script refuses to kill it; it only stops processes whose
command line clearly belongs to `mobile_agent.api.server`.

To share one Runtime across Web, CLI, and MCP, start the service with an explicit local
token:

```bash
MOBILE_AGENT_API_TOKEN=<local-random-token> \
MOBILE_AGENT_ADB_PATH=/usr/local/platform-tools/adb \
make run
```

Then configure a stdio server in your MCP host with the same token. See
[mcp-server.example.json](./docs/examples/mcp-server.example.json). The command the MCP
host actually launches is:

```bash
PYTHONPATH=runtime \
MOBILE_AGENT_API_TOKEN=<same-local-random-token> \
python3.11 -m mobile_agent.mcp
```

MCP exposes goal-level tools covering readiness diagnostics, device and installed-app
inspection, application lifecycle, async agent tasks, task query/cancel, redacted logs,
aggregate performance snapshots, diagnostic evidence bundles, performance comparison,
and local artifact retention cleanup. It does not expose ADB, arbitrary shell, arbitrary
file paths, or atomic tools such as `input.tap`. Actions that require confirmation only
accept `confirmed=true` after the MCP host has shown the user the parameters and impact
and obtained confirmation.

After startup, view the unified readiness diagnostics:

```bash
PYTHONPATH=runtime python3.11 -m mobile_agent.cli.runtime_diagnose
```

`GET /v1/readiness` and the Web UI show the Android Gateway, device
connection/authorization, Session, Lease occupancy, and repair suggestions. When ADB is
missing or the path is wrong, the Runtime still starts in diagnostic mode instead of
exiting with `ADB_NOT_FOUND`.

Inspect a single device's current capabilities, risks, confirmation requirements, and
limits:

```bash
PYTHONPATH=runtime python3.11 -m mobile_agent.cli.device_inspect <device_id>
```

MCP also provides the read-only `mobile_list_apps` and `mobile_inspect_app`, which
bounded-list app identifiers and query a single app's version, install source, and
enabled state. They never return APK paths, signatures, permissions, or raw `dumpsys`,
and they never launch or modify apps.

Local APK installation only accepts a single `.apk` inside `<data-dir>/apks`. An
external agent must first call `mobile_prepare_apk_install` to obtain a short-lived
approval containing the file name, size, SHA-256, Manifest package id, and replacement
impact; only after the MCP host shows the user this summary and obtains explicit
confirmation may it call `mobile_install_apk`. Approvals expire after ten minutes and
are single-use by default. The Runtime never downloads URLs and accepts neither split
APKs nor arbitrary ADB arguments.

App uninstall uses a separate two-phase `mobile_prepare_app_uninstall` →
`mobile_uninstall_app` flow. Prepare is read-only: it returns the app version, a
system-app determination, and the data-deletion impact; system apps or apps with unknown
properties are rejected outright. The async uninstall task can only be submitted after
the user explicitly re-confirms that summary. Failures or unknown outcomes are never
retried automatically.

Application lifecycle provides `mobile_inspect_app_state`, `mobile_launch_app`, and
`mobile_stop_app`. State inspection only reports whether the process exists, whether it
is in the foreground, and the stopped flag; launch and stop return an async task_id, and
stopping a non-system app requires explicit confirmation. Permanently clearing app data
requires calling `mobile_prepare_app_data_clear` first, showing the package name,
version, and data-deletion impact, and obtaining a fresh explicit confirmation before
calling `mobile_clear_app_data`. Clearing app data does not uninstall the app; failures
or unknown outcomes are never retried automatically.

Collect a recent log snapshot after explicit confirmation (requires the local API token
generated when the Runtime started):

```bash
PYTHONPATH=runtime python3.11 -m mobile_agent.cli.device_logs_collect \
  <device_id> --max-lines 500 --minimum-level info --confirm --token <runtime-token>
```

Logs are redacted first, then saved as a local artifact of at most 1 MiB; neither the
CLI nor REST returns log bodies. Add `--async-task` to get a task_id immediately and use
the unified execution status, events, cancellation, and task report:

```bash
PYTHONPATH=runtime python3.11 -m mobile_agent.cli.device_logs_collect \
  <device_id> --confirm --async-task --deadline-seconds 60 --token <runtime-token>
```

Collect an aggregate CPU, memory, battery-temperature, and system-load snapshot:

```bash
PYTHONPATH=runtime python3.11 -m mobile_agent.cli.device_performance_snapshot \
  <device_id> --async-task --deadline-seconds 90 --token <runtime-token>
```

Performance artifacts contain only aggregate JSON metrics — no raw dumpsys, process
names, or per-app details.

Collect a screenshot, UI tree, redacted logs, aggregate performance, and optional app
state in one pass, producing a local ZIP with a SHA-256 manifest:

```bash
PYTHONPATH=runtime python3.11 -m mobile_agent.cli.diagnostic_bundle_collect \
  <device_id> --app-id <package-id> --max-log-lines 500 \
  --minimum-log-level info --confirm --token <runtime-token>
```

Diagnostic bundles are Medium risk and require explicit confirmation. The CLI, Web,
REST, and MCP return only artifact metadata and a safety summary — they never inline the
screenshot, UI tree, logs, or ZIP contents; file names inside the bundle are fixed, the
total size never exceeds 24 MiB, and nothing is uploaded or sent out.

View local artifact usage and read-only-preview evidence older than the default 7-day
retention period:

```bash
PYTHONPATH=runtime python3.11 -m mobile_agent.cli.local_storage
PYTHONPATH=runtime python3.11 -m mobile_agent.cli.local_data_cleanup_prepare \
  --retention-days 7 --max-artifacts 500 --token <runtime-token>
```

Prepare deletes nothing; it only returns the candidate count, size, cutoff time, and a
short-lived approval. Only after the user reviews the impact summary and explicitly
re-confirms may the async cleanup task be submitted:

```bash
PYTHONPATH=runtime python3.11 -m mobile_agent.cli.local_data_cleanup \
  <approval-id> --confirm --token <runtime-token>
```

Cleanup only accepts the system-generated artifact IDs, relative paths, sizes, and
SHA-256 values bound into the approval; it accepts no arbitrary paths, never deletes the
task database, configuration, secrets, or APKs, and never runs automatically in the
background or auto-retries failures.

Compare two completed performance-snapshot tasks on the same device:

```bash
PYTHONPATH=runtime python3.11 -m mobile_agent.cli.device_performance_compare \
  <baseline_task_id> <candidate_task_id> --token <runtime-token>
```

The Web task report can also mark one successful snapshot as the baseline and pick
another snapshot to compare against. Comparison results only indicate the numeric
direction and stability thresholds of a two-point sample — they never assert causation
or performance regression on their own.

If `adb` is not on your `PATH`, configure it explicitly:

```bash
MOBILE_AGENT_ADB_PATH=/usr/local/platform-tools/adb
```

ITER-0003 added `GET /v1/tools`, `POST /v1/tools/{tool_id}/invoke`, and
`POST /v1/skills/app.open/invoke`. `input.tap` is Medium risk and requires explicit
confirmation by default.

ITER-0004 added safe UI-hierarchy parsing, semantic selectors, `input.tap_element`, and
`POST /v1/skills/settings.navigate/invoke`. Semantic tapping is Medium risk and is
rejected when the match is not unique.

ITER-0005 added policy-constrained `input.swipe`, `input.text`, bounded semantic
scroll-and-find, and `POST /v1/skills/settings.scroll_navigate/invoke`. Scrolling and
text input are Medium risk and require explicit confirmation by default; passwords, OTP
codes, payments, account security, and auto-submit scenarios are out of scope.

ITER-0006 added a minimal Task Runner, `TaskRun` evidence reports, and the preview
synchronous endpoint `POST /v1/tasks/settings.scroll_navigate/run`. That endpoint only
wraps the existing `settings.scroll_navigate` skill and does not replace the later
async task queue design.

ITER-0007 added an in-process Task Store, `TaskEvent`, and the query endpoints
`GET /v1/tasks/{task_id}` and `GET /v1/tasks/{task_id}/events`. The store lives only
for the current Runtime process lifetime and does not yet survive restarts.

ITER-0008 added the first CLI task-report view, rendering `TaskRun` and `TaskEvent`
into a human-readable report:

```bash
PYTHONPATH=runtime python3.11 -m mobile_agent.cli.task_report <task_id>
```

The command queries tasks and events from the local Runtime API.

ITER-0009 added a SQLite Task Store that saves tasks and events to
`<data-dir>/mobile-agent.db` by default. When `MOBILE_AGENT_DATA_DIR` is set, the
database lives under that directory; otherwise the platform default local data
directory is used.

ITER-0010 added the task history list:

```bash
PYTHONPATH=runtime python3.11 -m mobile_agent.cli.task_list --limit 20
```

The list shows recent task summaries; copy a `task_id` from it into `task_report` for
details.

ITER-0011 added the local Web UI. With the Runtime running, open:

```text
http://127.0.0.1:8765/ui
```

to browse task history and task-report details.

ITER-0012 added a "Run safe demo" button to the Web UI. It picks an online Android
device and runs a fixed task: open system Settings and navigate to the
Display/Brightness page. The POST still uses the local Runtime token and can only be
triggered from the same-origin loopback page.

ITER-0013 added the pre-model Agent Loop Preview: `POST /v1/tasks/agent.run`. The
endpoint uses a deterministic planner to produce constrained decisions, currently
supporting only the safe demo goal "go to the Display/Brightness page in system
Settings", and writes observation summaries, planner decisions, skill execution
results, and evidence into the task report.

ITER-0014 added a natural-language task input box and a "Run Agent Preview" button to
the Web UI. The page calls `POST /v1/tasks/agent.run`, then refreshes the history list
and opens the task report when the task returns.

ITER-0015 added the internal preview contract for an LLM planner plus a
`MockLLMPlanner`. Model-style output must pass structured parsing and field validation,
then a second check against the Agent Runner's skill allowlist; this iteration neither
calls a real model service nor reads model keys.

ITER-0016 added an off-by-default OpenAI-compatible planner provider preview. The
provider builds chat-completions-style requests, parses structured responses through an
injectable transport, and reuses ITER-0015's planner output validation; the default
Runtime does not enable a real provider, and tests depend on neither the network nor
model keys.

ITER-0017 added the model provider configuration gate: the default configuration still
returns the `RuleBasedPlanner`; only when `openai_compatible` is explicitly enabled
with `base_url`, `model`, and `api_key_ref`, and the key resolves through the injected
`SecretResolver`, is an OpenAI-compatible planner constructed. This iteration does not
wire into the default Runtime and does not read real keys.

ITER-0018 added a read-only model-provider status entry: `GET /v1/model-provider/status`
and a "Model Provider" status panel in the Web UI. The status only shows whether it is
enabled, the provider, the model, and whether a key reference is configured — never the
real key or the raw `api_key_ref`; the default Runtime still does not enable a real
model.

ITER-0019 added local model configuration loading: at startup the Runtime reads
`<data-dir>/model-provider.json` or the file named by `MOBILE_AGENT_MODEL_CONFIG`, and
allows `MOBILE_AGENT_MODEL_*` environment variables to override configuration fields.
The configuration file stores only `api_key_ref`; the developer-preview SecretResolver
only resolves `env:MOBILE_AGENT_MODEL_SECRET_*` references; the default Agent Runner
still does not call a real model.

ITER-0020 wired the model planner into the default Runtime under control: when the
configuration is off, the rule planner keeps running; when it is on and the key
reference resolves, the OpenAI-compatible planner is used; when it is on but
unavailable, agent tasks fail explicitly with `MODEL_UNAVAILABLE` instead of silently
falling back to the rule planner. Model output still passes structured parsing, the
skill allowlist, the Policy Engine, and the Device Gateway.

ITER-0021 enhanced the Web UI model-provider status card to distinguish not-enabled,
connected, configuration-unavailable, and configuration-loaded states, and to suggest
checking the configuration file, `MOBILE_AGENT_MODEL_CONFIG`, and
`MOBILE_AGENT_MODEL_SECRET_*` when unavailable. The repository ships a configuration
example: [model-provider.example.json](./docs/examples/model-provider.example.json).

ITER-0022 upgraded the Agent Preview from "one model decision calling a big skill" to
"multi-round model decisions + atomic tool execution + re-observation every round".
The planner may emit `run_tool` and `finish`; the Runtime only allows whitelisted
tools and verifies `finish` deterministically through UI selectors; the legacy
`run_skill` path remains for compatibility.

ITER-0023 promoted the per-round `AgentObservationSummary`, `AgentDecision`, and
`AgentStepResult` in agent reports to public JSON Schemas, and updated the `TaskRun`
schema to officially support `agent.run`. The desktop app, CLI, and future external
agents can stably consume multi-round Observe–Plan–Act reports.

ITER-0024 added agent action-progress feedback: the Runtime compares the foreground
app and UI tree before and after a tool call, feeds `changed` / `unchanged` back to the
next model round, and blocks re-dispatching the same no-progress action. Web reports
show the actual tool, parameters, and page progress in sync.

ITER-0025 optimized model-side observations: filtering out non-semantic layout nodes,
preferring visible text and operable nodes, adding summary truncation metadata, and
redacting common phone numbers, email addresses, and long numeric identifiers before
UI text enters model prompts and task summaries.

ITER-0026 added a strict agent ToolCall contract, one bounded repair of invalid model
arguments, and evidence retention for failed rounds. A multi-round model closed loop
for "enter Display & Brightness" has been completed on a real device.

ITER-0027 established goal-driven online agent evaluation: the real model re-plans
against the live device UI every time, and evaluation constrains only the goal, final
state, disabled tools, and round budget — never a fixed action path. Completed
`agent.run` tasks can be evaluated via `POST /v1/tasks/{task_id}/evaluate`; see
[agent-evaluation-scenario.example.json](./docs/examples/agent-evaluation-scenario.example.json)
for a scenario example.

ITER-0042 organizes multiple path-independent scenarios into a versioned suite. Run
each goal in the suite via Web or MCP, then hand the finished task_ids to a read-only
aggregation CLI; the command only calls the existing evaluation API and never submits
or replays device actions:

```bash
./scripts/report-mcp-evaluation.zsh \
  --suite evaluations/android-settings-smoke-v1.json \
  --task settings.bluetooth.v1=task_<id> \
  --task settings.display-brightness.v1=task_<id> \
  --task settings.battery.v1=task_<id>
```

The report shows overall success rate, per-scenario success rate, p50/p95 latency,
average rounds and tool calls, plus provider-retry, `NO_PROGRESS`,
`MODEL_UNAVAILABLE`, and policy-violation statistics. The suite defines goals with
independent success conditions and contains no fixed action paths. The script only
reads the registered `mobile-agent` local connection info from Codex — it neither
prints the token nor submits device tasks.

ITER-0028 hardened reliability: side-effect-free goal localization and `finish`
verification failures can feed back to the model as failed rounds for continued
planning; `finish` can combine foreground app/activity with UI selectors; taps in the
top system area and bottom gesture area are intercepted before dispatch. Provider
timeout, HTTP, connection, and response-format errors are classified and recorded,
with at most one retry for retryable model requests; invalid selectors surface only
field-level redacted diagnostics. When the model omits a non-safety-critical `reason`,
the Runtime generates a fixed audit note instead of issuing an extra model repair
request; tool, selector, policy, and completion-condition validation stays strict.

ITER-0029 added caller-optional Runtime-owned success conditions.
`POST /v1/tasks/agent.run` can receive `acceptance`, verifying the model's `finish`
with all-of semantics over foreground app id, activity, and unique UI selectors; the
path is still planned dynamically by the model from live observations. Task reports
persist and display `goal_acceptance` and `completion_source`. See
[agent-run-runtime-acceptance.example.json](./docs/examples/agent-run-runtime-acceptance.example.json)
for a request example.

ITER-0030 added two-phase goal compilation: `POST /v1/goals/compile` converts a short
natural-language goal into a reviewable `AgentGoalSpec` draft with an enhanced
execution goal, assumptions, confidence, and optional success conditions. The model
draft must be explicitly confirmed by the user before it can be passed to `agent.run`;
tasks are still planned dynamically by the model from live observations — no fixed
action path is generated. See
[agent-goal-spec.example.json](./docs/examples/agent-goal-spec.example.json).

ITER-0031 added async agent execution: `POST /v1/tasks/agent.run/async` immediately
returns `202 Accepted` with a task_id; `GET /v1/task-executions/{task_id}` and
`/events` provide persistent status and per-round events; and
`POST /v1/task-executions/{task_id}/cancel` requests cancellation at a safe boundary.
Async creation supports `Idempotency-Key`; the original synchronous
`POST /v1/tasks/agent.run` remains compatible. The local Web UI uses the async entry
by default.

ITER-0032 added an exclusive per-device lease to the Runtime's public write entries,
plus optional `deadline_seconds` (default 600, range 1–1800) for synchronous and async
`agent.run`. When the device is occupied by another task, callers get `DEVICE_LOCKED`;
a task that exceeds its budget at a safe boundary ends as
`timed_out/TASK_DEADLINE_EXCEEDED`, with evidence of completed actions preserved.

ITER-0033 added a single-instance Runtime lock per data directory, plus a `session_id`
for each continuous online device connection. Tasks and leases bind to the current
session; after a device disconnects or reconnects, old tasks stop with
`DEVICE_SESSION_CHANGED` and never send further actions into the new connection.
Device, TaskExecution, TaskRun, and Web/CLI reports all show the session identifier.

ITER-0034 added unified Runtime/Device readiness: Web and CLI interpret ADB, device
connection and authorization, session, and lease state through the same read-only
contract; only `ready` devices can start tasks from the Web. When ADB is missing, the
Runtime enters diagnostic mode with repair suggestions — it never auto-installs tools
or modifies device configuration.

ITER-0035 added device inspection and a capability catalog. Clicking a device in the
Web UI shows the eight basic V1 capabilities; `GET /v1/devices/{device_id}/inspection`
and the CLI show current availability, risk, idempotency, verification requirements,
associated tools, and limits. Inspection only reads device discovery and lease state —
no screenshots, no UI reads, no actions.

ITER-0036 added the first engineering diagnostic skill:
`POST /v1/skills/device.logs.collect/invoke`. The Android adapter accepts only a
bounded line count and fixed log levels, capturing a snapshot with fixed logcat
arguments; the skill requires Medium-risk explicit confirmation and produces a
redacted local `device_log` artifact. Web and CLI show artifact metadata only.
Continuous streaming capture, arbitrary logcat filters, and log upload are out of
scope.

ITER-0037 wired log collection into the unified async task pipeline:
`POST /v1/tasks/device.logs.collect/async` returns `202 Accepted` and reuses
TaskExecution status, incremental events, Idempotency-Key, cancellation, deadline,
device session, lease, and the persistent TaskRun report. The Web log button submits
asynchronously by default; the synchronous skill endpoint remains. The executor only
allows the agent and log task types registered in code — clients cannot submit
arbitrary handlers.

ITER-0038 added `device.performance.snapshot`: the Android adapter collects total CPU,
Total/Free RAM, battery level/temperature, uptime, and load average through fixed
read-only commands, writing only normalized values into a local JSON artifact.
Synchronous skill, async task, Web, and CLI share one contract; per-app/PID details
and continuous sampling are not provided.

ITER-0039 added `POST /v1/performance-comparisons`, taking two successful
performance-snapshot TaskRuns on the same device and computing two-point deltas and
threshold trends for CPU, memory, battery, temperature, and load. Comparison reads
only structured local task evidence — no device, model, or raw dumpsys access; Web and
CLI explicitly note that a two-point sample alone cannot prove causation or
regression.

ITER-0040 added the MCP `2025-11-25` stdio developer preview. The MCP subprocess only
calls the already-running Runtime's fixed localhost REST API, so it shares tasks,
sessions, leases, and policy with the Web; all time-consuming capabilities return a
ThumbAgent task_id asynchronously. Tool inputs come from the public contract and are
strictly validated and rate-limited; domain errors are returned as structuredContent.
MCP Tasks, remote transports, Resources, and Prompts are not implemented yet.

ITER-0047 added `device.diagnostics.bundle`. One confirmed async task combines
observation, redacted logs, aggregate performance, and optional app state within the
same device session and lease, producing a fixed-content local ZIP. The manifest
records the name, size, and SHA-256 of the four source artifacts; before releasing the
bundle, the Runtime re-validates source integrity and the ZIP file set, keeping the
already-completed safe artifact references on failure.

ITER-0048 added a local artifact storage summary and two-phase expiry cleanup. Preview
only scans system-generated files and returns an aggregate impact summary; submit only
accepts a ten-minute, single-use, scope-bound High-risk approval, then re-checks every
path, size, SHA-256, and cutoff time before deleting. The async task takes no device
session or lease; cancellation and deadline stop further deletions at safe boundaries
between artifacts, preserving the summary of completed deletions.

If a real provider consistently completes near the default 30-second budget, raise
`timeout_seconds` to 60 (allowed range 1–120) in the local configuration, or override
with `MOBILE_AGENT_MODEL_TIMEOUT_SECONDS=60`. Timeout retries may incur extra model
calls; task reports show the retry count.

## Product Documentation

- [Product positioning](./docs/product/positioning.md)
- [V1 product solution](./docs/product/solution-v1.md)
- [V1 technical design](./docs/architecture/technical-design-v1.md)

## Engineering Guidelines

- [Agent development guide](./AGENTS.md)
- [Contributing guide](./CONTRIBUTING.md)
- [Documentation & iteration rules](./docs/documentation-guide.md)
- [Development rules](./docs/engineering/development.md)
- [Contract & API evolution rules](./docs/engineering/contract-versioning.md)
- [Capability model](./docs/architecture/capability-model.md)
- [Skill development rules](./docs/engineering/skill-development.md)
- [Reliability & execution semantics](./docs/architecture/reliability-model.md)
- [Data & migration rules](./docs/engineering/data-migrations.md)
- [Error & diagnostics rules](./docs/engineering/error-handling.md)
- [Architecture boundaries](./docs/architecture/rules.md)
- [Testing rules](./docs/engineering/testing.md)
- [Security rules](./docs/engineering/security.md)
- [Multi-agent collaboration rules](./docs/engineering/agent-collaboration.md)
- [Architecture decision records](./docs/adr/README.md)
- [Iteration index](./docs/iterations/README.md)

## License

[Apache-2.0](./LICENSE)
