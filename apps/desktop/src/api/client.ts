import type { Device } from '@contracts/device'
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
const AGENT_MAX_ROUNDS = 6
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
 */
export async function submitAgentTask(
  deviceId: string,
  goal: string,
): Promise<TaskExecution> {
  const payload = await runtimeApiPost<ExecutionResponse>(AGENT_RUN_ASYNC_PATH, {
    device_id: deviceId,
    goal,
    confirmed: true,
    max_rounds: AGENT_MAX_ROUNDS,
    deadline_seconds: AGENT_DEADLINE_SECONDS,
  })
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

export async function getTaskRun(taskId: string): Promise<TaskRun> {
  const payload = await runtimeApiGet<TaskRunResponse>(`/v1/tasks/${taskId}`)
  return payload.task
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
