mod sidecar;

use std::sync::Arc;

use sidecar::{Sidecar, SidecarStatus};
use tauri::{RunEvent, State};

struct AppState {
    sidecar: Arc<Sidecar>,
}

#[tauri::command]
fn runtime_bridge_status(state: State<'_, AppState>) -> SidecarStatus {
    state.sidecar.status()
}

#[tauri::command]
fn runtime_api_get(path: String, state: State<'_, AppState>) -> Result<serde_json::Value, String> {
    state.sidecar.api_get(&path)
}

#[tauri::command]
fn runtime_api_get_bytes(path: String, state: State<'_, AppState>) -> Result<String, String> {
    state.sidecar.api_get_bytes(&path)
}

#[tauri::command]
fn runtime_api_post(
    path: String,
    body: serde_json::Value,
    state: State<'_, AppState>,
) -> Result<serde_json::Value, String> {
    state.sidecar.api_post(&path, &body)
}

#[tauri::command]
fn model_secret_store(secret: String) -> Result<(), String> {
    sidecar::model_secret_store(&secret)
}

#[tauri::command]
fn model_secret_clear() -> Result<(), String> {
    sidecar::model_secret_clear()
}

#[tauri::command]
fn model_secret_is_stored() -> bool {
    sidecar::model_secret_is_stored()
}

#[tauri::command]
fn restart_runtime(state: State<'_, AppState>) -> Result<(), String> {
    state.sidecar.restart()
}

#[tauri::command]
fn data_dir_path() -> Result<String, String> {
    sidecar::data_dir().map(|path| path.display().to_string())
}

#[tauri::command]
fn reveal_data_dir() -> Result<String, String> {
    sidecar::reveal_data_dir().map(|path| path.display().to_string())
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
