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
            runtime_api_post
        ])
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(move |_app, event| {
            if matches!(event, RunEvent::ExitRequested { .. } | RunEvent::Exit) {
                shutdown_sidecar.shutdown();
            }
        });
}
