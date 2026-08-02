//! Python Runtime sidecar lifecycle owned by the desktop process.
//!
//! The desktop spawns `python3.11 -m mobile_agent.api.server` on a random
//! loopback port with a one-time API token passed through the child
//! environment, polls `/v1/health` until ready, and kills the child on app
//! exit. The token never leaves this module; the webview reaches the Runtime
//! exclusively through the `runtime_api_get` command.

use std::io::{Read, Write};
use std::net::{Ipv4Addr, SocketAddr, TcpListener, TcpStream};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

const HEALTH_TIMEOUT: Duration = Duration::from_secs(20);
const HEALTH_POLL_INTERVAL: Duration = Duration::from_millis(200);
const HTTP_CONNECT_TIMEOUT: Duration = Duration::from_millis(500);
const HTTP_READ_TIMEOUT: Duration = Duration::from_secs(5);
const MAX_HTTP_RESPONSE_BYTES: usize = 1 << 20;
const STDERR_TAIL_BYTES: usize = 4 * 1024;
const MAX_API_PATH_BYTES: usize = 512;

#[derive(Debug, Clone, Copy, PartialEq, Eq, serde::Serialize)]
#[serde(rename_all = "snake_case")]
pub enum SidecarPhase {
    Starting,
    Ready,
    Failed,
}

#[derive(Debug, Clone, serde::Serialize)]
pub struct SidecarStatus {
    pub phase: SidecarPhase,
    pub detail: String,
    pub base_url: Option<String>,
}

struct SidecarInner {
    phase: SidecarPhase,
    detail: String,
    child: Option<Child>,
    port: u16,
    token: String,
    stderr_tail: Arc<Mutex<String>>,
}

pub struct Sidecar {
    inner: Mutex<SidecarInner>,
}

impl Sidecar {
    /// Spawn the Runtime child and start the background health loop.
    ///
    /// Configuration or spawn failures are reported as `Failed` phase instead
    /// of aborting the app, so the UI can render actionable diagnostics.
    pub fn start() -> Arc<Self> {
        match Self::spawn() {
            Ok(sidecar) => {
                let shared = Arc::new(sidecar);
                Sidecar::start_health_loop(Arc::clone(&shared));
                shared
            }
            Err(detail) => Arc::new(Sidecar {
                inner: Mutex::new(SidecarInner {
                    phase: SidecarPhase::Failed,
                    detail,
                    child: None,
                    port: 0,
                    token: String::new(),
                    stderr_tail: Arc::new(Mutex::new(String::new())),
                }),
            }),
        }
    }

    fn spawn() -> Result<Self, String> {
        let repo_root = resolve_repo_root(
            std::env::var_os("MOBILE_AGENT_REPO_ROOT").map(PathBuf::from),
            Path::new(env!("CARGO_MANIFEST_DIR")),
        )?;
        let python = resolve_python(
            std::env::var_os("MOBILE_AGENT_PYTHON").map(PathBuf::from),
            std::env::var_os("PATH"),
            std::env::var_os("HOME").map(PathBuf::from),
        )
        .ok_or_else(|| {
            "未找到 python3.11。请安装 Python 3.11+ 或设置 MOBILE_AGENT_PYTHON。".to_string()
        })?;
        let port =
            pick_loopback_port().map_err(|error| format!("无法分配本地回环端口：{error}"))?;
        let token = generate_token().map_err(|error| format!("无法生成会话令牌：{error}"))?;

        let mut pythonpath = repo_root.join("runtime").as_os_str().to_os_string();
        if let Some(existing) = std::env::var_os("PYTHONPATH") {
            pythonpath.push(":");
            pythonpath.push(existing);
        }

        let mut command = Command::new(&python);
        command
            .arg("-m")
            .arg("mobile_agent.api.server")
            .arg("--host")
            .arg("127.0.0.1")
            .arg("--port")
            .arg(port.to_string())
            .current_dir(&repo_root)
            .env("MOBILE_AGENT_API_TOKEN", &token)
            .env("PYTHONPATH", pythonpath)
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::piped());

        let mut child = command
            .spawn()
            .map_err(|error| format!("启动 Runtime 进程失败（{}）：{error}", python.display()))?;

        let stderr_tail = Arc::new(Mutex::new(String::new()));
        if let Some(stderr) = child.stderr.take() {
            start_stderr_drain(stderr, Arc::clone(&stderr_tail));
        }

        Ok(Sidecar {
            inner: Mutex::new(SidecarInner {
                phase: SidecarPhase::Starting,
                detail: "正在启动本地 Runtime…".to_string(),
                child: Some(child),
                port,
                token,
                stderr_tail,
            }),
        })
    }

    fn start_health_loop(sidecar: Arc<Self>) {
        std::thread::spawn(move || {
            let deadline = Instant::now() + HEALTH_TIMEOUT;
            loop {
                std::thread::sleep(HEALTH_POLL_INTERVAL);
                let mut inner = sidecar.inner.lock().unwrap();
                if inner.phase == SidecarPhase::Failed {
                    return;
                }
                if let Some(child) = inner.child.as_mut() {
                    match child.try_wait() {
                        Ok(Some(status)) => {
                            let tail = inner.stderr_tail.lock().unwrap().clone();
                            inner.phase = SidecarPhase::Failed;
                            inner.detail = early_exit_detail(status.code(), &tail);
                            return;
                        }
                        Ok(None) => {}
                        Err(error) => {
                            inner.phase = SidecarPhase::Failed;
                            inner.detail = format!("无法检查 Runtime 进程状态：{error}");
                            return;
                        }
                    }
                }
                let (port, token) = (inner.port, inner.token.clone());
                drop(inner);

                if let Ok((200, _)) = http_get(port, "/v1/health", &token) {
                    let mut inner = sidecar.inner.lock().unwrap();
                    if inner.phase == SidecarPhase::Starting {
                        inner.phase = SidecarPhase::Ready;
                        inner.detail = "本地 Runtime 已就绪".to_string();
                    }
                    return;
                }
                if Instant::now() >= deadline {
                    let mut inner = sidecar.inner.lock().unwrap();
                    if inner.phase == SidecarPhase::Starting {
                        inner.phase = SidecarPhase::Failed;
                        inner.detail = format!(
                            "本地 Runtime 在 {} 秒内未通过健康检查",
                            HEALTH_TIMEOUT.as_secs()
                        );
                    }
                    return;
                }
            }
        });
    }

    pub fn status(&self) -> SidecarStatus {
        let inner = self.inner.lock().unwrap();
        SidecarStatus {
            phase: inner.phase,
            detail: inner.detail.clone(),
            base_url: (inner.phase == SidecarPhase::Ready)
                .then(|| format!("http://127.0.0.1:{}", inner.port)),
        }
    }

    /// Execute an authenticated GET against the sidecar Runtime.
    pub fn api_get(&self, path: &str) -> Result<serde_json::Value, String> {
        validate_api_path(path)?;
        let (port, token) = {
            let inner = self.inner.lock().unwrap();
            if inner.phase != SidecarPhase::Ready {
                return Err("本地 Runtime 尚未就绪".to_string());
            }
            (inner.port, inner.token.clone())
        };
        let (status, body) = http_get(port, path, &token)?;
        let value: serde_json::Value = serde_json::from_slice(&body)
            .map_err(|error| format!("Runtime 响应不是有效 JSON：{error}"))?;
        if status != 200 {
            let message = value
                .pointer("/error/message")
                .and_then(serde_json::Value::as_str)
                .unwrap_or("未知错误");
            return Err(format!("Runtime 返回 {status}：{message}"));
        }
        Ok(value)
    }

    /// Kill the sidecar child. Idempotent; safe to call on every exit path.
    pub fn shutdown(&self) {
        let child = {
            let mut inner = self.inner.lock().unwrap();
            inner.child.take()
        };
        if let Some(mut child) = child {
            let _ = child.kill();
            let _ = child.wait();
        }
    }
}

fn early_exit_detail(code: Option<i32>, stderr_tail: &str) -> String {
    let tail = stderr_tail.trim();
    let conflict =
        tail.contains("RUNTIME_ALREADY_RUNNING") || tail.contains("已有 Mobile Agent Runtime");
    if conflict {
        return "同一数据目录已有 Runtime 在运行。请关闭既有 Runtime（例如正在运行的 make run \
                或 MCP 预览），再重启桌面应用。"
            .to_string();
    }
    if !tail.is_empty() {
        return format!("Runtime 启动后退出：{}", last_lines(tail, 3));
    }
    match code {
        Some(code) => format!("Runtime 启动后退出（退出码 {code}），无诊断输出"),
        None => "Runtime 启动后被外部信号终止".to_string(),
    }
}

fn last_lines(text: &str, count: usize) -> String {
    let lines: Vec<&str> = text.lines().collect();
    let start = lines.len().saturating_sub(count);
    lines[start..].join("\n")
}

fn start_stderr_drain(mut stderr: impl Read + Send + 'static, tail: Arc<Mutex<String>>) {
    std::thread::spawn(move || {
        let mut chunk = [0u8; 1024];
        loop {
            match stderr.read(&mut chunk) {
                Ok(0) => return,
                Ok(read) => {
                    let mut tail = tail.lock().unwrap();
                    tail.push_str(&String::from_utf8_lossy(&chunk[..read]));
                    if tail.len() > STDERR_TAIL_BYTES {
                        let keep_from = tail.len() - STDERR_TAIL_BYTES;
                        tail.replace_range(..keep_from, "");
                    }
                }
                Err(_) => return,
            }
        }
    });
}

fn pick_loopback_port() -> std::io::Result<u16> {
    let listener = TcpListener::bind((Ipv4Addr::LOCALHOST, 0))?;
    listener.local_addr().map(|addr| addr.port())
}

fn generate_token() -> Result<String, getrandom::Error> {
    let mut bytes = [0u8; 32];
    getrandom::getrandom(&mut bytes)?;
    Ok(bytes.iter().map(|byte| format!("{byte:02x}")).collect())
}

/// Ordered python3.11 candidates: explicit override, PATH, then the absolute
/// locations used by common macOS installers (GUI apps get a sparse PATH).
fn python_candidates(
    override_path: Option<PathBuf>,
    path_var: Option<std::ffi::OsString>,
    home: Option<PathBuf>,
) -> Vec<PathBuf> {
    if let Some(override_path) = override_path {
        return vec![override_path];
    }
    let mut candidates = Vec::new();
    if let Some(paths) = path_var {
        for dir in std::env::split_paths(&paths) {
            candidates.push(dir.join("python3.11"));
        }
    }
    if let Some(home) = home {
        candidates.push(home.join(".local/bin/python3.11"));
    }
    candidates.push(PathBuf::from("/usr/local/bin/python3.11"));
    candidates.push(PathBuf::from("/opt/homebrew/bin/python3.11"));
    candidates.push(PathBuf::from("/usr/bin/python3.11"));
    candidates
}

fn resolve_python(
    override_path: Option<PathBuf>,
    path_var: Option<std::ffi::OsString>,
    home: Option<PathBuf>,
) -> Option<PathBuf> {
    python_candidates(override_path, path_var, home)
        .into_iter()
        .find(|candidate| candidate.is_file())
}

fn resolve_repo_root(
    override_root: Option<PathBuf>,
    manifest_dir: &Path,
) -> Result<PathBuf, String> {
    let candidate = match override_root {
        Some(root) => root,
        None => manifest_dir
            .ancestors()
            .nth(3)
            .map(Path::to_path_buf)
            .ok_or_else(|| "无法定位仓库根目录".to_string())?,
    };
    let root = candidate
        .canonicalize()
        .map_err(|error| format!("仓库根目录无效（{}）：{error}", candidate.display()))?;
    if !root.join("runtime/mobile_agent").is_dir() {
        return Err(format!(
            "{} 下缺少 runtime/mobile_agent，请通过 MOBILE_AGENT_REPO_ROOT 指向仓库根目录",
            root.display()
        ));
    }
    Ok(root)
}

fn validate_api_path(path: &str) -> Result<(), String> {
    if path.is_empty() || path.len() > MAX_API_PATH_BYTES {
        return Err("API 路径长度无效".to_string());
    }
    if !path.starts_with("/v1/") {
        return Err("API 路径必须以 /v1/ 开头".to_string());
    }
    if path
        .chars()
        .any(|ch| ch.is_control() || ch.is_whitespace() || ch == '"')
    {
        return Err("API 路径包含非法字符".to_string());
    }
    Ok(())
}

/// Minimal blocking HTTP/1.x GET for the loopback Runtime. The Runtime always
/// sets Content-Length and closes the connection per request (HTTP/1.0), so
/// reading to EOF is both correct and bounded.
fn http_get(port: u16, path: &str, token: &str) -> Result<(u16, Vec<u8>), String> {
    let addr = SocketAddr::from((Ipv4Addr::LOCALHOST, port));
    let mut stream = TcpStream::connect_timeout(&addr, HTTP_CONNECT_TIMEOUT)
        .map_err(|error| format!("连接本地 Runtime 失败：{error}"))?;
    stream
        .set_read_timeout(Some(HTTP_READ_TIMEOUT))
        .map_err(|error| error.to_string())?;
    let request = format!(
        "GET {path} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nAuthorization: Bearer {token}\r\n\
         Accept: application/json\r\nConnection: close\r\n\r\n"
    );
    stream
        .write_all(request.as_bytes())
        .map_err(|error| format!("发送请求失败：{error}"))?;

    let mut raw = Vec::with_capacity(4096);
    let mut chunk = [0u8; 8192];
    loop {
        match stream.read(&mut chunk) {
            Ok(0) => break,
            Ok(read) => {
                raw.extend_from_slice(&chunk[..read]);
                if raw.len() > MAX_HTTP_RESPONSE_BYTES {
                    return Err("Runtime 响应超过大小上限".to_string());
                }
            }
            Err(error) => return Err(format!("读取 Runtime 响应失败：{error}")),
        }
    }

    let header_end = raw
        .windows(4)
        .position(|window| window == b"\r\n\r\n")
        .ok_or_else(|| "Runtime 响应缺少 HTTP 头结束标记".to_string())?;
    let status_line = raw
        .split(|byte| *byte == b'\r')
        .next()
        .ok_or_else(|| "Runtime 响应缺少状态行".to_string())?;
    let status_text = String::from_utf8_lossy(status_line);
    let status = status_text
        .split_whitespace()
        .nth(1)
        .and_then(|code| code.parse::<u16>().ok())
        .ok_or_else(|| format!("Runtime 响应状态行无效：{status_text}"))?;
    Ok((status, raw[header_end + 4..].to_vec()))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn unique_temp_dir(label: &str) -> PathBuf {
        let mut bytes = [0u8; 8];
        getrandom::getrandom(&mut bytes).unwrap();
        let suffix = bytes.iter().map(|b| format!("{b:02x}")).collect::<String>();
        let dir = std::env::temp_dir().join(format!("mobile-agent-desktop-{label}-{suffix}"));
        std::fs::create_dir_all(&dir).unwrap();
        dir
    }

    #[test]
    fn picked_port_is_immediately_reusable() {
        let port = pick_loopback_port().unwrap();
        assert!(port > 0);
        TcpListener::bind((Ipv4Addr::LOCALHOST, port)).unwrap();
    }

    #[test]
    fn generated_tokens_are_64_hex_chars_and_distinct() {
        let first = generate_token().unwrap();
        let second = generate_token().unwrap();
        assert_eq!(first.len(), 64);
        assert!(first.chars().all(|ch| ch.is_ascii_hexdigit()));
        assert_ne!(first, second);
    }

    #[test]
    fn python_override_wins_and_missing_candidates_yield_none() {
        let dir = unique_temp_dir("python");
        let fake = dir.join("python3.11");
        std::fs::write(&fake, b"#!/bin/sh\n").unwrap();
        let resolved = resolve_python(Some(fake.clone()), None, None);
        assert_eq!(resolved, Some(fake));
    }

    #[test]
    fn python_resolution_prefers_home_candidate_over_system_paths() {
        let dir = unique_temp_dir("python-home");
        let home_candidate = dir.join(".local/bin/python3.11");
        std::fs::create_dir_all(home_candidate.parent().unwrap()).unwrap();
        std::fs::write(&home_candidate, b"#!/bin/sh\n").unwrap();
        let resolved = resolve_python(None, None, Some(dir));
        assert_eq!(resolved, Some(home_candidate));
    }

    #[test]
    fn python_candidates_fall_back_to_home_and_system_paths() {
        let home = PathBuf::from("/home/example");
        let candidates = python_candidates(None, None, Some(home.clone()));
        assert!(candidates.contains(&home.join(".local/bin/python3.11")));
        assert!(candidates.contains(&PathBuf::from("/opt/homebrew/bin/python3.11")));
    }

    #[test]
    fn repo_root_requires_runtime_package() {
        let dir = unique_temp_dir("repo");
        let probe = dir.join("apps/desktop/src-tauri");
        std::fs::create_dir_all(&probe).unwrap();
        assert!(resolve_repo_root(None, &probe).is_err());
        std::fs::create_dir_all(dir.join("runtime/mobile_agent")).unwrap();
        let resolved = resolve_repo_root(None, &probe).unwrap();
        assert_eq!(resolved, dir.canonicalize().unwrap());
    }

    #[test]
    fn repo_root_honors_override() {
        let dir = unique_temp_dir("repo-override");
        std::fs::create_dir_all(dir.join("runtime/mobile_agent")).unwrap();
        let resolved = resolve_repo_root(Some(dir.clone()), Path::new("/nonexistent")).unwrap();
        assert_eq!(resolved, dir.canonicalize().unwrap());
    }

    #[test]
    fn api_path_validation_accepts_only_bounded_v1_gets() {
        assert!(validate_api_path("/v1/health").is_ok());
        assert!(validate_api_path("/v1/devices?limit=20").is_ok());
        assert!(validate_api_path("").is_err());
        assert!(validate_api_path("/etc/passwd").is_err());
        assert!(validate_api_path("/v1/with space").is_err());
        assert!(validate_api_path("/v1/with\"quote").is_err());
        assert!(validate_api_path(&format!("/v1/{}", "x".repeat(600))).is_err());
    }

    #[test]
    fn http_get_reads_status_body_and_sends_auth_header() {
        let listener = TcpListener::bind((Ipv4Addr::LOCALHOST, 0)).unwrap();
        let port = listener.local_addr().unwrap().port();
        let server = std::thread::spawn(move || {
            let (mut stream, _) = listener.accept().unwrap();
            let mut request = Vec::new();
            let mut chunk = [0u8; 512];
            loop {
                let read = stream.read(&mut chunk).unwrap();
                if read == 0 {
                    break;
                }
                request.extend_from_slice(&chunk[..read]);
                if request.windows(4).any(|w| w == b"\r\n\r\n") {
                    break;
                }
            }
            let request_text = String::from_utf8_lossy(&request).to_string();
            let body = b"{\"ok\":true}";
            let response = format!(
                "HTTP/1.0 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n",
                body.len()
            );
            stream.write_all(response.as_bytes()).unwrap();
            stream.write_all(body).unwrap();
            request_text
        });
        let (status, body) = http_get(port, "/v1/health", "secret-token").unwrap();
        let request_text = server.join().unwrap();
        assert_eq!(status, 200);
        assert_eq!(body, b"{\"ok\":true}");
        assert!(request_text.contains("Authorization: Bearer secret-token"));
        assert!(request_text.starts_with("GET /v1/health HTTP/1.1"));
    }

    #[test]
    fn early_exit_detail_detects_instance_conflict() {
        let detail = early_exit_detail(
            Some(2),
            "Mobile Agent Runtime 启动失败：同一数据目录已有 Mobile Agent Runtime 正在运行",
        );
        assert!(detail.contains("已有 Runtime"));
        let generic = early_exit_detail(Some(1), "Traceback\nValueError: boom\n");
        assert!(generic.contains("ValueError: boom"));
    }
}
