use std::sync::Arc;
use std::time::Duration;
use tauri::{AppHandle, Emitter, Manager, Runtime};
use tauri_plugin_shell::ShellExt;
use tokio::sync::Mutex;
use tokio::time::sleep;

// ── Constants ───────────────────────────────────────────────────────────────

/// Starting port to try; we probe upward until we find a free one.
const BASE_PORT: u16 = 18_000;
const MAX_PORT_ATTEMPTS: u16 = 20;
/// How long to wait between health-check polls.
const HEALTH_POLL_INTERVAL_MS: u64 = 500;
/// Total time (ms) to wait for the backend to become healthy.
const HEALTH_TIMEOUT_MS: u64 = 30_000;
/// Event name emitted to the frontend when the backend is ready.
const EVENT_BACKEND_READY: &str = "backend-ready";
/// Event name emitted when the backend fails to start.
const EVENT_BACKEND_FAILED: &str = "backend-failed";

// ── State ───────────────────────────────────────────────────────────────────

/// Shared handle to the running sidecar child process.
struct SidecarState {
    child: Option<tauri_plugin_shell::process::CommandChild>,
    port: Option<u16>,
}

// ── Port helper ──────────────────────────────────────────────────────────────

/// Find an available TCP port starting from `base`.
fn find_free_port(base: u16, attempts: u16) -> Option<u16> {
    use std::net::TcpListener;
    for offset in 0..attempts {
        let port = base + offset;
        if TcpListener::bind(format!("127.0.0.1:{port}")).is_ok() {
            return Some(port);
        }
    }
    None
}

// ── Health check ─────────────────────────────────────────────────────────────

async fn wait_for_backend(port: u16) -> bool {
    let client = reqwest::Client::builder()
        .timeout(Duration::from_millis(2_000))
        .build()
        .expect("failed to build HTTP client");

    let url = format!("http://127.0.0.1:{port}/api/health");
    let deadline = std::time::Instant::now() + Duration::from_millis(HEALTH_TIMEOUT_MS);

    while std::time::Instant::now() < deadline {
        match client.get(&url).send().await {
            Ok(resp) if resp.status().is_success() => {
                log::info!("[sidecar] backend healthy on port {port}");
                return true;
            }
            _ => {
                sleep(Duration::from_millis(HEALTH_POLL_INTERVAL_MS)).await;
            }
        }
    }
    log::error!("[sidecar] backend did not become healthy within {HEALTH_TIMEOUT_MS}ms");
    false
}

// ── Sidecar spawn ─────────────────────────────────────────────────────────────

async fn spawn_sidecar<R: Runtime>(app: &AppHandle<R>, state: Arc<Mutex<SidecarState>>) {
    // Find a free port.
    let port = match find_free_port(BASE_PORT, MAX_PORT_ATTEMPTS) {
        Some(p) => p,
        None => {
            log::error!(
                "[sidecar] no free port found in range {BASE_PORT}–{}",
                BASE_PORT + MAX_PORT_ATTEMPTS
            );
            let _ = app.emit(EVENT_BACKEND_FAILED, "No free port available");
            return;
        }
    };
    log::info!("[sidecar] selected port {port}");

    // Resolve the data directory (macOS: ~/Library/Application Support/<identifier>).
    let data_dir = app
        .path()
        .app_data_dir()
        .unwrap_or_else(|_| std::path::PathBuf::from("/tmp/prompt-compiler"));

    let data_dir_str = data_dir.to_string_lossy().to_string();
    log::info!("[sidecar] data dir: {data_dir_str}");

    // Resolve the sidecar command.
    let sidecar_cmd = match app.shell().sidecar("prompt-compiler-backend") {
        Ok(cmd) => cmd,
        Err(e) => {
            log::error!("[sidecar] failed to resolve sidecar command: {e}");
            let _ = app.emit(EVENT_BACKEND_FAILED, format!("Sidecar not found: {e}"));
            return;
        }
    };

    // Spawn with environment variables — the backend reads all config from env.
    let (mut rx, child) = match sidecar_cmd
        .env("DESKTOP_MODE", "true")
        .env("DESKTOP_BACKEND_HOST", "127.0.0.1")
        .env("DESKTOP_BACKEND_PORT", port.to_string())
        .env("PROMPT_COMPILER_DATA_DIR", &data_dir_str)
        .env("APP_DATA_DIR", &data_dir_str)
        .env("OLLAMA_MODEL", "qwen3:0.6b")
        .spawn()
    {
        Ok(pair) => pair,
        Err(e) => {
            log::error!("[sidecar] failed to spawn: {e}");
            let _ = app.emit(EVENT_BACKEND_FAILED, format!("Spawn failed: {e}"));
            return;
        }
    };

    log::info!("[sidecar] process spawned on port {port}");

    // Store the child handle so we can kill it on exit.
    {
        let mut guard = state.lock().await;
        guard.child = Some(child);
        guard.port = Some(port);
    }

    // Forward stdout/stderr to the Tauri log in a background task.
    let app_clone = app.clone();
    tokio::spawn(async move {
        use tauri_plugin_shell::process::CommandEvent;
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(line) => {
                    log::debug!("[sidecar stdout] {}", String::from_utf8_lossy(&line));
                }
                CommandEvent::Stderr(line) => {
                    log::warn!("[sidecar stderr] {}", String::from_utf8_lossy(&line));
                }
                CommandEvent::Error(e) => {
                    log::error!("[sidecar error] {e}");
                    let _ = app_clone.emit(EVENT_BACKEND_FAILED, format!("Process error: {e}"));
                }
                CommandEvent::Terminated(status) => {
                    log::warn!("[sidecar] process terminated: {status:?}");
                    let _ = app_clone.emit(
                        EVENT_BACKEND_FAILED,
                        "Backend process terminated unexpectedly",
                    );
                    break;
                }
                _ => {}
            }
        }
    });

    // Poll health endpoint; emit ready/failed event to the frontend.
    if wait_for_backend(port).await {
        let base_url = format!("http://127.0.0.1:{port}");
        log::info!("[sidecar] emitting {EVENT_BACKEND_READY} → {base_url}");
        let _ = app.emit(EVENT_BACKEND_READY, base_url);
    } else {
        let _ = app.emit(
            EVENT_BACKEND_FAILED,
            "Backend health check timed out after 30 s",
        );
    }
}

// ── Shutdown ──────────────────────────────────────────────────────────────────

async fn shutdown_sidecar(state: Arc<Mutex<SidecarState>>) {
    let mut guard = state.lock().await;
    if let Some(child) = guard.child.take() {
        log::info!("[sidecar] killing sidecar process on app exit");
        if let Err(e) = child.kill() {
            log::error!("[sidecar] failed to kill sidecar: {e}");
        }
    }
    guard.port = None;
}

// ── Commands ──────────────────────────────────────────────────────────────────

/// Query the currently running backend URL (e.g. "http://127.0.0.1:18000").
#[tauri::command]
async fn get_backend_url(
    state: tauri::State<'_, Arc<Mutex<SidecarState>>>,
) -> Result<Option<String>, String> {
    let guard = state.lock().await;
    if let Some(port) = guard.port {
        Ok(Some(format!("http://127.0.0.1:{port}")))
    } else {
        Ok(None)
    }
}

/// Launch external browser (Google Chrome preferred, with system default fallback).
#[tauri::command]
async fn open_in_browser(url: String) -> Result<(), String> {
    if !url.starts_with("http://") && !url.starts_with("https://") {
        return Err("Invalid URL scheme. Expected http:// or https://".to_string());
    }

    #[cfg(target_os = "macos")]
    {
        // Try opening in Google Chrome first
        let status = std::process::Command::new("open")
            .args(["-a", "Google Chrome", &url])
            .status();

        if let Ok(exit_status) = status {
            if exit_status.success() {
                return Ok(());
            }
        }

        // Fallback to default browser
        let _ = std::process::Command::new("open").arg(&url).status();
        Ok(())
    }

    #[cfg(not(target_os = "macos"))]
    {
        let _ = std::process::Command::new("xdg-open").arg(&url).status();
        Ok(())
    }
}

// ── Entry point ───────────────────────────────────────────────────────────────

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let sidecar_state = Arc::new(Mutex::new(SidecarState {
        child: None,
        port: None,
    }));
    let sidecar_state_setup = Arc::clone(&sidecar_state);
    let sidecar_state_exit = Arc::clone(&sidecar_state);
    let sidecar_state_run = Arc::clone(&sidecar_state);

    let app = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .manage(Arc::clone(&sidecar_state))
        .invoke_handler(tauri::generate_handler![get_backend_url, open_in_browser])
        .setup(move |app| {
            let app_handle = app.handle().clone();
            let state = Arc::clone(&sidecar_state_setup);

            // Spawn the sidecar asynchronously so the window opens immediately.
            tauri::async_runtime::spawn(async move {
                spawn_sidecar(&app_handle, state).await;
            });

            Ok(())
        })
        .on_window_event(move |_window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                let state = Arc::clone(&sidecar_state_exit);
                tauri::async_runtime::block_on(async move {
                    shutdown_sidecar(state).await;
                });
            }
        })
        .build(tauri::generate_context!())
        .expect("error while building prompt compiler desktop application");

    app.run(move |_app_handle, event| {
        if let tauri::RunEvent::ExitRequested { .. } | tauri::RunEvent::Exit = event {
            let state = Arc::clone(&sidecar_state_run);
            tauri::async_runtime::block_on(async move {
                shutdown_sidecar(state).await;
            });
        }
    });
}
