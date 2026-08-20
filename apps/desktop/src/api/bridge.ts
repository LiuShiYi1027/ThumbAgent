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

/**
 * Authenticated binary GET against the local Runtime. The sidecar only
 * forwards `/v1/artifacts/{artifact_id}/content` paths and returns the
 * bounded body as base64.
 */
export function runtimeApiGetBytes(path: string): Promise<string> {
  return invoke<string>('runtime_api_get_bytes', { path })
}

/**
 * Authenticated POST against the local Runtime. The sidecar only forwards
 * whitelisted paths (task submit/cancel, model settings save); everything
 * else is rejected.
 */
export function runtimeApiPost<T>(path: string, body: unknown): Promise<T> {
  return invoke<T>('runtime_api_post', { path, body })
}

/** Store the model API key in the macOS Keychain (never sent to the Runtime). */
export function storeModelSecret(secret: string): Promise<void> {
  return invoke<void>('model_secret_store', { secret })
}

/** Remove the stored model API key from the Keychain. */
export function clearModelSecret(): Promise<void> {
  return invoke<void>('model_secret_clear')
}

/** Whether a model API key is currently stored in the Keychain. */
export function isModelSecretStored(): Promise<boolean> {
  return invoke<boolean>('model_secret_is_stored')
}

/**
 * Restart the Runtime sidecar so saved settings take effect. In-flight tasks
 * die with the old child; the UI must confirm with the user first.
 */
export function restartRuntime(): Promise<void> {
  return invoke<void>('restart_runtime')
}

/** Absolute path of the Runtime data directory on this machine. */
export function getDataDirPath(): Promise<string> {
  return invoke<string>('data_dir_path')
}

/** Open the Runtime data directory in Finder. Returns the opened path. */
export function revealDataDir(): Promise<string> {
  return invoke<string>('reveal_data_dir')
}
