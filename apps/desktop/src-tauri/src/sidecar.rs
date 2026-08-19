//! Python Runtime sidecar lifecycle owned by the desktop process.
//!
//! The desktop spawns `python3.11 -m mobile_agent.api.server` on a random
//! loopback port with a one-time API token passed through the child
//! environment, polls `/v1/health` until ready, and kills the child on app
//! exit. The token never leaves this module; the webview reaches the Runtime
//! through the `runtime_api_get` command and the whitelist-bounded
//! `runtime_api_post` command (task submit/cancel only).

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
/// Screenshot PNG content is larger than JSON responses but stays bounded.
const MAX_ARTIFACT_RESPONSE_BYTES: usize = 12 << 20;
const ARTIFACT_CONTENT_PREFIX: &str = "/v1/artifacts/";
const ARTIFACT_CONTENT_SUFFIX: &str = "/content";
const ARTIFACT_ID_LENGTH: usize = 41; // "artifact_" + 32 lowercase hex
const STDERR_TAIL_BYTES: usize = 4 * 1024;
const MAX_API_PATH_BYTES: usize = 512;
const MAX_API_BODY_BYTES: usize = 16 * 1024;
/// Only these Runtime writes are reachable from the webview: asynchronous
/// Agent task submission and task cancellation. Everything else stays GET-only.
const AGENT_RUN_ASYNC_PATH: &str = "/v1/tasks/agent.run/async";
const TASK_CANCEL_PREFIX: &str = "/v1/task-executions/";
const TASK_CANCEL_SUFFIX: &str = "/cancel";

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
        let (port, token) = self.ready_endpoint()?;
        let (status, body) = http_get(port, path, &token)?;
        parse_api_response(status, &body, &[200])
    }

    /// Execute an authenticated GET for screenshot artifact bytes.
    ///
    /// The path whitelist admits only `/v1/artifacts/{artifact_id}/content`;
    /// the response is bounded and returned base64-encoded for IPC transport.
    pub fn api_get_bytes(&self, path: &str) -> Result<String, String> {
        validate_artifact_content_path(path)?;
        let (port, token) = self.ready_endpoint()?;
        let (status, body) = http_request(
            port,
            "GET",
            path,
            &token,
            None,
            None,
            MAX_ARTIFACT_RESPONSE_BYTES,
        )?;
        // 成功响应是二进制 PNG，只有错误响应才是 JSON，先判状态再解析。
        if status != 200 {
            parse_api_response(status, &body, &[200])?;
        }
        if body.is_empty() {
            return Err("Runtime 返回了空的截图内容".to_string());
        }
        Ok(base64_encode(&body))
    }

    /// Execute an authenticated POST against the sidecar Runtime.
    ///
    /// Restricted to the desktop write whitelist (task submit/cancel). Task
    /// submission gets a fresh Rust-generated Idempotency-Key per call; the
    /// frontend must debounce repeat submissions of the same user intent.
    pub fn api_post(
        &self,
        path: &str,
        body: &serde_json::Value,
    ) -> Result<serde_json::Value, String> {
        validate_api_post_path(path)?;
        let payload =
            serde_json::to_vec(body).map_err(|error| format!("请求体不是有效 JSON：{error}"))?;
        if payload.is_empty() || payload.len() > MAX_API_BODY_BYTES {
            return Err("请求体大小无效".to_string());
        }
        let (port, token) = self.ready_endpoint()?;
        let idempotency_key = (path == AGENT_RUN_ASYNC_PATH)
            .then(|| generate_token().map_err(|error| format!("无法生成幂等键：{error}")))
            .transpose()?;
        let (status, response) = http_request(
            port,
            "POST",
            path,
            &token,
            Some(&payload),
            idempotency_key.as_deref(),
            MAX_HTTP_RESPONSE_BYTES,
        )?;
        parse_api_response(status, &response, &[200, 202])
    }

    fn ready_endpoint(&self) -> Result<(u16, String), String> {
        let inner = self.inner.lock().unwrap();
        if inner.phase != SidecarPhase::Ready {
            return Err("本地 Runtime 尚未就绪".to_string());
        }
        Ok((inner.port, inner.token.clone()))
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

fn parse_api_response(
    status: u16,
    body: &[u8],
    accepted: &[u16],
) -> Result<serde_json::Value, String> {
    let value: serde_json::Value = serde_json::from_slice(body)
        .map_err(|error| format!("Runtime 响应不是有效 JSON：{error}"))?;
    if !accepted.contains(&status) {
        let code = value
            .pointer("/error/code")
            .and_then(serde_json::Value::as_str);
        let message = value
            .pointer("/error/message")
            .and_then(serde_json::Value::as_str)
            .unwrap_or("未知错误");
        return Err(match code {
            Some(code) => format!("{code}：{message}"),
            None => format!("Runtime 返回 {status}：{message}"),
        });
    }
    Ok(value)
}

fn validate_api_post_path(path: &str) -> Result<(), String> {
    validate_api_path(path)?;
    if path == AGENT_RUN_ASYNC_PATH || is_task_cancel_path(path) {
        return Ok(());
    }
    Err("POST 路径不在桌面端白名单内".to_string())
}

/// `/v1/task-executions/task_<32 lowercase hex>/cancel`, mirroring the Runtime
/// route pattern without pulling in a regex dependency.
fn is_task_cancel_path(path: &str) -> bool {
    let Some(rest) = path.strip_prefix(TASK_CANCEL_PREFIX) else {
        return false;
    };
    let Some(task_id) = rest.strip_suffix(TASK_CANCEL_SUFFIX) else {
        return false;
    };
    let Some(hex) = task_id.strip_prefix("task_") else {
        return false;
    };
    hex.len() == 32
        && hex
            .chars()
            .all(|ch| ch.is_ascii_digit() || ('a'..='f').contains(&ch))
}

/// Minimal blocking HTTP/1.x request for the loopback Runtime. The Runtime
/// always sets Content-Length and closes the connection per request
/// (HTTP/1.0), so reading to EOF is both correct and bounded.
fn http_request(
    port: u16,
    method: &str,
    path: &str,
    token: &str,
    body: Option<&[u8]>,
    idempotency_key: Option<&str>,
    max_response_bytes: usize,
) -> Result<(u16, Vec<u8>), String> {
    let addr = SocketAddr::from((Ipv4Addr::LOCALHOST, port));
    let mut stream = TcpStream::connect_timeout(&addr, HTTP_CONNECT_TIMEOUT)
        .map_err(|error| format!("连接本地 Runtime 失败：{error}"))?;
    stream
        .set_read_timeout(Some(HTTP_READ_TIMEOUT))
        .map_err(|error| error.to_string())?;
    let mut request = format!(
        "{method} {path} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nAuthorization: Bearer {token}\r\n\
         Accept: application/json\r\nConnection: close\r\n"
    );
    if let Some(body) = body {
        request.push_str(&format!(
            "Content-Type: application/json\r\nContent-Length: {}\r\n",
            body.len()
        ));
    }
    if let Some(key) = idempotency_key {
        request.push_str(&format!("Idempotency-Key: {key}\r\n"));
    }
    request.push_str("\r\n");
    stream
        .write_all(request.as_bytes())
        .map_err(|error| format!("发送请求失败：{error}"))?;
    if let Some(body) = body {
        stream
            .write_all(body)
            .map_err(|error| format!("发送请求体失败：{error}"))?;
    }

    let mut raw = Vec::with_capacity(4096);
    let mut chunk = [0u8; 8192];
    loop {
        match stream.read(&mut chunk) {
            Ok(0) => break,
            Ok(read) => {
                raw.extend_from_slice(&chunk[..read]);
                if raw.len() > max_response_bytes {
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

fn http_get(port: u16, path: &str, token: &str) -> Result<(u16, Vec<u8>), String> {
    http_request(
        port,
        "GET",
        path,
        token,
        None,
        None,
        MAX_HTTP_RESPONSE_BYTES,
    )
}

/// `/v1/artifacts/artifact_<32 lowercase hex>/content`, mirroring the Runtime
/// route exactly; no regex dependency.
fn validate_artifact_content_path(path: &str) -> Result<(), String> {
    validate_api_path(path)?;
    let rejected = || "Artifact 内容路径不在桌面端白名单内".to_string();
    let Some(rest) = path.strip_prefix(ARTIFACT_CONTENT_PREFIX) else {
        return Err(rejected());
    };
    let Some(artifact_id) = rest.strip_suffix(ARTIFACT_CONTENT_SUFFIX) else {
        return Err(rejected());
    };
    let valid = artifact_id.len() == ARTIFACT_ID_LENGTH
        && artifact_id.starts_with("artifact_")
        && artifact_id[9..]
            .chars()
            .all(|ch| ch.is_ascii_hexdigit() && !ch.is_ascii_uppercase());
    if !valid {
        return Err(rejected());
    }
    Ok(())
}

/// Minimal RFC 4648 base64 encoder; avoids a new crate for one IPC transport.
fn base64_encode(data: &[u8]) -> String {
    const TABLE: &[u8; 64] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    let mut out = String::with_capacity(data.len().div_ceil(3) * 4);
    for chunk in data.chunks(3) {
        let b0 = u32::from(chunk[0]);
        let b1 = u32::from(*chunk.get(1).unwrap_or(&0));
        let b2 = u32::from(*chunk.get(2).unwrap_or(&0));
        let triple = (b0 << 16) | (b1 << 8) | b2;
        out.push(TABLE[((triple >> 18) & 63) as usize] as char);
        out.push(TABLE[((triple >> 12) & 63) as usize] as char);
        out.push(if chunk.len() > 1 {
            TABLE[((triple >> 6) & 63) as usize] as char
        } else {
            '='
        });
        out.push(if chunk.len() > 2 {
            TABLE[(triple & 63) as usize] as char
        } else {
            '='
        });
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn unique_temp_dir(label: &str) -> PathBuf {
        let mut bytes = [0u8; 8];
        getrandom::getrandom(&mut bytes).unwrap();
        let suffix = bytes.iter().map(|b| format!("{b:02x}")).collect::<String>();
        let dir = std::env::temp_dir().join(format!("thumbagent-desktop-{label}-{suffix}"));
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
    fn post_path_whitelist_accepts_only_submit_and_cancel() {
        assert!(validate_api_post_path(AGENT_RUN_ASYNC_PATH).is_ok());
        assert!(validate_api_post_path(
            "/v1/task-executions/task_0123456789abcdef0123456789abcdef/cancel"
        )
        .is_ok());
        // Sync agent.run, skill invoke and arbitrary writes stay blocked.
        assert!(validate_api_post_path("/v1/tasks/agent.run").is_err());
        assert!(validate_api_post_path("/v1/skills/app.open/invoke").is_err());
        assert!(validate_api_post_path("/v1/devices/emulator-5554/observe").is_err());
        // Cancel path must mirror the Runtime route pattern exactly.
        assert!(validate_api_post_path(
            "/v1/task-executions/task_0123456789ABCDEF0123456789abcdef/cancel"
        )
        .is_err());
        assert!(
            validate_api_post_path("/v1/task-executions/task_0123456789abcdef/cancel").is_err()
        );
        assert!(validate_api_post_path(
            "/v1/task-executions/task_0123456789abcdef0123456789abcdef/cancel/extra"
        )
        .is_err());
    }

    #[test]
    fn api_post_sends_body_and_idempotency_key() {
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
                if String::from_utf8_lossy(&request).contains("\"goal\"") {
                    break;
                }
            }
            let request_text = String::from_utf8_lossy(&request).to_string();
            let body = b"{\"task_id\":\"task_0123456789abcdef0123456789abcdef\"}";
            let response = format!(
                "HTTP/1.0 202 Accepted\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n",
                body.len()
            );
            stream.write_all(response.as_bytes()).unwrap();
            stream.write_all(body).unwrap();
            request_text
        });
        let sidecar = Sidecar {
            inner: Mutex::new(SidecarInner {
                phase: SidecarPhase::Ready,
                detail: String::new(),
                child: None,
                port,
                token: "secret-token".to_string(),
                stderr_tail: Arc::new(Mutex::new(String::new())),
            }),
        };
        let payload = serde_json::json!({"device_id": "adb:emulator-5554", "goal": "打开系统设置"});
        let value = sidecar.api_post(AGENT_RUN_ASYNC_PATH, &payload).unwrap();
        let request_text = server.join().unwrap();
        assert_eq!(
            value.pointer("/task_id").and_then(|v| v.as_str()),
            Some("task_0123456789abcdef0123456789abcdef")
        );
        assert!(request_text.starts_with("POST /v1/tasks/agent.run/async HTTP/1.1"));
        assert!(request_text.contains("Authorization: Bearer secret-token"));
        assert!(request_text.contains("Content-Type: application/json"));
        let key_line = request_text
            .lines()
            .find(|line| line.starts_with("Idempotency-Key: "))
            .expect("idempotency key header missing");
        let key = key_line.trim_start_matches("Idempotency-Key: ").trim();
        assert_eq!(key.len(), 64);
        assert!(key.chars().all(|ch| ch.is_ascii_hexdigit()));
        assert!(
            request_text.contains("\"goal\":\"打开系统设置\"")
                || request_text.contains("打开系统设置")
        );
    }

    #[test]
    fn api_post_rejects_oversized_body_and_non_whitelisted_path() {
        let sidecar = Sidecar {
            inner: Mutex::new(SidecarInner {
                phase: SidecarPhase::Ready,
                detail: String::new(),
                child: None,
                port: 1,
                token: "secret-token".to_string(),
                stderr_tail: Arc::new(Mutex::new(String::new())),
            }),
        };
        let oversized = serde_json::json!({"goal": "x".repeat(MAX_API_BODY_BYTES)});
        assert!(sidecar.api_post(AGENT_RUN_ASYNC_PATH, &oversized).is_err());
        let small = serde_json::json!({"goal": "ok"});
        assert!(sidecar.api_post("/v1/tasks/agent.run", &small).is_err());
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
    fn artifact_content_path_whitelist_is_exact() {
        assert!(validate_artifact_content_path(
            "/v1/artifacts/artifact_0123456789abcdef0123456789abcdef/content"
        )
        .is_ok());
        // Other Runtime routes, other artifact suffixes and malformed ids stay blocked.
        assert!(validate_artifact_content_path("/v1/tasks").is_err());
        assert!(validate_artifact_content_path(
            "/v1/artifacts/artifact_0123456789abcdef0123456789abcdef"
        )
        .is_err());
        assert!(validate_artifact_content_path(
            "/v1/artifacts/artifact_0123456789ABCDEF0123456789abcdef/content"
        )
        .is_err());
        assert!(validate_artifact_content_path(
            "/v1/artifacts/artifact_0123456789abcdef0123456789abcde/content"
        )
        .is_err());
        assert!(validate_artifact_content_path(
            "/v1/artifacts/artifact_0123456789abcdef0123456789abcdef/content/extra"
        )
        .is_err());
        assert!(validate_artifact_content_path(
            "/v1/artifacts/artifact_0123456789abcdef0123456789abcdef/../content"
        )
        .is_err());
    }

    #[test]
    fn base64_encode_matches_rfc4648_vectors() {
        assert_eq!(base64_encode(b""), "");
        assert_eq!(base64_encode(b"f"), "Zg==");
        assert_eq!(base64_encode(b"fo"), "Zm8=");
        assert_eq!(base64_encode(b"foo"), "Zm9v");
        assert_eq!(base64_encode(b"foob"), "Zm9vYg==");
        assert_eq!(base64_encode(b"fooba"), "Zm9vYmE=");
        assert_eq!(base64_encode(b"foobar"), "Zm9vYmFy");
    }

    #[test]
    fn api_get_bytes_fetches_binary_body_with_auth() {
        let listener = TcpListener::bind((Ipv4Addr::LOCALHOST, 0)).unwrap();
        let port = listener.local_addr().unwrap().port();
        let png: &[u8] = b"\x89PNG\r\n\x1a\nfake-image-body";
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
            let response = format!(
                "HTTP/1.0 200 OK\r\nContent-Type: image/png\r\nContent-Length: {}\r\n\r\n",
                png.len()
            );
            stream.write_all(response.as_bytes()).unwrap();
            stream.write_all(png).unwrap();
            request_text
        });
        let sidecar = Sidecar {
            inner: Mutex::new(SidecarInner {
                phase: SidecarPhase::Ready,
                detail: String::new(),
                child: None,
                port,
                token: "secret-token".to_string(),
                stderr_tail: Arc::new(Mutex::new(String::new())),
            }),
        };
        let encoded = sidecar
            .api_get_bytes("/v1/artifacts/artifact_0123456789abcdef0123456789abcdef/content")
            .unwrap();
        let request_text = server.join().unwrap();
        assert_eq!(encoded, base64_encode(png));
        assert!(!encoded.is_empty());
        assert!(request_text.contains("Authorization: Bearer secret-token"));
    }

    #[test]
    fn api_get_bytes_rejects_non_whitelisted_path_before_io() {
        let sidecar = Sidecar {
            inner: Mutex::new(SidecarInner {
                phase: SidecarPhase::Ready,
                detail: String::new(),
                child: None,
                port: 1,
                token: "secret-token".to_string(),
                stderr_tail: Arc::new(Mutex::new(String::new())),
            }),
        };
        assert!(sidecar.api_get_bytes("/v1/tasks").is_err());
        assert!(sidecar.api_get_bytes("/v1/devices").is_err());
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
