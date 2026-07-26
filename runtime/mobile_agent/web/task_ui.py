"""Single-file local task history UI."""

from __future__ import annotations


TASK_UI_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Mobile Agent Tasks</title>
  <style>
    :root { color-scheme: light dark; --bg:#0f172a; --panel:#111827; --muted:#94a3b8; --text:#e5e7eb; --line:#243244; --ok:#22c55e; --bad:#f97316; --accent:#38bdf8; }
    * { box-sizing: border-box; }
    body { margin:0; font:14px/1.5 ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background:linear-gradient(135deg,#020617,#111827); color:var(--text); }
    header { padding:28px 32px 18px; border-bottom:1px solid var(--line); }
    h1 { margin:0 0 6px; font-size:28px; letter-spacing:-0.03em; }
    header p { margin:0; color:var(--muted); }
    main { display:grid; grid-template-columns: minmax(320px, 420px) 1fr; gap:18px; padding:18px; min-height:calc(100vh - 98px); }
    section { background:rgba(17,24,39,.82); border:1px solid var(--line); border-radius:18px; overflow:hidden; box-shadow:0 20px 60px rgba(0,0,0,.25); }
    .section-head { display:flex; align-items:center; justify-content:space-between; gap:12px; padding:16px 18px; border-bottom:1px solid var(--line); }
    .section-head h2 { margin:0; font-size:16px; }
    button { cursor:pointer; border:1px solid #334155; background:#172033; color:var(--text); padding:8px 12px; border-radius:10px; }
    button:hover { border-color:var(--accent); }
    button.primary { background:#075985; border-color:#0284c7; }
    button:disabled { opacity:.55; cursor:not-allowed; }
    select { width:100%; margin:10px 0; border:1px solid #334155; background:#0b1220; color:var(--text); padding:9px 10px; border-radius:10px; }
    textarea { width:100%; min-height:74px; resize:vertical; margin:10px 0; border:1px solid #334155; background:#0b1220; color:var(--text); padding:10px; border-radius:10px; font:inherit; }
    .demo { padding:14px 18px; border-bottom:1px solid var(--line); background:rgba(8,13,25,.55); }
    .demo-title { font-weight:650; }
    .demo-copy { color:var(--muted); margin:4px 0 8px; font-size:13px; }
    .demo-actions { display:flex; align-items:center; gap:10px; flex-wrap:wrap; }
    .model-status { margin:10px 0; padding:10px 12px; border:1px solid var(--line); border-radius:12px; background:#0b1220; }
    .model-status.state-active { border-color:#15803d; background:rgba(20,83,45,.22); }
    .model-status.state-unavailable { border-color:#c2410c; background:rgba(124,45,18,.24); }
    .model-status.state-disabled { border-color:#334155; }
    .model-status.state-ready { border-color:#15803d; background:rgba(20,83,45,.22); }
    .model-status.state-attention { border-color:#a16207; background:rgba(113,63,18,.24); }
    .model-status.state-blocked { border-color:#c2410c; background:rgba(124,45,18,.24); }
    .model-status-help { color:var(--muted); font-size:12px; margin-top:6px; }
    .device-cards { display:flex; flex-wrap:wrap; gap:8px; margin:8px 0; }
    .device-card { text-align:left; font-size:12px; }
    .device-inspection { margin:10px 0; padding:12px; border:1px solid var(--line); border-radius:12px; background:#0b1220; }
    .device-inspection[hidden] { display:none; }
    .capability-row { padding:8px 0; border-top:1px solid var(--line); }
    .capability-row:first-child { border-top:0; }
    .goal-draft { margin:10px 0; padding:12px; border:1px solid #0369a1; border-radius:12px; background:rgba(3,105,161,.13); }
    .goal-draft[hidden] { display:none; }
    #demoStatus { color:var(--muted); font-size:13px; }
    #tasks { list-style:none; padding:8px; margin:0; display:flex; flex-direction:column; gap:8px; }
    .task { padding:12px; border:1px solid transparent; border-radius:12px; background:#0b1220; cursor:pointer; }
    .task:hover, .task.active { border-color:var(--accent); }
    .task-title { display:flex; justify-content:space-between; gap:12px; align-items:center; }
    .task-id { color:var(--muted); font-family:ui-monospace, SFMono-Regular, Menlo, monospace; font-size:12px; }
    .status { border-radius:999px; padding:2px 8px; font-size:12px; background:#1e293b; }
    .status.succeeded { color:#bbf7d0; background:#14532d; }
    .status.failed { color:#fed7aa; background:#7c2d12; }
    .status.queued, .status.running, .status.cancelling { color:#bae6fd; background:#075985; }
    .status.cancelled { color:#cbd5e1; background:#334155; }
    .status.timed_out { color:#fde68a; background:#78350f; }
    .goal { margin-top:6px; color:var(--text); }
    .time { margin-top:6px; color:var(--muted); font-size:12px; }
    #detail { padding:18px; }
    .empty { color:var(--muted); padding:18px; }
    .grid { display:grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap:12px; }
    .card { background:#0b1220; border:1px solid var(--line); border-radius:14px; padding:14px; }
    .label { color:var(--muted); font-size:12px; margin-bottom:4px; }
    .value { word-break:break-word; }
    h3 { margin:22px 0 10px; font-size:15px; }
    ol { margin:0; padding-left:22px; }
    li { margin:6px 0; }
    code { font-family:ui-monospace, SFMono-Regular, Menlo, monospace; color:#bae6fd; }
    .error { color:#fed7aa; }
    @media (max-width: 860px) { main { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <header>
    <h1>Mobile Agent Tasks</h1>
    <p>本地任务历史与执行报告。只展示摘要、步骤、证据和事件，不展开完整 UI 树或截图内容。</p>
  </header>
  <main>
    <section>
      <div class="section-head">
        <h2>最近任务</h2>
        <button id="refresh">刷新</button>
      </div>
      <div class="demo">
        <div class="demo-title">安全 Demo 任务</div>
        <div class="demo-copy">打开系统设置，滚动查找并进入显示/亮度页面。该任务需要已连接 Android 设备和 ADB 输入权限。</div>
        <div id="readinessCard" class="model-status">
          <div class="label">Runtime / 设备就绪状态</div>
          <div id="readinessStatus" class="value">加载中…</div>
        </div>
        <div id="modelProviderCard" class="model-status">
          <div class="label">模型 Provider</div>
          <div id="modelProviderStatus" class="value">加载中…</div>
        </div>
        <select id="deviceSelect"><option value="">加载设备中…</option></select>
        <div id="deviceCards" class="device-cards"></div>
        <div id="deviceInspection" class="device-inspection" hidden></div>
        <div class="demo-actions">
          <select id="logLevel" aria-label="最低日志级别">
            <option value="info">日志级别：Info</option>
            <option value="warn">日志级别：Warn</option>
            <option value="error">日志级别：Error</option>
            <option value="debug">日志级别：Debug</option>
          </select>
          <button id="collectLogs" disabled>确认并采集最近 500 行日志</button>
          <button id="capturePerformance" disabled>采集性能快照</button>
          <button id="collectDiagnosticBundle" disabled>确认并采集诊断包</button>
        </div>
        <div id="logCaptureStatus" class="model-status-help"></div>
        <div id="performanceStatus" class="model-status-help"></div>
        <div id="diagnosticBundleStatus" class="model-status-help"></div>
        <label class="label" for="agentGoal">Agent Preview 目标</label>
        <textarea id="agentGoal" maxlength="500" placeholder="例如：进入显示和亮度页面">进入显示和亮度页面</textarea>
        <div id="goalDraft" class="goal-draft" hidden></div>
        <div class="demo-actions">
          <button id="compileGoal" class="primary" disabled>解析目标</button>
          <button id="runCompiledGoal" class="primary" disabled>确认并运行</button>
          <button id="runAgent" class="primary" disabled>运行 Agent Preview</button>
          <button id="cancelExecution" hidden disabled>取消当前任务</button>
          <button id="runDemo" class="primary" disabled>运行安全 Demo</button>
          <button id="resetGoal" type="button">重置目标</button>
          <span id="demoStatus"></span>
        </div>
      </div>
      <ul id="tasks"><li class="empty">加载中…</li></ul>
    </section>
    <section>
      <div class="section-head"><h2>任务报告</h2></div>
      <div id="detail" class="empty">选择左侧任务查看详情。</div>
    </section>
  </main>
  <script>
    const tasksEl = document.querySelector("#tasks");
    const detailEl = document.querySelector("#detail");
    const refreshEl = document.querySelector("#refresh");
    const deviceSelectEl = document.querySelector("#deviceSelect");
    const agentGoalEl = document.querySelector("#agentGoal");
    const goalDraftEl = document.querySelector("#goalDraft");
    const compileGoalEl = document.querySelector("#compileGoal");
    const runCompiledGoalEl = document.querySelector("#runCompiledGoal");
    const runAgentEl = document.querySelector("#runAgent");
    const cancelExecutionEl = document.querySelector("#cancelExecution");
    const runDemoEl = document.querySelector("#runDemo");
    const resetGoalEl = document.querySelector("#resetGoal");
    const demoStatusEl = document.querySelector("#demoStatus");
    const modelProviderCardEl = document.querySelector("#modelProviderCard");
    const modelProviderStatusEl = document.querySelector("#modelProviderStatus");
    const readinessCardEl = document.querySelector("#readinessCard");
    const readinessStatusEl = document.querySelector("#readinessStatus");
    const deviceCardsEl = document.querySelector("#deviceCards");
    const deviceInspectionEl = document.querySelector("#deviceInspection");
    const collectLogsEl = document.querySelector("#collectLogs");
    const logLevelEl = document.querySelector("#logLevel");
    const logCaptureStatusEl = document.querySelector("#logCaptureStatus");
    const capturePerformanceEl = document.querySelector("#capturePerformance");
    const collectDiagnosticBundleEl = document.querySelector("#collectDiagnosticBundle");
    const diagnosticBundleStatusEl = document.querySelector("#diagnosticBundleStatus");
    const performanceStatusEl = document.querySelector("#performanceStatus");
    const API_TOKEN = __MOBILE_AGENT_API_TOKEN__;
    let selectedTaskId = "";
    let compiledGoalSpec = null;
    let activeExecutionId = "";
    let executionPollTimer = null;
    let baselinePerformanceTaskId = "";

    function esc(value) {
      return String(value ?? "").replace(/[&<>"']/g, ch => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;" }[ch]));
    }

    async function getJson(path) {
      const response = await fetch(path, { headers: { "Accept": "application/json" } });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload?.error?.message || response.statusText);
      return payload;
    }

    async function postJson(path, body) {
      const response = await fetch(path, {
        method: "POST",
        headers: {
          "Accept": "application/json",
          "Content-Type": "application/json",
          "Authorization": `Bearer ${API_TOKEN}`
        },
        body: JSON.stringify(body)
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload?.error?.message || response.statusText);
      return payload;
    }

    function newIdempotencyKey() {
      if (globalThis.crypto?.randomUUID) return `web-${globalThis.crypto.randomUUID()}`;
      return `web-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    }

    async function loadReadiness() {
      try {
        const payload = await getJson("/v1/readiness");
        const readiness = payload.readiness || {};
        const gateway = readiness.gateway || {};
        const summary = readiness.summary || {};
        const status = ["ready", "attention", "blocked"].includes(readiness.status) ? readiness.status : "blocked";
        readinessCardEl.className = `model-status state-${esc(status)}`;
        const issues = [];
        if (gateway.issue) issues.push(gateway.issue);
        (readiness.issues || []).forEach(issue => {
          if (!issues.some(existing => existing.code === issue.code)) issues.push(issue);
        });
        const availability = Array.isArray(readiness.devices) ? readiness.devices : [];
        availability.forEach(item => (item.issues || []).forEach(issue => {
          if (!issues.some(existing => existing.code === issue.code)) issues.push(issue);
        }));
        const issueHtml = issues.map(issue => `<div class="error">${esc(issue.code || "-")} · ${esc(issue.message || "")}${issue.suggested_action ? `<div class="model-status-help">下一步：${esc(issue.suggested_action)}</div>` : ""}</div>`).join("");
        readinessStatusEl.innerHTML = `${esc(readinessStateLabel(status))} · ${esc(gateway.platform || "-")}/${esc(gateway.transport || "-")} · ${esc(summary.ready || 0)} ready / ${esc(summary.busy || 0)} busy / ${esc(summary.attention || 0)} attention${issueHtml}`;
        deviceCardsEl.innerHTML = availability.map(item => {
          const device = item.device || {};
          return `<button class="device-card" data-device-id="${esc(device.device_id || "")}">${esc(device.name || device.device_id || "未知设备")} · ${esc(item.status || "unknown")}<br><code>${esc(device.device_id || "-")}</code></button>`;
        }).join("");
        document.querySelectorAll(".device-card").forEach(button => {
          button.addEventListener("click", () => loadDeviceInspection(button.dataset.deviceId));
        });
        const devices = availability.filter(item => item.status === "ready").map(item => item.device);
        if (!devices.length) {
          deviceSelectEl.innerHTML = '<option value="">当前没有可执行任务的设备</option>';
          updateRunButtons();
          return;
        }
        deviceSelectEl.innerHTML = devices.map(device => `<option value="${esc(device.device_id)}">${esc(device.name || device.device_id)} · ${esc(device.device_id)} · ${esc(device.session_id || "无在线会话")}</option>`).join("");
        updateRunButtons();
      } catch (error) {
        readinessCardEl.className = "model-status state-blocked";
        readinessStatusEl.textContent = `就绪状态加载失败：${error.message}`;
        deviceSelectEl.innerHTML = `<option value="">设备加载失败</option>`;
        demoStatusEl.textContent = error.message;
        updateRunButtons();
      }
    }

    function readinessStateLabel(status) {
      if (status === "ready") return "可以执行任务";
      if (status === "attention") return "设备暂时忙碌";
      return "需要处理后才能执行任务";
    }

    async function loadDeviceInspection(deviceId) {
      if (!deviceId) return;
      deviceInspectionEl.hidden = false;
      deviceInspectionEl.textContent = "加载设备能力…";
      try {
        const payload = await getJson(`/v1/devices/${encodeURIComponent(deviceId)}/inspection`);
        const inspection = payload.inspection || {};
        const availability = inspection.availability || {};
        const device = availability.device || {};
        const capabilities = Array.isArray(inspection.capabilities) ? inspection.capabilities : [];
        deviceInspectionEl.innerHTML = `<div class="demo-title">${esc(device.name || device.device_id || "设备详情")}</div>
          <div class="model-status-help">${esc(device.platform || "-")} · ${esc(device.model || "-")} · OS ${esc(device.os_version || "-")} · ${esc(device.connection || "-")} · ${esc(availability.status || "-")}</div>
          <div class="model-status-help">Session：<code>${esc(device.session_id || "-")}</code>${availability.lease_owner_id ? ` · Lease：<code>${esc(availability.lease_owner_id)}</code>` : ""}</div>
          <div>${capabilities.map(renderCapability).join("")}</div>`;
      } catch (error) {
        deviceInspectionEl.innerHTML = `<div class="error">设备详情加载失败：${esc(error.message)}</div>`;
      }
    }

    function renderCapability(capability) {
      const confirmation = capability.confirmation_required ? " · 需要确认" : "";
      const tools = (capability.tools || []).length ? ` · Tools: ${esc(capability.tools.join(", "))}` : "";
      const requirements = (capability.requirements || []).length ? `<div class="model-status-help">要求：${capability.requirements.map(esc).join("；")}</div>` : "";
      const limitations = (capability.limitations || []).length ? `<div class="model-status-help">限制：${capability.limitations.map(esc).join("；")}</div>` : "";
      return `<div class="capability-row"><code>${esc(capability.capability || "-")}</code> · ${esc(capability.availability || "-")} · risk=${esc(capability.risk || "-")}${confirmation}${tools}${requirements}${limitations}</div>`;
    }

    async function loadModelProviderStatus() {
      try {
        const payload = await getJson("/v1/model-provider/status");
        const status = payload.model_provider || {};
        const runtimeStatus = status.status || (status.enabled ? "configured" : "disabled");
        const state = ["active", "unavailable", "disabled", "configured"].includes(runtimeStatus) ? runtimeStatus : "configured";
        modelProviderCardEl.className = `model-status state-${esc(state)}`;
        const enabled = modelProviderStateLabel(runtimeStatus);
        const provider = status.provider || "-";
        const model = status.model || "-";
        const key = status.api_key_ref_configured ? "有密钥引用" : "无密钥引用";
        const error = status.error;
        const errorHtml = error ? `<div class="error">不可用原因：${esc(error.code || "-")} · ${esc(error.message || "")}</div>` : "";
        modelProviderStatusEl.innerHTML = `${esc(enabled)} · provider=${esc(provider)} · model=${esc(model)} · ${esc(key)}${errorHtml}<div class="model-status-help">${modelProviderHelp(runtimeStatus)}</div>`;
      } catch (error) {
        modelProviderCardEl.className = "model-status state-unavailable";
        modelProviderStatusEl.textContent = `模型状态加载失败：${error.message}`;
      }
    }

    function modelProviderStateLabel(status) {
      if (status === "active") return "已接入模型 Planner";
      if (status === "unavailable") return "模型配置不可用";
      if (status === "configured") return "模型配置已读取";
      return "未启用模型";
    }

    function modelProviderHelp(status) {
      if (status === "active") return "Agent Preview 会使用模型 Planner；模型输出仍受 Skill allowlist 和 Policy 约束。";
      if (status === "unavailable") return "请检查 model-provider.json、MOBILE_AGENT_MODEL_CONFIG 和 MOBILE_AGENT_MODEL_SECRET_*。";
      if (status === "configured") return "配置已存在，但当前 Runtime 未声明模型已可用。";
      return "默认使用本地规则 Planner；如需模型，请显式配置本地模型 Provider。";
    }

    function updateRunButtons() {
      const hasDevice = Boolean(deviceSelectEl.value);
      const hasGoal = Boolean(agentGoalEl.value.trim());
      const hasActiveExecution = Boolean(activeExecutionId);
      runDemoEl.disabled = !hasDevice || hasActiveExecution;
      runAgentEl.disabled = !hasDevice || !hasGoal || hasActiveExecution;
      compileGoalEl.disabled = !hasGoal || hasActiveExecution;
      runCompiledGoalEl.disabled = !hasDevice || !compiledGoalSpec || hasActiveExecution;
      cancelExecutionEl.disabled = !activeExecutionId;
      cancelExecutionEl.hidden = !activeExecutionId;
      collectLogsEl.disabled = !hasDevice || hasActiveExecution;
      capturePerformanceEl.disabled = !hasDevice || hasActiveExecution;
      collectDiagnosticBundleEl.disabled = !hasDevice || hasActiveExecution;
    }

    async function collectDeviceLogs() {
      const deviceId = deviceSelectEl.value;
      if (!deviceId) return;
      collectLogsEl.disabled = true;
      logCaptureStatusEl.textContent = "正在采集并脱敏设备日志…";
      try {
        const response = await fetch("/v1/tasks/device.logs.collect/async", {
          method: "POST",
          headers: {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": `Bearer ${API_TOKEN}`,
            "Idempotency-Key": newIdempotencyKey()
          },
          body: JSON.stringify({
            device_id: deviceId,
            max_lines: 500,
            minimum_level: logLevelEl.value,
            confirmed: true,
            deadline_seconds: 60
          })
        });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload?.error?.message || response.statusText);
        activeExecutionId = payload.execution.task_id;
        selectedTaskId = activeExecutionId;
        logCaptureStatusEl.textContent = `日志任务已提交：${payload.execution.status}`;
        updateRunButtons();
        await pollExecution();
      } catch (error) {
        logCaptureStatusEl.textContent = `日志采集失败：${error.message}`;
      } finally {
        updateRunButtons();
      }
    }

    async function captureDevicePerformance() {
      const deviceId = deviceSelectEl.value;
      if (!deviceId) return;
      capturePerformanceEl.disabled = true;
      performanceStatusEl.textContent = "正在提交性能快照任务…";
      try {
        const response = await fetch("/v1/tasks/device.performance.snapshot/async", {
          method: "POST",
          headers: {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": `Bearer ${API_TOKEN}`,
            "Idempotency-Key": newIdempotencyKey()
          },
          body: JSON.stringify({ device_id: deviceId, deadline_seconds: 90 })
        });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload?.error?.message || response.statusText);
        activeExecutionId = payload.execution.task_id;
        selectedTaskId = activeExecutionId;
        performanceStatusEl.textContent = `性能任务已提交：${payload.execution.status}`;
        updateRunButtons();
        await pollExecution();
      } catch (error) {
        performanceStatusEl.textContent = `性能快照失败：${error.message}`;
      } finally {
        updateRunButtons();
      }
    }

    async function collectDiagnosticBundle() {
      const deviceId = deviceSelectEl.value;
      if (!deviceId) return;
      collectDiagnosticBundleEl.disabled = true;
      diagnosticBundleStatusEl.textContent = "正在采集截图、UI Tree、脱敏日志和聚合性能…";
      try {
        const response = await fetch("/v1/tasks/device.diagnostics.bundle/async", {
          method: "POST",
          headers: {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": `Bearer ${API_TOKEN}`,
            "Idempotency-Key": newIdempotencyKey()
          },
          body: JSON.stringify({
            device_id: deviceId,
            max_log_lines: 500,
            minimum_log_level: logLevelEl.value,
            confirmed: true,
            deadline_seconds: 120
          })
        });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload?.error?.message || response.statusText);
        activeExecutionId = payload.execution.task_id;
        selectedTaskId = activeExecutionId;
        diagnosticBundleStatusEl.textContent = `诊断包任务已提交：${payload.execution.status}`;
        updateRunButtons();
        await pollExecution();
      } catch (error) {
        diagnosticBundleStatusEl.textContent = `诊断包采集失败：${error.message}`;
      } finally {
        updateRunButtons();
      }
    }

    async function compileGoal() {
      const goal = agentGoalEl.value.trim();
      if (!goal) return;
      compileGoalEl.disabled = true;
      demoStatusEl.textContent = "正在解析目标…";
      try {
        const payload = await postJson("/v1/goals/compile", { goal });
        compiledGoalSpec = payload.goal_spec;
        const assumptions = compiledGoalSpec.assumptions || [];
        const acceptance = compiledGoalSpec.acceptance ? `<code>${esc(JSON.stringify(compiledGoalSpec.acceptance))}</code>` : "未生成，请由 Planner finish 验证";
        goalDraftEl.hidden = false;
        goalDraftEl.innerHTML = `<div class="demo-title">GoalSpec 草案（确认前不会操作设备）</div>
          <div class="label">执行目标</div><div>${esc(compiledGoalSpec.execution_goal)}</div>
          <div class="label">假设</div><div>${assumptions.length ? assumptions.map(esc).join("；") : "无"}</div>
          <div class="label">置信度 / 来源</div><div>${esc(compiledGoalSpec.confidence)} / ${esc(compiledGoalSpec.source)}</div>
          <div class="label">成功条件</div><div>${acceptance}</div>`;
        demoStatusEl.textContent = "目标草案已生成，请检查后确认运行。";
      } catch (error) {
        compiledGoalSpec = null;
        goalDraftEl.hidden = true;
        demoStatusEl.textContent = `目标解析失败：${error.message}`;
      } finally {
        updateRunButtons();
      }
    }

    async function runAgentTask(goalSpec = null) {
      const deviceId = deviceSelectEl.value;
      const goal = agentGoalEl.value.trim();
      if (!deviceId || !goal) {
        demoStatusEl.textContent = "请选择设备并输入目标。";
        updateRunButtons();
        return;
      }
      runAgentEl.disabled = true;
      runDemoEl.disabled = true;
      demoStatusEl.textContent = "正在提交 Agent 任务…";
      try {
        const request = {
          device_id: deviceId,
          goal,
          confirmed: true,
          max_rounds: 6,
          deadline_seconds: 600
        };
        if (goalSpec) {
          request.goal_spec = goalSpec;
          request.goal_spec_confirmed = true;
        }
        const response = await fetch("/v1/tasks/agent.run/async", {
          method: "POST",
          headers: {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": `Bearer ${API_TOKEN}`,
            "Idempotency-Key": newIdempotencyKey()
          },
          body: JSON.stringify(request)
        });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload?.error?.message || response.statusText);
        activeExecutionId = payload.execution.task_id;
        selectedTaskId = activeExecutionId;
        demoStatusEl.textContent = `任务已提交：${payload.execution.status}`;
        updateRunButtons();
        await pollExecution();
      } catch (error) {
        demoStatusEl.textContent = `Agent 运行失败：${error.message}`;
      } finally {
        updateRunButtons();
      }
    }

    async function pollExecution() {
      if (!activeExecutionId) return;
      if (executionPollTimer) clearTimeout(executionPollTimer);
      const taskId = activeExecutionId;
      try {
        const executionPayload = await getJson(`/v1/task-executions/${encodeURIComponent(taskId)}`);
        const eventPayload = await getJson(`/v1/task-executions/${encodeURIComponent(taskId)}/events`);
        const execution = executionPayload.execution;
        detailEl.className = "";
        detailEl.innerHTML = renderExecution(execution, eventPayload.events || []);
        if (execution.task_type === "device.logs.collect") {
          logCaptureStatusEl.textContent = `日志采集任务：${execution.status}`;
        } else if (execution.task_type === "device.performance.snapshot") {
          performanceStatusEl.textContent = `性能快照任务：${execution.status}`;
        } else {
          demoStatusEl.textContent = `Agent 任务：${execution.status}`;
        }
        const terminal = ["succeeded", "failed", "cancelled", "timed_out"].includes(execution.status);
        if (terminal) {
          activeExecutionId = "";
          updateRunButtons();
          await loadReadiness();
          await loadTasks();
          if (execution.result_available) await loadDetail(taskId);
          return;
        }
        executionPollTimer = setTimeout(pollExecution, 1200);
      } catch (error) {
        demoStatusEl.textContent = `任务进度加载失败：${error.message}`;
        executionPollTimer = setTimeout(pollExecution, 2500);
      }
    }

    async function cancelExecution() {
      if (!activeExecutionId) return;
      cancelExecutionEl.disabled = true;
      try {
        const payload = await postJson(
          `/v1/task-executions/${encodeURIComponent(activeExecutionId)}/cancel`,
          {}
        );
        demoStatusEl.textContent = `取消请求已记录：${payload.execution.status}`;
        await pollExecution();
      } catch (error) {
        demoStatusEl.textContent = `取消失败：${error.message}`;
        updateRunButtons();
      }
    }

    function renderExecution(execution, events) {
      return `<div class="grid">
        ${card("执行状态", `<span class="status ${esc(execution.status)}">${esc(execution.status)}</span>`)}
        ${card("任务", `<code>${esc(execution.task_id)}</code>`)}
        ${card("目标", esc(execution.goal))}
        ${card("设备", esc(execution.device_id))}
        ${card("设备会话", esc(execution.device_session_id || "等待绑定"))}
        ${card("提交时间", esc(execution.submitted_at))}
        ${card("Deadline", `${esc(execution.deadline_seconds)} 秒<br>${esc(execution.deadline_at || "等待开始")}`)}
        ${card("取消请求", execution.cancel_requested ? "已请求，将在安全边界停止" : "未请求")}
      </div>
      <h3>实时事件</h3>
      ${renderEvents(events)}
      ${execution.error ? `<h3>执行状态说明</h3><div class="card error">${esc(execution.error.code)} · ${esc(execution.error.message || "")}</div>` : ""}`;
    }

    async function runDemoTask() {
      const deviceId = deviceSelectEl.value;
      if (!deviceId) return;
      runDemoEl.disabled = true;
      demoStatusEl.textContent = "任务运行中…";
      try {
        const payload = await postJson("/v1/tasks/settings.scroll_navigate/run", {
          device_id: deviceId,
          goal: "进入系统设置的显示/亮度页面",
          direction: "up",
          max_scrolls: 8,
          distance_percent: 0.35,
          duration_ms: 900,
          settle_seconds: 1.0,
          confirmed: true,
          target_selector: {
            strategy: "text",
            value: "亮度",
            match: "contains",
            resolve_clickable_ancestor: true
          },
          expected_selector: {
            strategy: "text",
            value: "亮度",
            match: "contains",
            ancestor_path: [
              { strategy: "resource_id", value: "action_bar", match: "contains" }
            ]
          }
        });
        demoStatusEl.textContent = `已完成：${payload.task.status}`;
        await loadReadiness();
        await loadTasks();
        await loadDetail(payload.task.task_id);
      } catch (error) {
        demoStatusEl.textContent = `运行失败：${error.message}`;
      } finally {
        updateRunButtons();
      }
    }

    async function loadTasks() {
      tasksEl.innerHTML = '<li class="empty">加载中…</li>';
      try {
        const payload = await getJson("/v1/tasks?limit=50");
        const tasks = payload.tasks || [];
        if (!tasks.length) {
          tasksEl.innerHTML = '<li class="empty">暂无历史任务。运行一次任务后会出现在这里。</li>';
          return;
        }
        tasksEl.innerHTML = tasks.map(task => taskItem(task)).join("");
        document.querySelectorAll(".task").forEach(el => {
          el.addEventListener("click", () => loadDetail(el.dataset.taskId));
        });
        if (selectedTaskId) markActive(selectedTaskId);
      } catch (error) {
        tasksEl.innerHTML = `<li class="empty error">加载失败：${esc(error.message)}</li>`;
      }
    }

    function taskItem(task) {
      const status = esc(task.status);
      return `<li class="task" data-task-id="${esc(task.task_id)}">
        <div class="task-title"><span class="task-id">${esc(task.task_id)}</span><span class="status ${status}">${status}</span></div>
        <div class="goal">${esc(task.goal || task.task_type)}</div>
        <div class="time">${esc(task.completed_at)} · ${esc(task.device_id)}</div>
      </li>`;
    }

    async function loadDetail(taskId) {
      selectedTaskId = taskId;
      markActive(taskId);
      detailEl.className = "empty";
      detailEl.textContent = "加载任务报告…";
      try {
        const taskPayload = await getJson(`/v1/tasks/${encodeURIComponent(taskId)}`);
        const eventPayload = await getJson(`/v1/tasks/${encodeURIComponent(taskId)}/events`);
        detailEl.className = "";
        detailEl.innerHTML = renderReport(taskPayload.task, eventPayload.events || []);
        bindPerformanceComparison(taskPayload.task);
      } catch (error) {
        detailEl.className = "empty error";
        detailEl.textContent = `加载失败：${error.message}`;
      }
    }

    function markActive(taskId) {
      document.querySelectorAll(".task").forEach(el => el.classList.toggle("active", el.dataset.taskId === taskId));
    }

    function renderReport(task, events) {
      const summary = task.evidence_summary || {};
      const foreground = summary.final_foreground_app || {};
      const node = summary.verified_node || {};
      return `<div class="grid">
        ${card("状态", `<span class="status ${esc(task.status)}">${esc(task.status)}</span>`)}
        ${card("任务", `<code>${esc(task.task_id)}</code>`)}
        ${card("目标", esc(task.goal))}
        ${card("GoalSpec", task.goal_spec ? `<code>${esc(JSON.stringify(task.goal_spec))}</code>` : "-")}
        ${card("设备", esc(task.device_id))}
        ${card("设备会话", esc(task.device_session_id || "-"))}
        ${card("类型", esc(task.task_type))}
        ${card("完成来源", esc(task.completion_source || "-"))}
        ${card("成功条件", task.goal_acceptance ? `<code>${esc(JSON.stringify(task.goal_acceptance))}</code>` : "-")}
        ${card("Deadline", task.deadline_seconds ? `${esc(task.deadline_seconds)} 秒` : "-")}
        ${card("时间", `${esc(task.started_at)}<br>→ ${esc(task.completed_at)}`)}
      </div>
      ${task.task_type === "device.performance.snapshot" && task.status === "succeeded" ? renderPerformanceActions(task.task_id) : ""}
      <h3>步骤</h3>
      ${renderSteps(task.steps || [])}
      <h3>证据摘要</h3>
      <div class="grid">
        ${card("前台应用", `${esc(foreground.app_id || "-")} / ${esc(foreground.activity || "-")}`)}
        ${card("验证节点", `${esc(node.text || "-")} <br><code>${esc(node.resource_id || "-")}</code>`)}
        ${card("Skill Call", `<code>${esc(summary.skill_call_id || "-")}</code>`)}
        ${card("Tap Action", `<code>${esc(summary.tap_action_id || "-")}</code>`)}
        ${card("Artifacts", (summary.artifact_refs || []).length ? summary.artifact_refs.map(item => `<code>${esc(item)}</code>`).join("<br>") : "-")}
        ${card("日志采集", summary.captured_bytes !== undefined ? `${esc(summary.captured_bytes)} bytes · 脱敏 ${esc(summary.redaction_count || 0)} 处 · ${summary.truncated ? "已截断" : "未截断"}` : "-")}
        ${card("性能快照", summary.cpu_total_usage_percent !== undefined ? `CPU ${esc(summary.cpu_total_usage_percent)}% · 内存 ${esc(summary.memory_used_percent)}% · 电量 ${esc(summary.battery_level_percent)}% · 温度 ${esc(summary.battery_temperature_celsius ?? "-")}°C` : "-")}
        ${card("应用生命周期", summary.operation ? `${esc(summary.operation)} · ${esc(summary.app?.app_id || "-")}<br>前台 ${esc(summary.state?.foreground ?? "-")} · 进程 ${esc(summary.state?.process_present ?? "-")} · stopped ${esc(summary.state?.stopped ?? "-")} · 数据清除 ${esc(summary.data_cleared ?? "-")}` : "-")}
        ${card("诊断包", summary.bundle_artifact ? `${esc(summary.bundle_artifact.artifact_id)} · ${esc(summary.bundle_artifact.size_bytes)} bytes<br><code>${esc(summary.bundle_artifact.relative_path)}</code><br>日志 ${esc(summary.log_summary?.captured_bytes ?? "-")} bytes · CPU ${esc(summary.performance_summary?.cpu?.total_usage_percent ?? "-")}%` : "-")}
      </div>
      <h3>事件</h3>
      ${renderEvents(events)}
      ${task.error ? `<h3>失败原因</h3><div class="card error">${esc(task.error.code)} · ${esc(task.error.message || "")}${renderErrorDiagnostics(task.error)}</div>` : ""}`;
    }

    function renderPerformanceActions(taskId) {
      const isBaseline = baselinePerformanceTaskId === taskId;
      const canCompare = baselinePerformanceTaskId && !isBaseline;
      return `<h3>性能对比</h3>
        <div class="card">
          <div class="label">基线任务：<code>${esc(baselinePerformanceTaskId || "尚未选择")}</code></div>
          <div class="demo-actions">
            <button id="setPerformanceBaseline" type="button">${isBaseline ? "当前已是基线" : "将当前快照设为基线"}</button>
            ${canCompare ? '<button id="comparePerformance" type="button" class="primary">与基线比较</button>' : ""}
          </div>
          <div id="performanceComparisonResult" class="model-status-help">${isBaseline ? "请选择另一条成功的性能快照任务进行比较。" : ""}</div>
        </div>`;
    }

    function bindPerformanceComparison(task) {
      if (task.task_type !== "device.performance.snapshot" || task.status !== "succeeded") return;
      const baselineButton = document.querySelector("#setPerformanceBaseline");
      const compareButton = document.querySelector("#comparePerformance");
      baselineButton?.addEventListener("click", () => {
        baselinePerformanceTaskId = task.task_id;
        loadDetail(task.task_id);
      });
      compareButton?.addEventListener("click", () => comparePerformance(task.task_id));
    }

    async function comparePerformance(candidateTaskId) {
      const resultEl = document.querySelector("#performanceComparisonResult");
      if (!resultEl || !baselinePerformanceTaskId) return;
      resultEl.textContent = "正在比较两次聚合快照…";
      try {
        const payload = await postJson("/v1/performance-comparisons", {
          baseline_task_id: baselinePerformanceTaskId,
          candidate_task_id: candidateTaskId,
        });
        resultEl.innerHTML = renderPerformanceComparison(payload.comparison || {});
      } catch (error) {
        resultEl.textContent = `性能对比失败：${error.message}`;
      }
    }

    function renderPerformanceComparison(comparison) {
      const metrics = comparison.metrics || {};
      const metric = (id, label) => {
        const value = metrics[id] || {};
        const delta = value.delta === null || value.delta === undefined ? "-" : value.delta;
        return `<div><strong>${esc(label)}</strong>：${esc(value.baseline_value ?? "-")} → ${esc(value.candidate_value ?? "-")} · Δ ${esc(delta)} · ${esc(value.trend || "-")}</div>`;
      };
      const session = comparison.same_device_session === true ? "同一设备会话" : comparison.same_device_session === false ? "不同设备会话" : "会话信息不可用";
      return `<div>${esc(comparison.interval_seconds ?? "-")} 秒 · ${esc(session)}</div>
        ${metric("cpu_total_usage_percent", "CPU")}
        ${metric("memory_used_percent", "内存使用率")}
        ${metric("memory_free_bytes", "空闲内存")}
        ${metric("battery_level_percent", "电量")}
        ${metric("battery_temperature_celsius", "电池温度")}
        ${metric("load_average_1m", "1 分钟负载")}
        <div class="label">两点快照只表示方向，不能单独证明因果关系或性能回退。</div>`;
    }

    function card(label, value) {
      return `<div class="card"><div class="label">${label}</div><div class="value">${value}</div></div>`;
    }

    function renderSteps(steps) {
      if (!steps.length) return '<div class="empty">无步骤</div>';
      return `<ol>${steps.map(step => `<li>${esc(step.name)} [${esc(step.status)}]${step.error ? ` <span class="error">${esc(step.error.code)}</span>` : ""}${renderStepDecision(step)}</li>`).join("")}</ol>`;
    }

    function renderStepDecision(step) {
      const decision = step?.result?.decision;
      if (!decision) return "";
      const confidence = decision.confidence === null || decision.confidence === undefined ? "-" : decision.confidence;
      const repair = Number.isInteger(decision.repair_count) && decision.repair_count > 0 ? ` · 模型修复 ${esc(decision.repair_count)} 次` : "";
      const providerRetry = Number.isInteger(decision.provider_retry_count) && decision.provider_retry_count > 0 ? ` · Provider 重试 ${esc(decision.provider_retry_count)} 次` : "";
      const providerAttempts = Number.isInteger(decision.provider_attempt_count) && decision.provider_attempt_count > 0 ? ` · Provider 尝试 ${esc(decision.provider_attempt_count)} 次` : "";
      const providerLatency = Number.isInteger(decision.provider_latency_ms) && decision.provider_latency_ms >= 0 && Number.isInteger(decision.provider_attempt_count) && decision.provider_attempt_count > 0 ? ` · Provider ${esc(decision.provider_latency_ms)} ms` : "";
      const target = decision.tool_id || decision.skill_id || decision.decision_type || "-";
      const argumentsText = decision.arguments && Object.keys(decision.arguments).length ? JSON.stringify(decision.arguments) : "";
      return `<div class="label">Decision: ${esc(target)} · ${esc(decision.source || "-")} · confidence ${esc(confidence)}${repair}${providerRetry}${providerAttempts}${providerLatency}</div><div class="value">${esc(decision.reason || "")}</div>${argumentsText ? `<div class="label"><code>${esc(argumentsText)}</code></div>` : ""}${renderActionFeedback(step?.result?.action_feedback)}`;
    }

    function renderActionFeedback(feedback) {
      if (!feedback) return "";
      return `<div class="label">页面进展：${esc(feedback.effect || "unknown")} · ${esc(feedback.message || "")}</div>`;
    }

    function renderErrorDiagnostics(error) {
      const details = error?.details;
      if (!details || typeof details !== "object") return error?.suggested_action ? `<div class="label">建议：${esc(error.suggested_action)}</div>` : "";
      const scalarKeys = ["failure_kind", "failure_phase", "http_status", "timeout_seconds", "elapsed_ms", "total_elapsed_ms", "provider_attempt_count", "provider_retry_count", "match_count", "tap_y", "safe_top", "safe_bottom", "tool_id", "selector_error", "selector_error_field", "repair_count", "owner_id", "session_id", "lease_expired"];
      const stringArrayKeys = ["argument_keys", "missing_argument_keys", "unknown_argument_keys", "selector_keys", "selector_unknown_keys"];
      const safe = {};
      scalarKeys.forEach(key => {
        const value = details[key];
        if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") safe[key] = value;
      });
      stringArrayKeys.forEach(key => {
        const value = details[key];
        if (Array.isArray(value) && value.every(item => typeof item === "string")) safe[key] = value;
      });
      const diagnostic = Object.keys(safe).length ? `<div class="label">诊断：<code>${esc(JSON.stringify(safe))}</code></div>` : "";
      const suggested = error?.suggested_action ? `<div class="label">建议：${esc(error.suggested_action)}</div>` : "";
      return diagnostic + suggested;
    }

    function renderEvents(events) {
      if (!events.length) return '<div class="empty">无事件</div>';
      return `<ol>${events.map(event => `<li>${esc(event.event_type)} @ ${esc(event.occurred_at)} ${event.payload?.status ? ` · ${esc(event.payload.status)}` : ""}${event.payload?.error_code ? ` · <span class="error">${esc(event.payload.error_code)}</span>` : ""}</li>`).join("")}</ol>`;
    }

    refreshEl.addEventListener("click", () => {
      loadReadiness();
      loadTasks();
    });
    deviceSelectEl.addEventListener("change", updateRunButtons);
    agentGoalEl.addEventListener("input", () => {
      compiledGoalSpec = null;
      goalDraftEl.hidden = true;
      updateRunButtons();
    });
    resetGoalEl.addEventListener("click", () => {
      agentGoalEl.value = "进入显示和亮度页面";
      updateRunButtons();
    });
    compileGoalEl.addEventListener("click", compileGoal);
    runCompiledGoalEl.addEventListener("click", () => runAgentTask(compiledGoalSpec));
    runAgentEl.addEventListener("click", () => runAgentTask());
    cancelExecutionEl.addEventListener("click", cancelExecution);
    runDemoEl.addEventListener("click", runDemoTask);
    collectLogsEl.addEventListener("click", collectDeviceLogs);
    capturePerformanceEl.addEventListener("click", captureDevicePerformance);
    collectDiagnosticBundleEl.addEventListener("click", collectDiagnosticBundle);
    loadModelProviderStatus();
    loadReadiness();
    loadTasks();
  </script>
</body>
</html>
"""
