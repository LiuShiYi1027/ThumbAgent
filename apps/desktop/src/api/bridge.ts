import { invoke } from '@tauri-apps/api/core'

export type SidecarPhase = 'starting' | 'ready' | 'failed'

export interface SidecarStatus {
  phase: SidecarPhase
  detail: string
  base_url: string | null
}

/** Poll the desktop-owned Runtime sidecar lifecycle state. */
export function getBridgeStatus(): Promise<SidecarStatus> {
  return invoke<SidecarStatus>('runtime_bridge_status')
}

/** Authenticated GET against the local Runtime, routed through the sidecar. */
export function runtimeApiGet<T>(path: string): Promise<T> {
  return invoke<T>('runtime_api_get', { path })
}
