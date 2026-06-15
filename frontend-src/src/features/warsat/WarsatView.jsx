import React, { useState, useMemo, useEffect } from "react";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Cloud,
  Container,
  Cpu,
  Database,
  Eye,
  Gauge,
  HardDrive,
  Layers,
  Lock,
  MonitorSpeaker,
  Package,
  Pause,
  Play,
  Power,
  RefreshCw,
  Satellite,
  Search,
  Server,
  Shield,
  ShieldCheck,
  ShieldOff,
  SlidersHorizontal,
  Square,
  Unlock,
  Wrench,
  Zap,
} from "lucide-react";
import {
  displayModelName,
  displayWorkspaceName,
  isModelHealthy,
  labelize,
  runtimeStatus,
} from "../../lib/display.js";
import { actionRegistry, useReliableAction } from "../../lib/actionRegistry.js";
import { api, postJson } from "../../api/client.js";

/* ── Tab config ── */
const warsatTabs = [
  { id: "queue",      label: "Queue",      icon: Activity },
  { id: "deploy",     label: "Deploy",     icon: Play },
  { id: "containers", label: "Containers", icon: Server },
  { id: "safety",     label: "Safety",     icon: Shield },
];

/* ── Helpers ── */
function statusColor(st) {
  if (["running", "reachable", "healthy", "ready", "approved", "done", "success"].includes(st)) return "#10B981";
  if (["failed", "error", "denied", "blocked", "unhealthy"].includes(st)) return "var(--ras-danger)";
  if (["paused", "pending", "queued", "warning", "stopped", "unknown"].includes(st)) return "#F59E0B";
  return "var(--cc-muted)";
}

function taskStatusIcon(status) {
  if (["running"].includes(status)) return <Activity size={14} color="#10B981" />;
  if (["queued"].includes(status)) return <Gauge size={14} color="#F59E0B" />;
  if (["paused"].includes(status)) return <Pause size={14} color="#F59E0B" />;
  if (["completed", "done", "success"].includes(status)) return <CheckCircle2 size={14} color="#10B981" />;
  if (["failed", "error", "cancelled"].includes(status)) return <AlertTriangle size={14} color="var(--ras-danger)" />;
  return <Activity size={14} color="var(--cc-muted)" />;
}

/* ═══════════════════════════════════════════
   MAIN COMPONENT
   ═══════════════════════════════════════════ */
export function WarsatView({
  view,
  warsat,
  hardware,
  runtimes,
  plan,
  error,
  createPlan,
  deployPlan,
  deploying,
  deployment,
  operation,
  logs,
  loadLogs,
  runtimeAction,
  approvals,
  approveApproval,
  denyApproval,
  clearPlan,
  refresh,
  modelCatalog,
  modelCatalogLoading,
  modelCatalogError,
  loadModelCatalog,
  prepareCatalogModelForWarsat,
  /* new props for mission control */
  tasks,
  models,
  security,
  cancelTask,
  pauseTask,
  resumeTask,
}) {
  const [activeTab, setActiveTab] = useState("queue");
  const [uiState, setUiState] = useState({ status: "idle", message: "" });
  const executeAction = useReliableAction("WarsatView");

  /* deploy tab state */
  const protocols = warsat?.protocols || [];
  const strengthProfiles = warsat?.strengthProfiles || {};
  const containers = runtimes?.containers || [];
  const catalogItems = modelCatalog?.items || [];
  const catalogCategories = modelCatalog?.categories || [];
  const firstProtocol = protocols[0];
  const [protocolId, setProtocolId] = useState(firstProtocol?.id || "");
  const [strengthProfile, setStrengthProfile] = useState("balanced");
  const [catalogSearch, setCatalogSearch] = useState("");
  const [catalogPurpose, setCatalogPurpose] = useState("all");
  const [selectedCatalogId, setSelectedCatalogId] = useState("");

  useEffect(() => {
    if (!protocolId && firstProtocol?.id) setProtocolId(firstProtocol.id);
  }, [firstProtocol?.id, protocolId]);

  const selectedProtocol = protocols.find(p => p.id === protocolId) || firstProtocol;
  const selectedProfile = strengthProfiles[strengthProfile] || strengthProfiles.balanced || {};

  const warsatCatalogItems = useMemo(() => {
    const search = catalogSearch.trim().toLowerCase();
    return catalogItems
      .filter(item => item.deployable)
      .filter(item => catalogPurpose === "all" || item.purpose === catalogPurpose)
      .filter(item => {
        if (!search) return true;
        return [item.name, item.id, item.modelId, item.provider, item.purpose, ...(item.capabilities || [])].join(" ").toLowerCase().includes(search);
      });
  }, [catalogItems, catalogPurpose, catalogSearch]);

  const selectedCatalogModel = warsatCatalogItems.find(i => i.id === selectedCatalogId) || warsatCatalogItems[0] || null;

  /* deploy state */
  const canDeployPlan = !!plan?.executionEnabled && !!plan?.dockerControlEnabled && !!plan?.dockerCliAvailable;
  const deploymentApprovalId = deployment?.approval?.id || deployment?.approvalId;
  const currentApproval = (approvals?.approvals || []).find(a => a.id === deploymentApprovalId) || deployment?.approval;
  const approvalStatus = currentApproval?.status;
  const approvalPending = deployment?.approvalRequired && (!approvalStatus || approvalStatus === "pending");
  const approvalApproved = deployment?.approvalRequired && approvalStatus === "approved";
  const approvalClosed = deployment?.approvalRequired && ["denied", "expired", "executed"].includes(approvalStatus);
  const approvalReady = !deployment?.approvalRequired || approvalApproved;
  const deployDisabled = !canDeployPlan || deploying || !approvalReady || approvalClosed;
  const lifecycle = deployment?.lifecycle || plan?.lifecycle || [];
  const deploymentFailed = deployment?.status === "failed";
  const deploymentRegistered = deployment?.status === "registered";
  const deployLabel = deploying
    ? "Deploying..."
    : deployment?.approvalRequired
      ? approvalStatus === "approved" ? "Run approved deploy" : approvalClosed ? "Approval closed" : "Waiting for approval"
      : deploymentFailed ? "Request retry approval"
      : deploymentRegistered ? "Request redeploy approval"
      : "Request deploy approval";

  /* reliable actions */
  const handleRefresh = () => executeAction("RefreshWarsat", "system", async () => refresh?.(), setUiState);
  const handleCancel = (id) => executeAction("CancelTask", id, async () => cancelTask?.(id), setUiState);
  const handlePause = (id) => executeAction("PauseTask", id, async () => pauseTask?.(id), setUiState);
  const handleResume = (id) => executeAction("ResumeTask", id, async () => resumeTask?.(id), setUiState);
  const handleLoadLogs = (name) => executeAction("LoadLogs", name, async () => loadLogs?.(name), setUiState);
  const handleRuntimeAction = (action, name) => executeAction(`Runtime_${action}`, name, async () => runtimeAction?.(action, name), setUiState);

  /* derived stats */
  const allTasks = tasks || [];
  const activeTasks = allTasks.filter(t => ["running", "queued", "paused"].includes(t.status));
  const runningTasks = allTasks.filter(t => t.status === "running");
  const failedTasks = allTasks.filter(t => ["failed", "error"].includes(t.status));
  const pendingApprovals = (approvals?.approvals || []).filter(a => a.status === "pending");
  const healthyModels = (models || []).filter(m => isModelHealthy(m));
  const privacyLocked = security?.privacyLock;
  const dockerEnabled = warsat?.dockerControlEnabled;
  const executionEnabled = warsat?.executionEnabled;

  function handleFormChange() { if (plan || error) clearPlan?.(); }

  return (
    <section className={`w2-layout app-view warsat-view ${view === "warsat" ? "active" : ""}`} id="warsatView" data-app-view="warsat">

      {/* ── Commander Dashboard ── */}
      <div className="w2-header-card">
        <div>
          <h1><Satellite size={22} style={{ verticalAlign: "-3px", marginRight: "8px" }} />WarSat Command</h1>
          <p>Mission control for local AI operations.</p>
        </div>
        <div className="w2-header-stats">
          <div className="w2-header-stat">
            <strong style={{ color: "#10B981" }}>{runningTasks.length}</strong>
            <small>Running</small>
          </div>
          <div className="w2-header-stat">
            <strong style={{ color: "#F59E0B" }}>{pendingApprovals.length}</strong>
            <small>Approvals</small>
          </div>
          <div className="w2-header-stat">
            <strong>{containers.length}</strong>
            <small>Containers</small>
          </div>
          <div className="w2-header-stat">
            <strong style={{ color: healthyModels.length > 0 ? "#10B981" : "var(--cc-muted)" }}>{healthyModels.length}</strong>
            <small>Models OK</small>
          </div>
          <div className="w2-header-stat">
            <strong style={{ color: failedTasks.length > 0 ? "var(--ras-danger)" : "var(--cc-muted)" }}>{failedTasks.length}</strong>
            <small>Failures</small>
          </div>
          <div className="w2-header-stat">
            <strong style={{ color: privacyLocked ? "#10B981" : "#F59E0B" }}>
              {privacyLocked ? "Locked" : "Open"}
            </strong>
            <small>Privacy</small>
          </div>
        </div>
      </div>

      {/* ── Tab Bar ── */}
      <div style={{ padding: "0 24px", display: "flex", gap: "12px", overflowX: "auto", marginBottom: "16px" }}>
        {warsatTabs.map(t => {
          const Icon = t.icon;
          return (
            <button key={t.id} className={`w2-button ${activeTab === t.id ? "primary" : ""}`} type="button" onClick={() => setActiveTab(t.id)}>
              <Icon size={16} /> {t.label}
              {t.id === "queue" && activeTasks.length > 0 && (
                <span style={{ fontSize: "0.6875rem", padding: "1px 6px", borderRadius: "999px", background: "#10B981", color: "#fff", marginLeft: "4px" }}>{activeTasks.length}</span>
              )}
              {t.id === "safety" && pendingApprovals.length > 0 && (
                <span style={{ fontSize: "0.6875rem", padding: "1px 6px", borderRadius: "999px", background: "#F59E0B", color: "#fff", marginLeft: "4px" }}>{pendingApprovals.length}</span>
              )}
            </button>
          );
        })}
        <div style={{ flex: 1 }} />
        {uiState.status !== "idle" && (
          <div style={{
            padding: "8px 16px", borderRadius: "4px", fontSize: "0.875rem",
            backgroundColor: uiState.status === "failed" ? "var(--ras-danger)" : uiState.status === "success" ? "#10B981" : "var(--cc-surface)",
            color: "#fff", display: "flex", alignItems: "center",
          }}>
            {uiState.message}
          </div>
        )}
        <button className="w2-button" type="button" onClick={handleRefresh}><RefreshCw size={16} /> Refresh</button>
      </div>

      {/* ── Content ── */}
      <div className="w2-main-grid" style={{ gridTemplateColumns: "1fr 320px" }}>
        <div className="w2-column">

          {/* ═══ QUEUE TAB ═══ */}
          {activeTab === "queue" && (
            <QueueTab
              tasks={allTasks}
              activeTasks={activeTasks}
              failedTasks={failedTasks}
              models={models}
              handleCancel={handleCancel}
              handlePause={handlePause}
              handleResume={handleResume}
            />
          )}

          {/* ═══ DEPLOY TAB ═══ */}
          {activeTab === "deploy" && (
            <DeployTab
              warsat={warsat}
              protocols={protocols}
              strengthProfiles={strengthProfiles}
              protocolId={protocolId}
              setProtocolId={setProtocolId}
              strengthProfile={strengthProfile}
              setStrengthProfile={setStrengthProfile}
              selectedProtocol={selectedProtocol}
              selectedProfile={selectedProfile}
              catalogSearch={catalogSearch}
              setCatalogSearch={setCatalogSearch}
              catalogPurpose={catalogPurpose}
              setCatalogPurpose={setCatalogPurpose}
              catalogCategories={catalogCategories}
              warsatCatalogItems={warsatCatalogItems}
              selectedCatalogModel={selectedCatalogModel}
              setSelectedCatalogId={setSelectedCatalogId}
              modelCatalogLoading={modelCatalogLoading}
              modelCatalogError={modelCatalogError}
              loadModelCatalog={loadModelCatalog}
              prepareCatalogModelForWarsat={prepareCatalogModelForWarsat}
              createPlan={createPlan}
              plan={plan}
              error={error}
              clearPlan={clearPlan}
              handleFormChange={handleFormChange}
              deployPlan={deployPlan}
              deploying={deploying}
              deployment={deployment}
              deployLabel={deployLabel}
              deployDisabled={deployDisabled}
              canDeployPlan={canDeployPlan}
              approvalPending={approvalPending}
              approvalClosed={approvalClosed}
              approvalStatus={approvalStatus}
              currentApproval={currentApproval}
              approveApproval={approveApproval}
              denyApproval={denyApproval}
              lifecycle={lifecycle}
            />
          )}

          {/* ═══ CONTAINERS TAB ═══ */}
          {activeTab === "containers" && (
            <ContainersTab
              containers={containers}
              runtimes={runtimes}
              logs={logs}
              handleLoadLogs={handleLoadLogs}
              handleRuntimeAction={handleRuntimeAction}
              operation={operation}
              approvals={approvals}
              handleRefresh={handleRefresh}
            />
          )}

          {/* ═══ SAFETY TAB ═══ */}
          {activeTab === "safety" && (
            <SafetyTab
              security={security}
              warsat={warsat}
              hardware={hardware}
              pendingApprovals={pendingApprovals}
              approveApproval={approveApproval}
              denyApproval={denyApproval}
              handleRefresh={handleRefresh}
            />
          )}

        </div>

        {/* ── Right Column ── */}
        <div className="w2-column">
          <SafetyLockPanel security={security} warsat={warsat} hardware={hardware} />
          <QuickActionsPanel activeTab={activeTab} handleRefresh={handleRefresh} clearPlan={clearPlan} plan={plan} />
        </div>
      </div>
    </section>
  );
}


/* ═══════════════════════════════════════════
   QUEUE TAB
   ═══════════════════════════════════════════ */
function QueueTab({ tasks, activeTasks, failedTasks, models, handleCancel, handlePause, handleResume }) {
  const [filter, setFilter] = useState("active");
  const displayTasks = useMemo(() => {
    if (filter === "active") return activeTasks;
    if (filter === "failed") return failedTasks;
    return tasks;
  }, [filter, tasks, activeTasks, failedTasks]);

  return (
    <div className="w2-section" style={{ flex: 1 }}>
      <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
        <h2 style={{ margin: 0, fontSize: "1rem" }}>Mission Queue</h2>
        <div style={{ flex: 1 }} />
        <button className={`w2-button ${filter === "active" ? "primary" : ""}`} type="button" onClick={() => setFilter("active")} style={{ fontSize: "0.75rem", padding: "4px 10px" }}>
          Active ({activeTasks.length})
        </button>
        <button className={`w2-button ${filter === "failed" ? "primary" : ""}`} type="button" onClick={() => setFilter("failed")} style={{ fontSize: "0.75rem", padding: "4px 10px" }}>
          Failed ({failedTasks.length})
        </button>
        <button className={`w2-button ${filter === "all" ? "primary" : ""}`} type="button" onClick={() => setFilter("all")} style={{ fontSize: "0.75rem", padding: "4px 10px" }}>
          All ({tasks.length})
        </button>
      </div>

      {displayTasks.map(task => (
        <div key={task.id} className="w2-card" style={{ gap: "8px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
              {taskStatusIcon(task.status)}
              <div>
                <strong style={{ fontSize: "0.875rem" }}>{task.objective || task.id}</strong>
                <div style={{ fontSize: "0.6875rem", color: "var(--cc-muted)" }}>
                  {task.workspace ? displayWorkspaceName(task.workspace) : ""}{task.workspace && task.mode ? " · " : ""}{task.mode ? labelize(task.mode) : ""}
                </div>
              </div>
            </div>
            <span style={{ fontSize: "0.6875rem", padding: "2px 10px", borderRadius: "999px", background: `color-mix(in srgb, ${statusColor(task.status)} 15%, var(--cc-surface))`, color: statusColor(task.status), fontWeight: 600 }}>
              {labelize(task.status)}
            </span>
          </div>

          {task.model && (
            <div style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>
              Model: {displayModelName(task.model, models)}
            </div>
          )}

          <div style={{ display: "flex", gap: "8px" }}>
            {task.status === "running" && (
              <button className="w2-button" type="button" onClick={() => handlePause(task.id)} style={{ fontSize: "0.75rem", padding: "4px 10px" }}>
                <Pause size={12} /> Pause
              </button>
            )}
            {task.status === "paused" && (
              <button className="w2-button primary" type="button" onClick={() => handleResume(task.id)} style={{ fontSize: "0.75rem", padding: "4px 10px" }}>
                <Play size={12} /> Resume
              </button>
            )}
            {["running", "queued", "paused"].includes(task.status) && (
              <button className="w2-button" type="button" onClick={() => handleCancel(task.id)} style={{ fontSize: "0.75rem", padding: "4px 10px", color: "var(--ras-danger)" }}>
                <Square size={12} /> Cancel
              </button>
            )}
          </div>
        </div>
      ))}

      {!displayTasks.length && (
        <div style={{ padding: "32px", textAlign: "center", color: "var(--cc-muted)", backgroundColor: "var(--cc-surface)", borderRadius: "8px" }}>
          {filter === "active" ? "No active missions. Start a task from chat or the planner." : filter === "failed" ? "No failed missions." : "No missions recorded yet."}
        </div>
      )}
    </div>
  );
}


/* ═══════════════════════════════════════════
   DEPLOY TAB
   ═══════════════════════════════════════════ */
function DeployTab({
  warsat, protocols, strengthProfiles, protocolId, setProtocolId,
  strengthProfile, setStrengthProfile, selectedProtocol, selectedProfile,
  catalogSearch, setCatalogSearch, catalogPurpose, setCatalogPurpose,
  catalogCategories, warsatCatalogItems, selectedCatalogModel, setSelectedCatalogId,
  modelCatalogLoading, modelCatalogError, loadModelCatalog, prepareCatalogModelForWarsat,
  createPlan, plan, error, clearPlan, handleFormChange,
  deployPlan, deploying, deployment, deployLabel, deployDisabled, canDeployPlan,
  approvalPending, approvalClosed, approvalStatus, currentApproval,
  approveApproval, denyApproval, lifecycle,
}) {
  return (
    <div className="w2-section" style={{ flex: 1 }}>
      {/* Model Finder */}
      <div className="w2-card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div>
            <h3 style={{ margin: 0, fontSize: "0.875rem" }}>Find A Model</h3>
            <div style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>Search deployable catalog entries to generate a launch plan.</div>
          </div>
          <div style={{ display: "flex", gap: "8px" }}>
            <button className="w2-button" type="button" onClick={() => loadModelCatalog?.(false)} style={{ fontSize: "0.75rem", padding: "4px 10px" }}>Local</button>
            <button className="w2-button primary" type="button" onClick={() => loadModelCatalog?.(true)} disabled={modelCatalogLoading} style={{ fontSize: "0.75rem", padding: "4px 10px" }}>
              {modelCatalogLoading ? "Refreshing..." : "Refresh Remote"}
            </button>
          </div>
        </div>
        <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
          <Search size={14} color="var(--cc-muted)" />
          <input className="w2-input" value={catalogSearch} onChange={e => setCatalogSearch(e.target.value)} placeholder="qwen, coder, 7b, vision..." />
          <select className="w2-input" style={{ width: "130px", flex: "none" }} value={catalogPurpose} onChange={e => setCatalogPurpose(e.target.value)}>
            <option value="all">All deployable</option>
            {catalogCategories.map(c => <option key={c.id} value={c.id}>{c.label}</option>)}
          </select>
        </div>
        <div style={{ fontSize: "0.6875rem", color: "var(--cc-muted)" }}>
          {warsatCatalogItems.length} deployable{modelCatalogError && <span style={{ color: "var(--ras-danger)" }}> · {modelCatalogError}</span>}
        </div>
      </div>

      {/* Catalog results */}
      {warsatCatalogItems.slice(0, 20).map(item => (
        <div key={item.id} className={`w2-list-item ${selectedCatalogModel?.id === item.id ? "is-active" : ""}`} onClick={() => setSelectedCatalogId(item.id)}>
          <div>
            <strong style={{ fontSize: "0.8125rem" }}>{item.name}</strong>
            <div style={{ fontSize: "0.6875rem", color: "var(--cc-muted)" }}>{item.modelId || item.id} · {labelize(item.purpose || "chat")}</div>
          </div>
          <div style={{ display: "flex", gap: "6px", fontSize: "0.6875rem", color: "var(--cc-muted)" }}>
            {item.vramEstimateGb && <span>{item.vramEstimateGb} GB</span>}
            {item.fitLabel && <span style={{ color: item.fitLabel === "Strong fit" ? "#10B981" : item.fitLabel === "Blocked" ? "var(--ras-danger)" : "var(--cc-muted)" }}>{item.fitLabel}</span>}
          </div>
        </div>
      ))}

      {/* Selected model detail + Create Plan */}
      {selectedCatalogModel && (
        <div className="w2-card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <strong style={{ fontSize: "0.875rem" }}>{selectedCatalogModel.name}</strong>
              <div style={{ fontSize: "0.6875rem", color: "var(--cc-muted)" }}>{selectedCatalogModel.modelId || selectedCatalogModel.id}</div>
            </div>
            <button className="w2-button primary" type="button" onClick={() => prepareCatalogModelForWarsat?.(selectedCatalogModel)}>
              <Play size={14} /> Create Plan
            </button>
          </div>
          <div style={{ display: "flex", gap: "16px", fontSize: "0.75rem", color: "var(--cc-muted)", flexWrap: "wrap" }}>
            <span>Use: {labelize(selectedCatalogModel.purpose || "chat")}</span>
            <span>Fit: {selectedCatalogModel.fitLabel || "Unknown"}</span>
            <span>Runtime: {selectedCatalogModel.recommendedProtocol || "vLLM"}</span>
            <span>VRAM: {selectedCatalogModel.vramEstimateGb ? `${selectedCatalogModel.vramEstimateGb} GB` : "Unknown"}</span>
          </div>
          {selectedCatalogModel.summary && <p style={{ fontSize: "0.75rem", color: "var(--cc-muted)", margin: 0 }}>{selectedCatalogModel.summary}</p>}
        </div>
      )}

      {/* Launch Recipe Form */}
      <div className="w2-card">
        <h3 style={{ margin: 0, fontSize: "0.875rem" }}>Launch Recipe</h3>
        <form onSubmit={createPlan} onChange={handleFormChange} style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
          <label style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>
            Protocol
            <select className="w2-input" name="protocolId" value={protocolId} onChange={e => setProtocolId(e.target.value)} required>
              <option value="" disabled>Choose protocol</option>
              {protocols.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </label>
          <label style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>
            Model ID
            <input className="w2-input" name="modelRef" placeholder="Qwen/Qwen2.5-Coder-7B-Instruct" />
          </label>
          <label style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>
            Model Path (GGUF)
            <input className="w2-input" name="modelPath" placeholder="models/my-model.gguf" />
          </label>
          <label style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>
            Host Port
            <input className="w2-input" name="hostPort" type="number" min="1024" max="65535" placeholder="Auto" />
          </label>
          <label style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>
            Role
            <select className="w2-input" name="role" defaultValue={selectedProtocol?.defaultRole || "helper"}>
              <option value="main">Main</option><option value="planner">Planner</option><option value="coder">Coder</option>
              <option value="researcher">Researcher</option><option value="summarizer">Summarizer</option><option value="embeddings">Embeddings</option><option value="helper">Helper</option>
            </select>
          </label>
          <label style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>
            Profile
            <select className="w2-input" name="strengthProfile" value={strengthProfile} onChange={e => setStrengthProfile(e.target.value)}>
              {Object.entries(strengthProfiles).map(([k, p]) => <option key={k} value={k}>{p.label || k}</option>)}
              {!Object.keys(strengthProfiles).length && <option value="balanced">Balanced</option>}
            </select>
          </label>
          <div style={{ gridColumn: "1 / -1", display: "flex", gap: "8px" }}>
            <button className="w2-button primary" type="submit"><Zap size={14} /> Create Plan</button>
            {(plan || error) && <button className="w2-button" type="button" onClick={clearPlan}>Clear</button>}
          </div>
        </form>
        {error && <div style={{ fontSize: "0.75rem", color: "var(--ras-danger)", marginTop: "4px" }}>{error}</div>}
      </div>

      {/* Plan Preview */}
      {plan && <PlanPreview
        plan={plan}
        deployment={deployment}
        deploying={deploying}
        deployLabel={deployLabel}
        deployDisabled={deployDisabled}
        canDeployPlan={canDeployPlan}
        deployPlan={deployPlan}
        approvalPending={approvalPending}
        approvalClosed={approvalClosed}
        approvalStatus={approvalStatus}
        currentApproval={currentApproval}
        approveApproval={approveApproval}
        denyApproval={denyApproval}
        lifecycle={lifecycle}
      />}
    </div>
  );
}


/* ═══════════════════════════════════════════
   PLAN PREVIEW
   ═══════════════════════════════════════════ */
function PlanPreview({ plan, deployment, deploying, deployLabel, deployDisabled, canDeployPlan, deployPlan, approvalPending, approvalClosed, approvalStatus, currentApproval, approveApproval, denyApproval, lifecycle }) {
  return (
    <div className="w2-card" style={{ border: "1px solid var(--cc-accent)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <div style={{ fontSize: "0.6875rem", textTransform: "uppercase", letterSpacing: ".05em", color: "var(--cc-muted)", fontWeight: 600 }}>Launch Plan</div>
          <h3 style={{ margin: "2px 0 0", fontSize: "1rem" }}>{plan.protocolName}</h3>
          <div style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>
            {plan.runtime} on port {plan.hostPort} · {plan.executionEnabled ? "Execution enabled" : "Plan only"}
          </div>
        </div>
        <span style={{ fontSize: "0.6875rem", padding: "2px 10px", borderRadius: "999px", background: plan.securityChecks?.localhostOnly ? "color-mix(in srgb, #10B981 15%, var(--cc-surface))" : "color-mix(in srgb, var(--ras-danger) 15%, var(--cc-surface))", color: plan.securityChecks?.localhostOnly ? "#10B981" : "var(--ras-danger)", fontWeight: 600 }}>
          {plan.securityChecks?.localhostOnly ? "localhost only" : "review binding"}
        </span>
      </div>

      {/* Plan summary grid */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px", fontSize: "0.75rem" }}>
        <div><span style={{ color: "var(--cc-muted)" }}>Model:</span> <strong>{plan.modelRef || plan.modelPath || "Not set"}</strong></div>
        <div><span style={{ color: "var(--cc-muted)" }}>Container:</span> <strong>{plan.containerName}</strong></div>
        <div><span style={{ color: "var(--cc-muted)" }}>Endpoint:</span> <strong>{plan.expectedModelRegistryEntry?.baseUrl || plan.endpoint}</strong></div>
        <div><span style={{ color: "var(--cc-muted)" }}>Profile:</span> <strong>{plan.resourceProfile?.label || plan.strengthProfile}</strong></div>
      </div>

      {/* Deploy actions */}
      <div style={{ display: "flex", gap: "8px", alignItems: "center", padding: "8px 0", borderTop: "1px solid var(--cc-border)" }}>
        {approvalPending && currentApproval?.id && (
          <>
            <button className="w2-button primary" type="button" onClick={() => approveApproval?.(currentApproval.id)}>
              <CheckCircle2 size={14} /> Approve
            </button>
            <button className="w2-button" type="button" onClick={() => denyApproval?.(currentApproval.id)} style={{ color: "var(--ras-danger)" }}>
              Deny
            </button>
          </>
        )}
        <button className={`w2-button ${canDeployPlan ? "primary" : ""}`} type="button" disabled={deployDisabled} onClick={deployPlan}>
          <Play size={14} /> {deployLabel}
        </button>
      </div>

      {/* Lifecycle */}
      {lifecycle.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "0.75rem" }}>
          {lifecycle.map(phase => (
            <div key={phase.id} style={{ display: "flex", gap: "8px", alignItems: "center" }}>
              <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: statusColor(phase.status || "pending"), flexShrink: 0 }} />
              <strong>{phase.label || labelize(phase.id)}</strong>
              <span style={{ color: "var(--cc-muted)" }}>{phase.message}</span>
            </div>
          ))}
        </div>
      )}

      {/* Deployment result */}
      {deployment && (
        <div style={{ padding: "8px 12px", borderRadius: "6px", background: deployment.status === "failed" ? "color-mix(in srgb, var(--ras-danger) 8%, var(--cc-surface))" : "color-mix(in srgb, #10B981 8%, var(--cc-surface))", fontSize: "0.75rem" }}>
          <strong>{deployment.status === "failed" ? "Deployment failed" : deployment.status === "registered" ? "Model registered" : "Deploy updated"}</strong>
          {deployment.lastError && <div style={{ color: "var(--ras-danger)" }}>{deployment.lastError}</div>}
          {deployment.endpoint && <div style={{ color: "var(--cc-muted)" }}>Endpoint: {deployment.endpoint}</div>}
        </div>
      )}
    </div>
  );
}


/* ═══════════════════════════════════════════
   CONTAINERS TAB
   ═══════════════════════════════════════════ */
function ContainersTab({ containers, runtimes, logs, handleLoadLogs, handleRuntimeAction, operation, approvals, handleRefresh }) {
  const operationApproval = (approvals?.approvals || []).find(a => a.id === (operation?.approval?.id || operation?.approvalId)) || operation?.approval;

  return (
    <div className="w2-section" style={{ flex: 1 }}>
      <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
        <h2 style={{ margin: 0, fontSize: "1rem" }}>Managed Runtimes</h2>
        <div style={{ flex: 1 }} />
        <button className="w2-button" type="button" onClick={handleRefresh} style={{ fontSize: "0.75rem", padding: "4px 10px" }}>
          <RefreshCw size={12} /> Refresh
        </button>
      </div>

      {!runtimes?.executionEnabled && (
        <div style={{ padding: "12px", fontSize: "0.75rem", color: "#F59E0B", background: "color-mix(in srgb, #F59E0B 8%, var(--cc-surface))", borderRadius: "6px" }}>
          <AlertTriangle size={13} style={{ verticalAlign: "-2px", marginRight: "4px" }} />
          {runtimes?.message || "Start Rasputin with Docker control and enable it in Safety settings to manage containers."}
        </div>
      )}

      {containers.map(container => (
        <div key={container.name || container.id} className="w2-card" style={{ gap: "8px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
              <Server size={16} color={statusColor(container.status || container.state || "unknown")} />
              <div>
                <strong style={{ fontSize: "0.875rem" }}>{container.name || "Unnamed container"}</strong>
                <div style={{ fontSize: "0.6875rem", color: "var(--cc-muted)" }}>{container.image || "Unknown image"}</div>
              </div>
            </div>
            <span style={{ fontSize: "0.6875rem", padding: "2px 10px", borderRadius: "999px", background: `color-mix(in srgb, ${statusColor(container.status || container.state || "unknown")} 15%, var(--cc-surface))`, color: statusColor(container.status || container.state || "unknown"), fontWeight: 600 }}>
              {labelize(container.status || container.state || "unknown")}
            </span>
          </div>

          <div style={{ display: "flex", gap: "16px", fontSize: "0.75rem", color: "var(--cc-muted)" }}>
            <span>Runtime: {container.runtime || "unknown"}</span>
            <span>Protocol: {container.protocolId || "unknown"}</span>
            <span>Ports: {container.ports || "none"}</span>
          </div>

          <div style={{ display: "flex", gap: "8px" }}>
            <button className="w2-button" type="button" onClick={() => handleLoadLogs(container.name)} style={{ fontSize: "0.75rem", padding: "4px 10px" }}>
              <Eye size={12} /> Logs
            </button>
            <button className="w2-button" type="button" onClick={() => handleRuntimeAction("restart", container.name)} style={{ fontSize: "0.75rem", padding: "4px 10px" }}>
              <RefreshCw size={12} /> Restart
            </button>
            <button className="w2-button" type="button" onClick={() => handleRuntimeAction("stop", container.name)} style={{ fontSize: "0.75rem", padding: "4px 10px", color: "var(--ras-danger)" }}>
              <Square size={12} /> Stop
            </button>
          </div>
        </div>
      ))}

      {!containers.length && (
        <div style={{ padding: "32px", textAlign: "center", color: "var(--cc-muted)", backgroundColor: "var(--cc-surface)", borderRadius: "8px" }}>
          No Warsat-managed containers visible. Deploy a model to get started.
        </div>
      )}

      {/* Container logs */}
      {logs && (
        <div className="w2-card">
          <h3 style={{ margin: 0, fontSize: "0.875rem" }}>Logs: {logs.containerName}</h3>
          <pre style={{ fontSize: "0.75rem", fontFamily: "monospace", whiteSpace: "pre-wrap", background: "var(--cc-bg)", border: "1px solid var(--cc-border)", borderRadius: "6px", padding: "12px", margin: 0, maxHeight: "300px", overflow: "auto" }}>
            {logs.logs || "No logs returned."}
          </pre>
        </div>
      )}
    </div>
  );
}


/* ═══════════════════════════════════════════
   SAFETY TAB
   ═══════════════════════════════════════════ */
function SafetyTab({ security, warsat, hardware, pendingApprovals, approveApproval, denyApproval, handleRefresh }) {
  const checks = hardware?.checks || [];
  const detected = hardware?.detectedHardware || {};

  return (
    <div className="w2-section" style={{ flex: 1 }}>
      {/* Offline status */}
      <div className="w2-card">
        <h3 style={{ margin: 0, fontSize: "0.875rem" }}><ShieldCheck size={14} style={{ verticalAlign: "-2px" }} /> Local-Only Safety Lock</h3>
        <div className="w2-health-grid">
          <div className={`w2-health-item ${security?.privacyLock ? "is-good" : "is-warn"}`}>
            {security?.privacyLock ? <Lock size={14} /> : <Unlock size={14} />}
            Privacy: {security?.privacyLock ? "Locked" : "Unlocked"}
          </div>
          <div className={`w2-health-item ${!security?.allowRemoteModels ? "is-good" : "is-warn"}`}>
            <Cloud size={14} />
            Remote models: {security?.allowRemoteModels ? "Allowed" : "Blocked"}
          </div>
          <div className={`w2-health-item ${warsat?.dockerControlEnabled ? "is-good" : ""}`}>
            <Server size={14} />
            Docker: {warsat?.dockerControlEnabled ? "Enabled" : "Off"}
          </div>
          <div className={`w2-health-item ${warsat?.executionEnabled ? "is-good" : ""}`}>
            <Zap size={14} />
            Execution: {warsat?.executionEnabled ? "Enabled" : "Plan only"}
          </div>
        </div>
      </div>

      {/* System readiness */}
      {hardware && (
        <div className="w2-card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <h3 style={{ margin: 0, fontSize: "0.875rem" }}><Gauge size={14} style={{ verticalAlign: "-2px" }} /> System Readiness</h3>
            <button className="w2-button" type="button" onClick={handleRefresh} style={{ fontSize: "0.75rem", padding: "4px 10px" }}>
              <RefreshCw size={12} /> Refresh
            </button>
          </div>
          {checks.map(check => (
            <div key={check.id} style={{ display: "flex", gap: "8px", alignItems: "flex-start", fontSize: "0.75rem" }}>
              <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: statusColor(check.status), flexShrink: 0, marginTop: "5px" }} />
              <div>
                <strong>{check.label}</strong>
                <div style={{ color: "var(--cc-muted)" }}>{check.message}</div>
                {check.nextStep && <div style={{ color: "#F59E0B", fontSize: "0.6875rem" }}>{check.nextStep}</div>}
              </div>
            </div>
          ))}
          <div style={{ display: "flex", gap: "16px", fontSize: "0.75rem", color: "var(--cc-muted)" }}>
            <span>Docker: {detected.dockerServerVersion || "not detected"}</span>
            <span>GPUs: {(detected.gpus || []).length}</span>
            <span>Runtimes: {(detected.dockerRuntimes || []).join(", ") || "none"}</span>
          </div>
        </div>
      )}

      {/* Pending approvals */}
      {pendingApprovals.length > 0 && (
        <div className="w2-card">
          <h3 style={{ margin: 0, fontSize: "0.875rem" }}><AlertTriangle size={14} style={{ verticalAlign: "-2px", color: "#F59E0B" }} /> Pending Approvals ({pendingApprovals.length})</h3>
          {pendingApprovals.map(approval => (
            <div key={approval.id} className="w2-list-item" style={{ cursor: "default" }}>
              <div>
                <strong style={{ fontSize: "0.8125rem" }}>{approval.summary}</strong>
                <div style={{ fontSize: "0.6875rem", color: "var(--cc-muted)" }}>
                  Code {approval.code} · {approval.actionType || approval.action_type} · {displayWorkspaceName(approval.workspace)}
                </div>
              </div>
              <div style={{ display: "flex", gap: "6px" }}>
                <button className="w2-button primary" type="button" onClick={() => approveApproval(approval.id)} style={{ fontSize: "0.75rem", padding: "4px 10px" }}>
                  Approve
                </button>
                <button className="w2-button" type="button" onClick={() => denyApproval(approval.id)} style={{ fontSize: "0.75rem", padding: "4px 10px", color: "var(--ras-danger)" }}>
                  Deny
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}


/* ═══════════════════════════════════════════
   SAFETY LOCK PANEL (right column)
   ═══════════════════════════════════════════ */
function SafetyLockPanel({ security, warsat, hardware }) {
  const gpus = hardware?.detectedHardware?.gpus || [];
  return (
    <div className="w2-section">
      <h3 className="w2-section-title">Safety Status</h3>
      <div className="w2-card">
        <div style={{ display: "flex", flexDirection: "column", gap: "8px", fontSize: "0.75rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span>Privacy Lock</span>
            <strong style={{ color: security?.privacyLock ? "#10B981" : "#F59E0B" }}>
              {security?.privacyLock ? "LOCKED" : "OPEN"}
            </strong>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span>Remote Models</span>
            <strong style={{ color: !security?.allowRemoteModels ? "#10B981" : "#F59E0B" }}>
              {security?.allowRemoteModels ? "ALLOWED" : "BLOCKED"}
            </strong>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span>Docker Control</span>
            <strong>{warsat?.dockerControlEnabled ? "ON" : "OFF"}</strong>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span>Execution</span>
            <strong>{warsat?.executionEnabled ? "ENABLED" : "PLAN ONLY"}</strong>
          </div>
        </div>
      </div>

      {gpus.length > 0 && (
        <>
          <h3 className="w2-section-title">GPU Hardware</h3>
          <div className="w2-card">
            {gpus.map((gpu, i) => (
              <div key={i} style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>
                <strong style={{ color: "var(--cc-text)" }}>{gpu.name}</strong>
                <div>{gpu.memory_total_mb ? `${(gpu.memory_total_mb / 1024).toFixed(1)} GB VRAM` : "Unknown VRAM"}</div>
              </div>
            ))}
          </div>
        </>
      )}

      <h3 className="w2-section-title">Offline Assurance</h3>
      <div className="w2-card">
        <div style={{ fontSize: "0.75rem", color: "var(--cc-muted)", display: "flex", flexDirection: "column", gap: "4px" }}>
          <span>• All data stays on this machine</span>
          <span>• Model inference runs locally</span>
          <span>• No telemetry, no cloud sync</span>
          <span>• Approval gates all risky actions</span>
          <span>• Privacy lock blocks remote endpoints</span>
        </div>
      </div>
    </div>
  );
}


/* ═══════════════════════════════════════════
   QUICK ACTIONS (right column)
   ═══════════════════════════════════════════ */
function QuickActionsPanel({ activeTab, handleRefresh, clearPlan, plan }) {
  return (
    <div className="w2-section">
      <h3 className="w2-section-title">Quick Actions</h3>
      <div className="w2-card" style={{ gap: "8px" }}>
        <button className="w2-button" type="button" onClick={handleRefresh} style={{ width: "100%" }}>
          <RefreshCw size={14} /> Refresh All
        </button>
        {plan && (
          <button className="w2-button" type="button" onClick={clearPlan} style={{ width: "100%" }}>
            Clear Plan
          </button>
        )}
      </div>
    </div>
  );
}
