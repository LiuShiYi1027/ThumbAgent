import type { Device } from '@contracts/device'
import type { RuntimeReadiness } from '@contracts/runtime-readiness'
import type { TaskEvent } from '@contracts/task-event'
import type { TaskExecution } from '@contracts/task-execution'
import type { TaskRun } from '@contracts/task-run'

import { runtimeApiGet, runtimeApiPost } from './bridge'

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
