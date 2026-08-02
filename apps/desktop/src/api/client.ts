import type { Device } from '@contracts/device'
import type { RuntimeReadiness } from '@contracts/runtime-readiness'

import { runtimeApiGet } from './bridge'

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
