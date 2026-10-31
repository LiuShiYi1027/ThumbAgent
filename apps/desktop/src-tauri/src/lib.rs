mod sidecar;

use std::sync::Arc;

use sidecar::{Sidecar, SidecarStatus};
use tauri::{RunEvent, State};

struct AppState {
    sidecar: Arc<Sidecar>,
}

/// IO-bound commands (loopback HTTP, Keychain subprocess, child respawn)
/// run inside `spawn_blocking` so the Tauri IPC handler never blocks the
/// main event loop; pure in-memory reads stay synchronous.
#[tauri::command]
fn runtime_bridge_status(state: State<'_, AppState>) -> SidecarStatus {
    state.sidecar.status()
}

#[tauri::command]
async fn runtime_api_get(
    path: String,
    state: State<'_, AppState>,
) -> Result<serde_json::Value, String> {
    let sidecar = Arc::clone(&state.sidecar);
    tauri::async_runtime::spawn_blocking(move || sidecar.api_get(&path))
        .await
        .map_err(|error| format!("后台任务执行失败：{error}"))?
}

#[tauri::command]
async fn runtime_api_get_bytes(path: String, state: State<'_, AppState>) -> Result<String, String> {
    let sidecar = Arc::clone(&state.sidecar);
    tauri::async_runtime::spawn_blocking(move || sidecar.api_get_bytes(&path))
        .await
        .map_err(|error| format!("后台任务执行失败：{error}"))?
}

#[tauri::command]
async fn runtime_api_post(
    path: String,
    body: serde_json::Value,
    idempotency_key: Option<String>,
    state: State<'_, AppState>,
) -> Result<serde_json::Value, String> {
    let sidecar = Arc::clone(&state.sidecar);
    tauri::async_runtime::spawn_blocking(move || {
        sidecar.api_post(&path, &body, idempotency_key.as_deref())
    })
    .await
    .map_err(|error| format!("后台任务执行失败：{error}"))?
}

#[tauri::command]
async fn model_secret_store(secret: String) -> Result<(), String> {
    tauri::async_runtime::spawn_blocking(move || sidecar::model_secret_store(&secret))
        .await
        .map_err(|error| format!("后台任务执行失败：{error}"))?
}

#[tauri::command]
async fn model_secret_clear() -> Result<(), String> {
    tauri::async_runtime::spawn_blocking(sidecar::model_secret_clear)
        .await
        .map_err(|error| format!("后台任务执行失败：{error}"))?
}

#[tauri::command]
async fn model_secret_is_stored() -> bool {
    tauri::async_runtime::spawn_blocking(sidecar::model_secret_is_stored)
        .await
        .unwrap_or(false)
}

#[tauri::command]
async fn restart_runtime(state: State<'_, AppState>) -> Result<(), String> {
    let sidecar = Arc::clone(&state.sidecar);
    tauri::async_runtime::spawn_blocking(move || sidecar.restart())
        .await
        .map_err(|error| format!("后台任务执行失败：{error}"))?
}

#[tauri::command]
fn data_dir_path() -> Result<String, String> {
    sidecar::data_dir().map(|path| path.display().to_string())
}

#[tauri::command]
async fn reveal_data_dir() -> Result<String, String> {
    tauri::async_runtime::spawn_blocking(|| {
        sidecar::reveal_data_dir().map(|path| path.display().to_string())
    })
    .await
    .map_err(|error| format!("后台任务执行失败：{error}"))?
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let sidecar = Sidecar::start();
    let shutdown_sidecar = Arc::clone(&sidecar);
    tauri::Builder::default()
        .setup(|app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }
            Ok(())
        })
        .manage(AppState { sidecar })
        .invoke_handler(tauri::generate_handler![
            runtime_bridge_status,
            runtime_api_get,
            runtime_api_get_bytes,
            runtime_api_post,
            model_secret_store,
            model_secret_clear,
            model_secret_is_stored,
            restart_runtime,
            data_dir_path,
            reveal_data_dir
        ])
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(move |_app, event| {
            if matches!(event, RunEvent::ExitRequested { .. } | RunEvent::Exit) {
                shutdown_sidecar.shutdown();
            }
        });
}
