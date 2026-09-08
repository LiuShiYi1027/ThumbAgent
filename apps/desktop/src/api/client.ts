import type { Device } from '@contracts/device'
import type { DevicePerformanceSnapshot } from '@contracts/device-performance-snapshot'
import type { RuntimeReadiness } from '@contracts/runtime-readiness'
import type { TaskEvent } from '@contracts/task-event'
import type { TaskExecution } from '@contracts/task-execution'
import type { TaskRun } from '@contracts/task-run'

import { runtimeApiGet, runtimeApiGetBytes, runtimeApiPost } from './bridge'

export interface RuntimeHealth {
  status: string
  runtime_version: string
  api_version: string
}

export interface DeviceListResponse {
  devices: Device[]
}

export function getHealth(): Promise<RuntimeHealth> {
  return runtimeApiGet<RuntimeHealth>('/v1/health')
}

interface ReadinessResponse {
  readiness: RuntimeReadiness
}

export async function getReadiness(): Promise<RuntimeReadiness> {
  const payload = await runtimeApiGet<ReadinessResponse>('/v1/readiness')
  return payload.readiness
}

export function getDevices(): Promise<DeviceListResponse> {
  return runtimeApiGet<DeviceListResponse>('/v1/devices')
}

const AGENT_RUN_ASYNC_PATH = '/v1/tasks/agent.run/async'
// Fixed V1 submission budget, matching the /ui prototype defaults.
const AGENT_MAX_ROUNDS = 12
const AGENT_DEADLINE_SECONDS = 600

interface ExecutionResponse {
  execution: TaskExecution
}

interface ExecutionEventsResponse {
  events: TaskEvent[]
}

interface TaskRunResponse {
  task: TaskRun
}

/**
 * Submit a confirmed asynchronous Agent task. The caller must have shown the
 * goal, device and risk summary and collected an explicit user confirmation
 * before invoking this; `confirmed: true` attests to that.
 *
 * `idempotencyKey` is minted when the confirmation dialog opens and reused
 * for every retry inside that flow, so duplicate submissions of the same
 * user intent collapse into one Runtime task.
 */
export async function submitAgentTask(
  deviceId: string,
  goal: string,
  idempotencyKey: string,
  maxRounds: number = AGENT_MAX_ROUNDS,
): Promise<TaskExecution> {
  const payload = await runtimeApiPost<ExecutionResponse>(
    AGENT_RUN_ASYNC_PATH,
    {
      device_id: deviceId,
      goal,
      confirmed: true,
      max_rounds: maxRounds,
      deadline_seconds: AGENT_DEADLINE_SECONDS,
    },
    idempotencyKey,
  )
  return payload.execution
}

export async function getTaskExecution(taskId: string): Promise<TaskExecution> {
  const payload = await runtimeApiGet<ExecutionResponse>(
    `/v1/task-executions/${taskId}`,
  )
  return payload.execution
}

export async function getTaskExecutionEvents(taskId: string): Promise<TaskEvent[]> {
  const payload = await runtimeApiGet<ExecutionEventsResponse>(
    `/v1/task-executions/${taskId}/events`,
  )
  return payload.events
}

export async function cancelTaskExecution(taskId: string): Promise<TaskExecution> {
  const payload = await runtimeApiPost<ExecutionResponse>(
    `/v1/task-executions/${taskId}/cancel`,
    {},
  )
  return payload.execution
}

export async function pauseTaskExecution(taskId: string): Promise<TaskExecution> {
  const payload = await runtimeApiPost<ExecutionResponse>(
    `/v1/task-executions/${taskId}/pause`,
    {},
  )
  return payload.execution
}

export async function resumeTaskExecution(taskId: string): Promise<TaskExecution> {
  const payload = await runtimeApiPost<ExecutionResponse>(
    `/v1/task-executions/${taskId}/resume`,
    {},
  )
  return payload.execution
}

export async function getTaskRun(taskId: string): Promise<TaskRun> {
  const payload = await runtimeApiGet<TaskRunResponse>(`/v1/tasks/${taskId}`)
  return payload.task
}

/** Non-secret on-disk model provider configuration shown on the settings page. */
export interface ModelProviderConfig {
  enabled: boolean
  provider: string
  base_url: string
  model: string
  api_key_ref: string
  timeout_seconds: number
  config_file: string
  env_override: boolean
}

interface ModelProviderConfigResponse {
  config: ModelProviderConfig
}

export async function getModelProviderConfig(): Promise<ModelProviderConfig> {
  const payload = await runtimeApiGet<ModelProviderConfigResponse>(
    '/v1/model-provider/config',
  )
  return payload.config
}

interface SaveModelProviderConfigResponse {
  saved: boolean
  restart_required: boolean
  config: ModelProviderConfig
}

/** Env reference the desktop always writes; the value itself stays in the Keychain. */
export const DESKTOP_SECRET_REF = 'env:MOBILE_AGENT_MODEL_SECRET_DESKTOP'

/**
 * Persist model provider settings. The Runtime validates and rejects unknown
 * fields; applying the saved settings requires a Runtime restart afterwards.
 */
export async function saveModelProviderConfig(
  config: Pick<
    ModelProviderConfig,
    'enabled' | 'provider' | 'base_url' | 'model' | 'timeout_seconds'
  >,
): Promise<ModelProviderConfig> {
  const payload = await runtimeApiPost<SaveModelProviderConfigResponse>(
    '/v1/model-provider/config',
    { ...config, api_key_ref: DESKTOP_SECRET_REF },
  )
  return payload.config
}

const ARTIFACT_ID_PATTERN = /^artifact_[a-f0-9]{32}$/

/**
 * Fetch one stored screenshot artifact as a PNG Blob. The Runtime endpoint is
 * token-gated and screenshot-only; the blob stays in webview memory and is
 * never written to disk by the desktop app.
 */
export async function getScreenshotContent(artifactId: string): Promise<Blob> {
  if (!ARTIFACT_ID_PATTERN.test(artifactId)) {
    throw new Error('无效的截图 Artifact ID')
  }
  const base64 = await runtimeApiGetBytes(`/v1/artifacts/${artifactId}/content`)
  const binary = atob(base64)
  const bytes = new Uint8Array(binary.length)
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index)
  }
  return new Blob([bytes], { type: 'image/png' })
}

/** Latest screenshot artifact id carried by task.step_completed events. */
export function latestScreenshotFromEvents(events: TaskEvent[]): string | null {
  for (let index = events.length - 1; index >= 0; index -= 1) {
    const event = events[index]
    if (event.event_type !== 'task.step_completed') {
      continue
    }
    const artifactId = event.payload.screenshot_artifact_id
    if (typeof artifactId === 'string' && ARTIFACT_ID_PATTERN.test(artifactId)) {
      return artifactId
    }
  }
  return null
}

/** Canonical object guard for this package's boundary narrowing. */
function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

/* ITER-0065: DSL 稳定性任务把性能采样序列与崩溃判定写入自由形态的
   evidence_summary（task-run schema 为宽松 object）。在 API 边界窄化一次，
   组件消费命名类型，不让 any 泄漏进渲染层。 */

export interface SamplingSeriesPoint {
  step_id: string
  captured_at: string
  cpu: DevicePerformanceSnapshot['cpu']
  memory: DevicePerformanceSnapshot['memory']
  battery: DevicePerformanceSnapshot['battery']
  system: DevicePerformanceSnapshot['system']
}

export interface CrashSignature {
  kind: 'crash' | 'anr'
  summary: string
}

export interface CrashCheckSummary {
  checked_lines: number
  signatures: CrashSignature[]
}

type SnapshotSlice = Omit<SamplingSeriesPoint, 'step_id' | 'captured_at'>

function asSnapshotSlice(value: Record<string, unknown>): SnapshotSlice | null {
  const { cpu, memory, battery, system } = value
  if (!isRecord(cpu) || !isRecord(memory) || !isRecord(battery) || !isRecord(system)) {
    return null
  }
  if (
    typeof cpu.total_usage_percent !== 'number' ||
    typeof memory.used_percent !== 'number' ||
    typeof battery.level_percent !== 'number' ||
    typeof system.uptime_seconds !== 'number'
  ) {
    return null
  }
  return {
    cpu: cpu as DevicePerformanceSnapshot['cpu'],
    memory: memory as DevicePerformanceSnapshot['memory'],
    battery: battery as DevicePerformanceSnapshot['battery'],
    system: system as DevicePerformanceSnapshot['system'],
  }
}

/** 窄化 evidence_summary.sampling_series；元素不符即丢弃，全部不符返回 null。 */
export function asSamplingSeries(value: unknown): SamplingSeriesPoint[] | null {
  if (!Array.isArray(value)) {
    return null
  }
  const points: SamplingSeriesPoint[] = []
  for (const entry of value) {
    if (!isRecord(entry)) {
      continue
    }
    const slice = asSnapshotSlice(entry)
    if (
      slice &&
      typeof entry.step_id === 'string' &&
      typeof entry.captured_at === 'string'
    ) {
      points.push({ step_id: entry.step_id, captured_at: entry.captured_at, ...slice })
    }
  }
  return points.length > 0 ? points : null
}

/** 窄化 evidence_summary.crash_check；形状不符返回 null（旧任务报告降级）。 */
export function asCrashCheck(value: unknown): CrashCheckSummary | null {
  if (!isRecord(value) || typeof value.checked_lines !== 'number') {
    return null
  }
  if (!Array.isArray(value.signatures)) {
    return null
  }
  const signatures: CrashSignature[] = []
  for (const entry of value.signatures) {
    if (
      isRecord(entry) &&
      (entry.kind === 'crash' || entry.kind === 'anr') &&
      typeof entry.summary === 'string'
    ) {
      signatures.push({ kind: entry.kind, summary: entry.summary })
    }
  }
  return { checked_lines: value.checked_lines, signatures }
}

/** After-action screenshot artifact id of one persisted task step. */
export function stepScreenshotArtifactId(step: TaskRun['steps'][number]): string | null {
  const result = step.result as Record<string, unknown> | null
  if (!result) {
    return null
  }
  const candidates: unknown[] = [result.action_result]
  const skill = result.skill_result as Record<string, unknown> | null | undefined
  if (skill) {
    candidates.push(skill.tap_action, skill.action)
  }
  for (const candidate of candidates) {
    const artifactId = readAfterScreenshotId(candidate)
    if (artifactId) {
      return artifactId
    }
  }
  return null
}

function readAfterScreenshotId(action: unknown): string | null {
  if (!action || typeof action !== 'object') {
    return null
  }
  const after = (action as Record<string, unknown>).after
  if (!after || typeof after !== 'object') {
    return null
  }
  const screen = (after as Record<string, unknown>).screen
  if (!screen || typeof screen !== 'object') {
    return null
  }
  const screenshot = (screen as Record<string, unknown>).screenshot
  if (!screenshot || typeof screenshot !== 'object') {
    return null
  }
  const artifactId = (screenshot as Record<string, unknown>).artifact_id
  return typeof artifactId === 'string' && ARTIFACT_ID_PATTERN.test(artifactId)
    ? artifactId
    : null
}
