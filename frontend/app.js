let tasks = new Map();
let activeWorkspace = ".";
let registryModels = [];
let securityFlags = {};
let activeTheme = "sage";
let outputConfig = {};
let currentSession = null;

const $ = (id) => document.getElementById(id);

function statusClass(s) {
  if (s === "done") return "text-bg-success";
  if (s === "error") return "text-bg-danger";
  if (s === "running") return "text-bg-primary";
  if (s === "cancelled") return "text-bg-warning";
  return "text-bg-secondary";
}

async function api(path, opts) {
  const res = await fetch(path, opts);
  let data;
  try {
    data = await res.json();
  } catch (_) {
    data = {error: await res.text()};
  }
  if (!res.ok || data.ok === false) {
    const err = data && data.error;
    throw new Error((err && err.message) || data.message || data.error || `Request failed: ${res.status}`);
  }
  if (data && data.ok === true && Object.prototype.hasOwnProperty.call(data, "data")) return data.data;
  return data;
}

function showError(place, err) {
  const msg = err && err.message ? err.message : String(err);
  if ($(place)) $(place).textContent = msg;
  console.error(err);
}

function esc(str) {
  return String(str || "").replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}

function applyTheme(theme) {
  const allowed = ["sage", "graphite", "ocean", "ember", "iris", "alpine", "sandstone", "contrast"];
  activeTheme = allowed.includes(theme) ? theme : "sage";
  document.documentElement.setAttribute("data-theme", activeTheme);
  localStorage.setItem("rasputin-theme", activeTheme);
  if ($("themeSelect")) $("themeSelect").value = activeTheme;
  document.querySelectorAll("[data-theme-choice]").forEach(btn => {
    btn.classList.toggle("active", btn.getAttribute("data-theme-choice") === activeTheme);
  });
}

function updateActiveProfile() {
  if (!$("activeProfile") || !$("model") || !$("skill") || !$("subagents")) return;
  const model = $("model").value || "model";
  const skill = $("skill").value || "skill";
  const mode = $("taskMode") ? $("taskMode").value : "chat";
  const subagents = Number($("subagents").value || 0);
  $("activeProfile").textContent = `${model} / ${skill} / ${mode} / ${subagents} sub-agent${subagents === 1 ? "" : "s"}`;
  if ($("runtimeSummary")) $("runtimeSummary").textContent = model;
  return;
}

function renderTasks() {
  const box = $("tasks");
  const subBox = $("subtasks");
  const list = [...tasks.values()].sort((a, b) => b.created_at - a.created_at);
  const mainTasks = list.filter(t => !t.parent_id);
  const subTasks = list.filter(t => t.parent_id);
  const running = list.filter(t => t.status === "running").length;

  $("taskCount").textContent = String(list.length);
  $("runningCount").textContent = String(running);
  $("mainTaskCount").textContent = String(mainTasks.length);
  $("subTaskCount").textContent = String(subTasks.length);

  if (!mainTasks.length) {
    box.innerHTML = `<div class="empty-state">No main tasks yet. Start one from the launch panel.</div>`;
  } else {
    box.innerHTML = mainTasks.map(renderTaskCard).join("");
  }

  if (!subTasks.length) {
    subBox.innerHTML = `<div class="empty-state compact-empty">No sub-agents running.</div>`;
    return;
  }
  subBox.innerHTML = subTasks.map(renderSubTaskCard).join("");
}

function renderTaskCard(t) {
  const spinning = t.status === "running" ? `<span class="spinner-border spinner-border-sm"></span>` : "";
  const response = t.result || (t.logs || []).slice(-10).join("\n") || "Queued.";
  const canExport = t.result ? `<button class="ghost-btn compact" type="button" data-export-task="${esc(t.id)}">Export Markdown</button>` : "";
  const canCancel = ["queued", "running"].includes(t.status) ? `<button class="ghost-btn compact" type="button" data-cancel-task="${esc(t.id)}">Cancel</button>` : "";
  return `<article class="task-card thread-item">
      <div class="message user-message">
        <div class="message-label">You</div>
        <div class="message-body">${esc(t.objective)}</div>
      </div>
      <div class="message assistant-message">
        <div class="message-top">
          <div class="meta-row">
            <span class="badge ${statusClass(t.status)}">${esc(t.status)}</span>
            <span class="badge text-bg-light">${esc(t.model)}</span>
            <span class="badge text-bg-light">${esc(t.skill)}</span>
            <span class="badge text-bg-light">${esc(t.mode || "chat")}</span>
            <span class="badge text-bg-light">${esc(t.workspace || ".")}</span>
            ${t.parent_id ? `<span class="badge text-bg-warning">sub</span>` : ""}
            ${spinning}
          </div>
          <div class="meta-row">${canCancel}${canExport}</div>
        </div>
        <div class="progress">
          <div class="progress-bar" style="width:${Number(t.progress) || 0}%"></div>
        </div>
        <pre class="message-result">${esc(response)}</pre>
        ${renderSources(t.sources || [])}
        ${renderGraph(t.graph || [])}
        ${t.logs && t.logs.length ? `<details class="mt-2"><summary>Logs</summary><pre class="log-box mini">${esc((t.logs || []).join("\n"))}</pre></details>` : ""}
      </div>
    </article>`;
}

function renderSubTaskCard(t) {
  const spinning = t.status === "running" ? `<span class="spinner-border spinner-border-sm"></span>` : "";
  return `<article class="subtask-card">
    <div class="subtask-top">
      <span class="badge ${statusClass(t.status)}">${esc(t.status)}</span>
      ${spinning}
    </div>
    <div class="task-title small-title">${esc(t.objective)}</div>
    <div class="meta-row tighter">
      <span class="badge text-bg-light">${esc(t.model)}</span>
      <span class="badge text-bg-light">${esc(t.skill)}</span>
    </div>
    <div class="progress">
      <div class="progress-bar" style="width:${Number(t.progress) || 0}%"></div>
    </div>
    <pre class="log-box mini">${esc((t.logs || []).slice(-6).join("\n"))}</pre>
  </article>`;
}

function renderSources(sources) {
  if (!sources.length) return "";
  return `<details class="mt-2"><summary>Sources</summary>
    <ul class="source-list">${sources.map(s => `<li>${esc(s.source)}#${esc(s.chunk)} <span>${esc(s.score)}</span></li>`).join("")}</ul>
  </details>`;
}

function renderGraph(edges) {
  if (!edges.length) return "";
  return `<details class="mt-2"><summary>Graph</summary>
    <ul class="source-list">${edges.map(e => `<li>${esc(e.source)} --${esc(e.relation)}--&gt; ${esc(e.target)}</li>`).join("")}</ul>
  </details>`;
}

function renderRagStats(stats) {
  $("ragStats").textContent = `${stats.docs} docs, ${stats.chunks} chunks`;
}

function renderRagResults(results) {
  const hits = results.hits || [];
  $("ragResults").innerHTML = hits.length ? hits.map(h => `
    <div class="rag-hit">
      <div class="rag-source">${esc(h.source)}#${esc(h.chunk)} - ${esc(h.score)}</div>
      <div>${esc(h.text.slice(0, 360))}</div>
    </div>
  `).join("") : `<div class="small text-secondary">No matches.</div>`;
}

function renderGraphStats(stats) {
  $("graphStats").textContent = `${stats.nodes} nodes, ${stats.edges} edges`;
}

function renderGraphResults(results) {
  const nodes = results.nodes || [];
  const edges = results.edges || [];
  if (!nodes.length && !edges.length) {
    $("graphResults").innerHTML = `<div class="small text-secondary">No graph matches.</div>`;
    return;
  }
  $("graphResults").innerHTML = `
    ${nodes.slice(0, 5).map(n => `<div class="rag-hit"><div class="rag-source">${esc(n.name)}</div><div>${esc(n.kind)} - weight ${esc(n.weight)}</div></div>`).join("")}
    ${edges.map(e => `<div class="rag-hit"><div class="rag-source">${esc(e.source)}</div><div>--${esc(e.relation)}--&gt; ${esc(e.target)}</div></div>`).join("")}
  `;
}

function renderWorkspace(info) {
  activeWorkspace = info.active_path || ".";
  $("workspaceActive").textContent = `Active: ${activeWorkspace}`;
  $("workspacePill").textContent = `workspace: ${activeWorkspace}`;
  $("workspacePath").value = activeWorkspace;
  $("ragPath").value = activeWorkspace;
  renderWorkspaceRegistry(info.workspaces || [], info.active_id);
}

function renderWorkspaceRegistry(workspaces, activeId) {
  const box = $("workspaceRegistry");
  if (!box) return;
  box.innerHTML = (workspaces || []).map(w => `
    <div class="workspace-item">
      <div>
        <strong>${esc(w.name || w.id)}</strong>
        <span class="muted-line">${esc(w.root || w.absolute_path || ".")}</span>
      </div>
      <div class="meta-row">
        ${w.id === activeId ? `<span class="badge text-bg-success">active</span>` : `<button class="ghost-btn compact" type="button" data-select-workspace="${esc(w.id)}">Use</button>`}
        ${w.id !== "project-root" ? `<button class="ghost-btn compact danger-text" type="button" data-remove-workspace="${esc(w.id)}">Remove</button>` : ""}
      </div>
    </div>
  `).join("") || `<div class="small text-secondary">No approved workspaces.</div>`;
}

function renderWorkspaceDirs(list) {
  $("workspaceDirs").innerHTML = (list.dirs || []).map(d => `
    <button type="button" class="dir-btn" data-path="${esc(d.path)}">${esc(d.name)}</button>
  `).join("") || `<div class="small text-secondary">No folders here.</div>`;
  document.querySelectorAll(".dir-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      const path = btn.getAttribute("data-path");
      const list = await api("/api/workspace/list", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({path}),
      });
      $("workspacePath").value = list.path;
      renderWorkspaceDirs(list);
    });
  });
}

function renderModelRegistry(models) {
  registryModels = models || [];
  $("modelRegistry").innerHTML = registryModels.map(m => {
    const managed = m.managed ? `<span class="badge text-bg-info">managed</span>` : `<span class="badge text-bg-secondary">external</span>`;
    const status = m.container_status ? `<span class="badge text-bg-light">${esc(m.container_status)}</span>` : "";
    const runtime = m.runtime_status ? `<span class="badge text-bg-light">${esc(m.runtime_status)}</span>` : "";
    return `<div class="model-row">
      <div>
        <div class="model-name">${esc(m.name || m.key)}</div>
        <div class="model-meta">${esc(m.key)} - ${esc(m.provider)} - ${esc(m.role || "general")} - ${esc(m.base_url || "")}</div>
      </div>
      <div class="model-actions">
        ${managed}
        ${status}
        ${runtime}
        <button class="btn btn-sm btn-outline-primary" data-model-action="test" data-key="${esc(m.key)}" type="button">Test</button>
        ${m.managed ? `<button class="btn btn-sm btn-outline-success" data-model-action="start" data-key="${esc(m.key)}" type="button">Start</button>
        <button class="btn btn-sm btn-outline-danger" data-model-action="stop" data-key="${esc(m.key)}" type="button">Stop</button>
        <button class="btn btn-sm btn-outline-secondary" data-model-action="logs" data-key="${esc(m.key)}" type="button">Logs</button>` : ""}
      </div>
    </div>`;
  }).join("") || `<div class="small text-secondary">No models registered.</div>`;

  document.querySelectorAll("[data-model-action]").forEach(btn => {
    btn.addEventListener("click", async () => {
      try {
        const action = btn.getAttribute("data-model-action");
        const key = btn.getAttribute("data-key");
        $("modelMsg").textContent = `${action} ${key}...`;
        const out = await api(`/api/model-registry/${action}`, {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({key}),
        });
        $("modelMsg").textContent = JSON.stringify(out);
        if (action === "logs") $("modelLogs").textContent = out.logs || JSON.stringify(out);
        await loadModels();
      } catch (err) {
        showError("modelMsg", err);
      }
    });
  });
}

function renderSecurity(flags) {
  securityFlags = flags || {};
  [
    "privacy_lock", "allow_file_read", "allow_file_write", "allow_file_reorganize",
    "allow_shell_execution", "allow_web_search", "allow_docker_control", "allow_model_tests",
    "allow_model_registry_edit", "allow_remote_models", "approval_required_file_write",
    "approval_required_file_move", "approval_required_web_search", "audit_enabled"
  ].forEach(id => {
    if ($(id)) $(id).checked = !!securityFlags[id];
  });
  $("web_search_max_chars").value = securityFlags.web_search_max_chars || 180;
  $("privacyStatus").innerHTML = securityFlags.privacy_lock
    ? `<span class="badge text-bg-success">local model endpoints only</span> <span class="badge text-bg-info">brokered web search</span>`
    : `<span class="badge text-bg-warning">privacy lock off</span>`;
  if ($("navPrivacySummary")) {
    $("navPrivacySummary").textContent = securityFlags.privacy_lock ? "locked" : "review";
    $("navPrivacySummary").className = securityFlags.privacy_lock ? "dot privacy ok" : "dot privacy warn";
  }
  $("sidebarStatus").innerHTML = `
    <div class="guardrail-item ${securityFlags.privacy_lock ? "ok" : "warn"}"><span>Privacy lock</span><strong>${securityFlags.privacy_lock ? "On" : "Off"}</strong></div>
    <div class="guardrail-item ${securityFlags.allow_remote_models ? "warn" : "ok"}"><span>Remote models</span><strong>${securityFlags.allow_remote_models ? "Allowed" : "Blocked"}</strong></div>
    <div class="guardrail-item ${securityFlags.allow_docker_control ? "warn" : "ok"}"><span>Docker control</span><strong>${securityFlags.allow_docker_control ? "On" : "Off"}</strong></div>
    <div class="guardrail-item ${securityFlags.allow_file_reorganize ? "warn" : "ok"}"><span>Reorganize</span><strong>${securityFlags.allow_file_reorganize ? "On" : "Off"}</strong></div>
    <div class="guardrail-item ${securityFlags.approval_required_file_write ? "ok" : "warn"}"><span>Write approval</span><strong>${securityFlags.approval_required_file_write ? "On" : "Off"}</strong></div>
  `;
}

function renderOutput(cfg) {
  outputConfig = cfg || {};
  if ($("outputFolder")) $("outputFolder").value = outputConfig.markdown_folder || "workspace/markdown-output";
  if ($("outputStatus")) $("outputStatus").textContent = `Markdown folder: ${outputConfig.markdown_folder || "workspace/markdown-output"}`;
}

function setSettingsTab(tab) {
  document.querySelectorAll("[data-settings-tab]").forEach(btn => {
    btn.classList.toggle("active", btn.getAttribute("data-settings-tab") === tab);
  });
  document.querySelectorAll(".settings-pane").forEach(pane => {
    pane.classList.toggle("active", pane.id === `settings-${tab}`);
  });
}

function setupSettingsTabs() {
  document.querySelectorAll("[data-settings-tab]").forEach(btn => {
    btn.addEventListener("click", () => {
      setSettingsTab(btn.getAttribute("data-settings-tab"));
    });
  });
}

function setupSettingsModal() {
  const shell = $("settingsShell");
  const open = (tab = "profile") => {
    setSettingsTab(tab);
    shell.classList.add("open");
    shell.setAttribute("aria-hidden", "false");
  };
  const close = () => {
    shell.classList.remove("open");
    shell.setAttribute("aria-hidden", "true");
  };
  $("settingsOpenBtn").addEventListener("click", () => open("profile"));
  $("settingsOpenTopBtn").addEventListener("click", () => open("profile"));
  $("profileSettingsBtn").addEventListener("click", () => open("profile"));
  document.querySelectorAll("[data-open-settings]").forEach(btn => {
    btn.addEventListener("click", () => {
      open(btn.getAttribute("data-open-settings"));
      document.querySelectorAll(".icon-nav-btn").forEach(item => item.classList.toggle("active", item === btn));
    });
  });
  $("settingsCloseBtn").addEventListener("click", close);
  $("settingsBackdrop").addEventListener("click", close);
  document.querySelectorAll("[data-view='home']").forEach(btn => {
    btn.addEventListener("click", () => {
      close();
      document.querySelectorAll("[data-view]").forEach(item => item.classList.toggle("active", item === btn));
    });
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && shell.classList.contains("open")) close();
  });
}

function setupThemes() {
  applyTheme(localStorage.getItem("rasputin-theme") || localStorage.getItem("local-ai-hub-theme") || "sage");
  $("themeSelect").addEventListener("change", (e) => applyTheme(e.target.value));
  document.querySelectorAll("[data-theme-choice]").forEach(btn => {
    btn.addEventListener("click", () => applyTheme(btn.getAttribute("data-theme-choice")));
  });
}

function renderAudit(events) {
  $("auditLog").textContent = (events || []).slice().reverse().map(e => {
    const date = new Date((e.ts || 0) * 1000).toLocaleString();
    return `${date} ${e.action} ${JSON.stringify(e.detail || {})}`;
  }).join("\n");
}

function renderSession(session) {
  currentSession = session || {};
  if ($("adminSession")) {
    $("adminSession").textContent = currentSession.authenticated
      ? `Signed in as ${currentSession.username || "local"} (${currentSession.role || "admin"})`
      : "Not signed in.";
  }
}

function showLogin(show) {
  if (!$("loginShell")) return;
  $("loginShell").classList.toggle("hidden", !show);
}

async function loadModels() {
  const reg = await api("/api/model-registry");
  renderModelRegistry(reg.models || []);
  const enabled = (reg.models || []).filter(m => m.enabled !== false);
  $("model").innerHTML = enabled.map(m => `<option value="${esc(m.key)}">${esc(m.key)} (${esc(m.role || "model")})</option>`).join("");
  updateActiveProfile();
}

async function loadBasics() {
  const [registry, skills, existing, memory, ragStats, workspaceInfo, graphStats, sec, audit, output] = await Promise.all([
    api("/api/model-registry"),
    api("/api/skills"),
    api("/api/tasks"),
    api("/api/memory"),
    api("/api/rag/stats"),
    api("/api/workspace"),
    api("/api/graph/stats"),
    api("/api/security"),
    api("/api/audit"),
    api("/api/output"),
  ]);
  renderModelRegistry(registry.models || []);
  $("model").innerHTML = (registry.models || []).filter(m => m.enabled !== false).map(m => `<option value="${esc(m.key)}">${esc(m.key)} (${esc(m.role || "model")})</option>`).join("");
  $("skill").innerHTML = skills.map(s => `<option value="${esc(s)}">${esc(s)}</option>`).join("");
  updateActiveProfile();
  existing.forEach(t => tasks.set(t.id, t));
  $("memoryBox").textContent = JSON.stringify(memory, null, 2);
  renderRagStats(ragStats);
  renderWorkspace(workspaceInfo);
  renderGraphStats(graphStats);
  renderSecurity(sec);
  renderAudit(audit.events || []);
  renderOutput(output);
  const dirs = await api("/api/workspace/list", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({path: activeWorkspace}),
  });
  renderWorkspaceDirs(dirs);
  renderTasks();
}

function connectEvents() {
  const ev = new EventSource("/api/events");
  ev.onopen = () => $("conn").textContent = "live";
  ev.onerror = () => $("conn").textContent = "reconnecting";
  ev.onmessage = (msg) => {
    const data = JSON.parse(msg.data);
    if (data.tasks) data.tasks.forEach(t => tasks.set(t.id, t));
    if (data.task) tasks.set(data.task.id, data.task);
    renderTasks();
  };
}

$("workspaceForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const info = await api("/api/workspace/select", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({path: $("workspacePath").value || "."}),
    });
    renderWorkspace(info);
    const dirs = await api("/api/workspace/list", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({path: activeWorkspace}),
    });
    renderWorkspaceDirs(dirs);
  } catch (err) {
    $("workspaceActive").textContent = `Error: ${err.message}`;
  }
});

$("workspaceAddForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    await api("/api/workspace/add", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({path: $("workspaceAddPath").value.trim(), name: $("workspaceAddName").value.trim() || undefined}),
    });
    const info = await api("/api/workspace/select", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({path: $("workspaceAddPath").value.trim()}),
    });
    $("workspaceAddPath").value = "";
    $("workspaceAddName").value = "";
    renderWorkspace(info);
  } catch (err) {
    $("workspaceActive").textContent = `Error: ${err.message}`;
  }
});

$("modelsRefreshBtn").addEventListener("click", loadModels);

$("model").addEventListener("change", updateActiveProfile);
$("skill").addEventListener("change", updateActiveProfile);
$("taskMode").addEventListener("change", updateActiveProfile);
$("subagents").addEventListener("input", updateActiveProfile);

$("securityForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const body = {};
    [
      "privacy_lock", "allow_file_read", "allow_file_write", "allow_file_reorganize",
      "allow_shell_execution", "allow_web_search", "allow_docker_control", "allow_model_tests",
      "allow_model_registry_edit", "allow_remote_models", "approval_required_file_write",
      "approval_required_file_move", "approval_required_web_search", "audit_enabled"
    ].forEach(id => {
      body[id] = $(id).checked;
    });
    body.web_search_max_chars = Number($("web_search_max_chars").value || 180);
    renderSecurity(await api("/api/security", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(body),
    }));
    $("auditLog").textContent = "Safety settings saved.\n" + $("auditLog").textContent;
  } catch (err) {
    showError("auditLog", err);
  }
});

$("outputForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const out = await api("/api/output", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({markdown_folder: $("outputFolder").value || "workspace/markdown-output"}),
    });
    renderOutput(out);
  } catch (err) {
    showError("outputStatus", err);
  }
});

$("auditRefreshBtn").addEventListener("click", async () => {
  const out = await api("/api/audit");
  renderAudit(out.events || []);
});

$("endpointModelForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const model = {
      key: $("endpointKey").value.trim(),
      name: $("endpointName").value.trim(),
      provider: "vllm",
      role: $("endpointRole").value.trim() || "main",
      base_url: $("endpointBaseUrl").value.trim(),
      model: $("endpointModelId").value.trim(),
      enabled: true,
      managed: false,
      notes: "External OpenAI-compatible endpoint.",
    };
    const out = await api("/api/model-registry/upsert", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(model),
    });
    $("modelMsg").textContent = `Saved ${out.key}`;
    await loadModels();
  } catch (err) {
    showError("modelMsg", err);
  }
});

$("ggufImportForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const body = {
      path: $("ggufPath").value.trim(),
      name: $("ggufName").value.trim() || undefined,
      role: $("ggufRole").value.trim() || "helper",
      port: $("ggufPort").value ? Number($("ggufPort").value) : undefined,
      context: Number($("ggufContext").value || 4096),
      n_gpu_layers: Number($("ggufGpuLayers").value || 0),
    };
    const out = await api("/api/model-registry/import-gguf", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(body),
    });
    $("modelMsg").textContent = `Imported ${out.key}`;
    await loadModels();
  } catch (err) {
    showError("modelMsg", err);
  }
});

$("taskForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const body = {
    objective: $("objective").value,
    model: $("model").value,
    skill: $("skill").value,
    mode: $("taskMode").value || "chat",
    subagents: Number($("subagents").value || 0),
    workspace_path: activeWorkspace,
  };
  const task = await api("/api/tasks", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(body),
  });
  tasks.set(task.id, task);
  $("objective").value = "";
  renderTasks();
});

$("memoryForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = $("memoryText").value.trim();
  if (!text) return;
  const mem = await api("/api/memory", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({kind: "fact", value: text}),
  });
  $("memoryText").value = "";
  $("memoryBox").textContent = JSON.stringify(mem, null, 2);
});

$("refreshBtn").addEventListener("click", async () => {
  const existing = await api("/api/tasks");
  existing.forEach(t => tasks.set(t.id, t));
  renderTasks();
  if ($("runtimeSummary")) $("runtimeSummary").textContent = "Updated";
});

$("ragIngestForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  $("ragStats").textContent = "Indexing...";
  const stats = await api("/api/rag/ingest", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({path: $("ragPath").value || activeWorkspace}),
  });
  $("ragStats").textContent = `${stats.total_docs} docs, ${stats.total_chunks} chunks indexed`;
});

$("ragSearchForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const query = $("ragQuery").value.trim();
  if (!query) return;
  const results = await api("/api/rag/search", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({query, limit: 5, path: activeWorkspace}),
  });
  renderRagResults(results);
});

$("graphBuildBtn").addEventListener("click", async () => {
  $("graphStats").textContent = "Graphifying...";
  const stats = await api("/api/graph/build", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({path: activeWorkspace}),
  });
  renderGraphStats(stats);
});

$("graphRefreshBtn").addEventListener("click", async () => {
  $("graphStats").textContent = "Refreshing...";
  renderGraphStats(await api("/api/graph/stats"));
});

$("graphSearchForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const query = $("graphQuery").value.trim();
  if (!query) return;
  const results = await api("/api/graph/search", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({query, limit: 10}),
  });
  renderGraphResults(results);
});

async function logout() {
  await api("/api/auth/logout", {method: "POST"});
  currentSession = null;
  showLogin(true);
  if ($("conn")) $("conn").textContent = "locked";
}

if ($("loginForm")) {
  $("loginForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      $("loginStatus").textContent = "Signing in...";
      const session = await api("/api/auth/login", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({username: $("loginUser").value || "admin", password: $("loginPassword").value}),
      });
      renderSession(session);
      $("loginPassword").value = "";
      $("loginStatus").textContent = "";
      showLogin(false);
      await loadBasics();
      connectEvents();
    } catch (err) {
      $("loginStatus").textContent = err.message;
    }
  });
}

$("logoutBtn").addEventListener("click", logout);
$("logoutSettingsBtn").addEventListener("click", logout);

document.addEventListener("click", async (e) => {
  const selectWorkspace = e.target.closest("[data-select-workspace]");
  if (selectWorkspace) {
    const info = await api("/api/workspace/select", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({path: selectWorkspace.getAttribute("data-select-workspace")}),
    });
    renderWorkspace(info);
    return;
  }
  const removeWorkspace = e.target.closest("[data-remove-workspace]");
  if (removeWorkspace) {
    await api("/api/workspace/remove", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({workspace_id: removeWorkspace.getAttribute("data-remove-workspace")}),
    });
    renderWorkspace(await api("/api/workspace"));
    return;
  }
  const cancelBtn = e.target.closest("[data-cancel-task]");
  if (cancelBtn) {
    const task = await api(`/api/tasks/${cancelBtn.getAttribute("data-cancel-task")}/cancel`, {method: "POST"});
    tasks.set(task.id, task);
    renderTasks();
    return;
  }
  const btn = e.target.closest("[data-export-task]");
  if (!btn) return;
  try {
    btn.disabled = true;
    btn.textContent = "Exporting...";
    const out = await api("/api/output/export-task", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({task_id: btn.getAttribute("data-export-task")}),
    });
    btn.textContent = "Exported";
    if ($("outputStatus")) $("outputStatus").textContent = `Saved: ${out.path}`;
  } catch (err) {
    btn.disabled = false;
    btn.textContent = "Export Markdown";
    if ($("outputStatus")) showError("outputStatus", err);
  }
});

setupThemes();
setupSettingsTabs();
setupSettingsModal();

async function boot() {
  try {
    const session = await api("/api/auth/session");
    renderSession(session);
    if (!session.authenticated) {
      showLogin(true);
      $("conn").textContent = "locked";
      return;
    }
    showLogin(false);
    await loadBasics();
    connectEvents();
  } catch (err) {
    showLogin(true);
    $("conn").textContent = "error";
    if ($("loginStatus")) $("loginStatus").textContent = err.message;
    console.error(err);
  }
}

boot();
