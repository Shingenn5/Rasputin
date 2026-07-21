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
import { Button as UIButton } from "@/components/ui/button.jsx";
import { Badge } from "@/components/ui/badge.jsx";
import {
  displayModelName,
  displayWorkspaceName,
  isModelHealthy,
  labelize,
  runtimeStatus,
} from "../../lib/display.js";
import { actionRegistry, useReliableAction } from "../../lib/actionRegistry.js";
import { api, postJson } from "../../api/client.js";
import { ENGINE_PROTOCOLS, ENGINE_LABELS } from "../../lib/engines.js";
import { useSettingsStore } from "../settings/settingsStore.js";

/* ── Tab config ── */
const warsatTabs = [
  { id: "planner",    label: "Planner",    icon: SlidersHorizontal },
  { id: "timeline",   label: "Timeline",   icon: Layers },
  { id: "agents",     label: "Agents",     icon: Database },
  { id: "telemetry",  label: "Telemetry",  icon: Cpu },
  { id: "queue",      label: "Queue",      icon: Activity },
  { id: "deploy",     label: "Deploy",     icon: Play },
  { id: "containers", label: "Containers", icon: Server },
  { id: "safety",     label: "Safety",     icon: Shield },
];

/* ── Helpers ── */
function statusColor(st) {
  if (["running", "reachable", "healthy", "ready", "approved", "done", "success"].includes(st)) return "var(--ras-safe)";
  if (["failed", "error", "denied", "blocked", "unhealthy"].includes(st)) return "var(--ras-danger)";
  if (["paused", "pending", "queued", "warning", "stopped", "unknown"].includes(st)) return "var(--ras-warn)";
  return "var(--cc-muted)";
}

function taskStatusIcon(status) {
  if (["running"].includes(status)) return <Activity size={14} color="var(--ras-safe)" />;
  if (["queued"].includes(status)) return <Gauge size={14} color="var(--ras-warn)" />;
  if (["paused"].includes(status)) return <Pause size={14} color="var(--ras-warn)" />;
  if (["completed", "done", "success"].includes(status)) return <CheckCircle2 size={14} color="var(--ras-safe)" />;
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
  loadModels,
  security,
  cancelTask,
  pauseTask,
  resumeTask,
  enableDockerControl,
  go,
}) {
  const [activeTab, setActiveTab] = useState("planner");
  const defaultEngine = useSettingsStore(state => state.models?.defaultEngine) || "llamacpp";
  const defaultEngineLabel = ENGINE_LABELS[defaultEngine] || labelize(defaultEngine);
  const [uiState, setUiState] = useState({ status: "idle", message: "" });
  const executeAction = useReliableAction("WarsatView");

  /* ── Telemetry & Agents Polling ── */
  const [telemetry, setTelemetry] = useState(null);
  const [agentState, setAgentState] = useState(null);

  useEffect(() => {
    if (plan && activeTab !== "deploy") {
      setActiveTab("deploy");
    }
  }, [plan]);

  useEffect(() => {
    if (activeTab !== "telemetry" && activeTab !== "agents") return;
    let isSubscribed = true;
    async function poll() {
      if (!isSubscribed) return;
      try {
        if (activeTab === "telemetry") {
          const res = await api("/api/warsat/system-metrics");
          if (isSubscribed) setTelemetry(res);
        } else if (activeTab === "agents") {
          const res = await api("/api/warsat/agent-state");
          if (isSubscribed) setAgentState(res);
        }
      } catch (err) {
        console.error("Warsat polling error:", err);
      }
      if (isSubscribed) setTimeout(poll, 2000);
    }
    poll();
    return () => { isSubscribed = false; };
  }, [activeTab]);

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
    if (protocolId) return;
    // Start the recipe on the protocol matching the Default Inference Engine
    // setting so the choice made in Settings carries through to deploys.
    const preferred = ENGINE_PROTOCOLS[defaultEngine];
    const initial = protocols.some(p => p.id === preferred) ? preferred : firstProtocol?.id;
    if (initial) setProtocolId(initial);
  }, [firstProtocol?.id, protocolId, defaultEngine, protocols]);

  useEffect(() => {
    if (plan) {
      if (plan.protocolId && plan.protocolId !== protocolId) setProtocolId(plan.protocolId);
      if (plan.strengthProfile && plan.strengthProfile !== strengthProfile) setStrengthProfile(plan.strengthProfile);
    }
  }, [plan, protocolId, strengthProfile]);

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
  // Deploy can never succeed without docker control + CLI — the backend 503s.
  // Keep the button locked and let the mission-brief banners explain why.
  const deployBlocked = !!plan && !canDeployPlan;
  const deploymentApprovalId = deployment?.approval?.id || deployment?.approvalId;
  const currentApproval = (approvals?.approvals || []).find(a => a.id === deploymentApprovalId) || deployment?.approval;
  const approvalStatus = currentApproval?.status;
  const approvalPending = deployment?.approvalRequired && (!approvalStatus || approvalStatus === "pending");
  const approvalApproved = deployment?.approvalRequired && approvalStatus === "approved";
  const approvalClosed = deployment?.approvalRequired && ["denied", "expired", "executed"].includes(approvalStatus);
  const approvalReady = !deployment?.approvalRequired || approvalApproved;
  const deployDisabled = !plan || deploying || deployBlocked || !approvalReady || approvalClosed;
  const lifecycle = deployment?.lifecycle || plan?.lifecycle || [];
  const deploymentFailed = deployment?.status === "failed";
  const deploymentRegistered = deployment?.status === "registered";
  const deployLabel = deploying
    ? "Deploying..."
    : deployBlocked
      ? "Deploy locked"
    : deployment?.approvalRequired
      ? approvalStatus === "approved" ? "Run approved deploy" : approvalClosed ? "Approval closed" : "Waiting for approval"
      : deploymentFailed ? "Retry deploy"
      : deploymentRegistered ? "Redeploy"
      : plan?.approvalGranted ? "Deploy (already approved)"
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
    <section className={`w2-layout app-view warsat-view tw ${view === "warsat" ? "active" : ""}`} id="warsatView" data-app-view="warsat">
      <div className="fx-rise mx-auto flex w-full min-w-0 max-w-[1500px] flex-col gap-5 p-7">

      {/* ── Commander Dashboard ── */}
      <div className="flex items-start justify-between gap-5">
        <div>
          <h1 className="flex items-center gap-2 text-3xl font-bold tracking-tight">
            <Satellite size={26} className="text-primary" /> WarSat <span className="text-muted-foreground">Command</span>
          </h1>
          <p className="mt-1.5 text-sm text-muted-foreground">Mission control for local AI operations.</p>
        </div>
        <div className="flex flex-wrap justify-end gap-3">
          {[
            { v: defaultEngineLabel, l: "Default Engine", c: "text-primary" },
            { v: runningTasks.length, l: "Running", c: "text-primary" },
            { v: pendingApprovals.length, l: "Approvals", c: "text-amber-400" },
            { v: containers.length, l: "Containers", c: "text-foreground" },
            { v: healthyModels.length, l: "Models OK", c: healthyModels.length > 0 ? "text-primary" : "text-muted-foreground" },
            { v: failedTasks.length, l: "Failures", c: failedTasks.length > 0 ? "text-rose-400" : "text-muted-foreground" },
            { v: privacyLocked ? "Locked" : "Open", l: "Privacy", c: privacyLocked ? "text-primary" : "text-amber-400" },
          ].map((s) => (
            <div key={s.l} className="glow-card rounded-xl border border-border bg-card px-3.5 py-2 text-center">
              <div className={`text-lg font-bold ${s.c}`}>{s.v}</div>
              <div className="text-[0.62rem] uppercase tracking-wide text-muted-foreground">{s.l}</div>
            </div>
          ))}
        </div>
      </div>

      {/* ── Tab Bar ── */}
      <div className="flex items-center gap-2 overflow-x-auto">
        {warsatTabs.map(t => {
          const Icon = t.icon;
          return (
            <UIButton key={t.id} variant={activeTab === t.id ? "default" : "outline"} size="sm" type="button" onClick={() => setActiveTab(t.id)}>
              <Icon size={15} /> {t.label}
              {t.id === "queue" && activeTasks.length > 0 && (
                <span className="ml-1 rounded-full bg-primary px-1.5 text-[0.65rem] text-primary-foreground">{activeTasks.length}</span>
              )}
              {t.id === "safety" && pendingApprovals.length > 0 && (
                <span className="ml-1 rounded-full bg-amber-500 px-1.5 text-[0.65rem] text-white">{pendingApprovals.length}</span>
              )}
            </UIButton>
          );
        })}
        <div className="flex-1" />
        {uiState.status !== "idle" && (
          <Badge variant={uiState.status === "failed" ? "down" : uiState.status === "success" ? "up" : "muted"}>{uiState.message}</Badge>
        )}
        <UIButton variant="outline" size="sm" type="button" onClick={handleRefresh}><RefreshCw size={15} /> Refresh</UIButton>
      </div>

      {/* ── Content ── */}
      <div className="w2-main-grid">
        <div className="w2-column">

          {/* ═══ PLANNER TAB ═══ */}
          {activeTab === "planner" && (
            <PlannerTab
              models={models}
              createTask={(data) => {
                // Implement task creation
                postJson("/api/tasks", data).then(() => refresh?.());
              }}
            />
          )}

          {/* ═══ TIMELINE TAB ═══ */}
          {activeTab === "timeline" && (
            <TimelineTab tasks={allTasks} />
          )}

          {/* ═══ AGENTS TAB ═══ */}
          {activeTab === "agents" && (
            <AgentsTab agentState={agentState} />
          )}

          {/* ═══ TELEMETRY TAB ═══ */}
          {activeTab === "telemetry" && (
            <TelemetryTab telemetry={telemetry} />
          )}

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
              hardware={hardware}
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
              defaultEngineLabel={defaultEngineLabel}
              enableDockerControl={enableDockerControl}
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
              enableDockerControl={enableDockerControl}
              loadModels={loadModels}
              go={go}
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
const PIPELINE_STEPS = [
  { id: "planned",         label: "Plan" },
  { id: "approvalPending", label: "Approve" },
  { id: "pulling",         label: "Pull" },
  { id: "starting",        label: "Start" },
  { id: "registered",      label: "Register" },
];

function DeployTab({
  warsat, hardware, protocols, strengthProfiles, protocolId, setProtocolId,
  strengthProfile, setStrengthProfile, selectedProtocol, selectedProfile,
  createPlan, plan, error, clearPlan, handleFormChange,
  deployPlan, deploying, deployment, deployLabel, deployDisabled, canDeployPlan,
  approvalPending, approvalClosed, approvalStatus, currentApproval,
  approveApproval, denyApproval, lifecycle,
  defaultEngineLabel, enableDockerControl,
}) {
  const formRef = React.useRef(null);
  const briefRef = React.useRef(null);
  const activePhase = deployment?.phase || plan?.phase || "";

  // Bring the Mission Brief into view whenever a plan lands — it renders
  // below the recipe form, and without the scroll a generate click looks
  // like nothing happened.
  React.useEffect(() => {
    if (plan && briefRef.current) {
      briefRef.current.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [plan]);

  // Sync the recipe form to each NEW plan (keyed by planId). Filling only
  // empty fields left the previous model's values behind, so sending a
  // second model from the catalog still showed — and regenerated — the
  // first one.
  const lastPlanIdRef = React.useRef(null);
  React.useEffect(() => {
    if (!plan || !formRef.current) return;
    if (lastPlanIdRef.current === plan.planId) return;
    lastPlanIdRef.current = plan.planId;
    const els = formRef.current.elements;
    if (els.modelRef) els.modelRef.value = plan.modelRef || "";
    if (els.modelPath) els.modelPath.value = plan.modelPath || "";
    if (els.hostPort) els.hostPort.value = plan.hostPort || "";
    if (els.role && plan.role) els.role.value = plan.role;
  }, [plan]);

  /* Derive which pipeline step is active/done */
  const stepStatus = (stepId) => {
    const phaseOrder = PIPELINE_STEPS.map(s => s.id);
    const activeIdx = phaseOrder.indexOf(activePhase);
    const stepIdx = phaseOrder.indexOf(stepId);
    if (!plan && !deployment) return "pending";
    if (stepIdx < activeIdx) return "done";
    if (stepIdx === activeIdx) return "active";
    return "pending";
  };

  return (
    <div className="w2-section" style={{ flex: 1 }}>

      {/* ── Pipeline Stepper ── */}
      {(plan || deployment) && (
        <div className="ws-pipeline-stepper">
          {PIPELINE_STEPS.map((step, i) => {
            const st = stepStatus(step.id);
            return (
              <React.Fragment key={step.id}>
                <div className={`ws-pipeline-step is-${st}`}>
                  <div className="ws-pipeline-dot">
                    {st === "done" ? <CheckCircle2 size={14} /> : <span>{i + 1}</span>}
                  </div>
                  <span>{step.label}</span>
                </div>
                {i < PIPELINE_STEPS.length - 1 && (
                  <div className={`ws-pipeline-connector ${st === "done" ? "is-done" : ""}`} />
                )}
              </React.Fragment>
            );
          })}
        </div>
      )}

      {/* ── Launch Recipe Form ── */}
      <div className="ws-mission-recipe">
        <div className="ws-recipe-header">
          <SlidersHorizontal size={14} />
          <span>Launch Recipe</span>
          {defaultEngineLabel && (
            <span className="ws-protocol-hint">Default engine: {defaultEngineLabel}</span>
          )}
          {protocols.length > 0 && (
            <span className="ws-protocol-hint">{selectedProtocol?.runtime || ""}</span>
          )}
        </div>
        <form ref={formRef} onSubmit={createPlan} onChange={handleFormChange} className="ws-recipe-form">
          <label className="ws-recipe-field">
            <span>Protocol</span>
            <select className="w2-input" name="protocolId" value={protocolId} onChange={e => setProtocolId(e.target.value)} required>
              <option value="" disabled>Choose protocol</option>
              {protocols.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </label>
          <label className="ws-recipe-field">
            <span>{selectedProtocol?.modelFormat === "gguf" ? "Model Name (Optional)" : selectedProtocol?.id === "ollamaOpenaiServer" ? "Ollama Model" : "Model ID (HuggingFace)"}</span>
            <input className="w2-input" name="modelRef" placeholder="e.g. Qwen/Qwen2.5-7B-Instruct" />
          </label>
          {selectedProtocol?.modelFormat === "gguf" && (
            <label className="ws-recipe-field" style={{ gridColumn: "1 / -1" }}>
              <span>Model Path (GGUF)</span>
              <input className="w2-input" name="modelPath" placeholder="models/my-model.gguf" />
            </label>
          )}
          <label className="ws-recipe-field">
            <span>Host Port</span>
            <input className="w2-input" name="hostPort" type="number" min="1024" max="65535" placeholder="Auto" />
          </label>
          <label className="ws-recipe-field">
            <span>Role</span>
            <select className="w2-input" name="role" defaultValue={selectedProtocol?.defaultRole || "helper"}>
              <option value="main">Main</option><option value="planner">Planner</option><option value="coder">Coder</option>
              <option value="researcher">Researcher</option><option value="summarizer">Summarizer</option>
              <option value="embeddings">Embeddings</option><option value="helper">Helper</option>
            </select>
          </label>
          <label className="ws-recipe-field">
            <span>Profile</span>
            <select className="w2-input" name="strengthProfile" value={strengthProfile} onChange={e => setStrengthProfile(e.target.value)}>
              {Object.entries(strengthProfiles).map(([k, p]) => <option key={k} value={k}>{p.label || k}</option>)}
              {!Object.keys(strengthProfiles).length && <option value="balanced">Balanced</option>}
            </select>
          </label>
          <label className="ws-recipe-field" htmlFor="warsatMultiGpu">
            <span>GPU allocation</span>
            <span className="ws-checkbox-row">
              <input
                id="warsatMultiGpu"
                key={(hardware?.detectedHardware?.gpus || []).length}
                name="multiGpu"
                type="checkbox"
                defaultChecked={(hardware?.detectedHardware?.gpus || []).length > 1}
              />
              Use all detected GPUs
            </span>
            <small>
              Auto-shards across {(hardware?.detectedHardware?.gpus || []).length || "the visible"} GPUs and fits to available VRAM.
            </small>
          </label>
          <div className="ws-recipe-actions">
            <button className="w2-button primary" type="submit" style={{ flex: 1 }}>
              <Zap size={14} /> {plan ? "Regenerate Plan" : "Generate Plan"}
            </button>
            {(plan || error) && (
              <button className="w2-button" type="button" onClick={clearPlan}>Clear</button>
            )}
          </div>
        </form>
        {error && (
          <div className="ws-recipe-error">
            <AlertTriangle size={13} /> {error}
          </div>
        )}
      </div>

      {/* ── Mission Brief (Plan Preview) ── */}
      {plan && (
        <div ref={briefRef}>
          <PlanPreview
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
            enableDockerControl={enableDockerControl}
          />
        </div>
      )}
    </div>
  );
}


/* ═══════════════════════════════════════════
   ENABLE DOCKER CONTROL (inline prompt)
   ═══════════════════════════════════════════ */
function EnableDockerButton({ enableDockerControl }) {
  const [busy, setBusy] = useState(false);
  if (!enableDockerControl) return null;

  async function handleClick() {
    const ok = window.confirm(
      "Enable Docker control?\n\nWarSat will be allowed to manage Docker containers on this machine (same as the toggle in Settings > Security)."
    );
    if (!ok) return;
    setBusy(true);
    try {
      await enableDockerControl();
    } finally {
      setBusy(false);
    }
  }

  return (
    <button
      className="w2-button primary"
      type="button"
      disabled={busy}
      onClick={handleClick}
      style={{ fontSize: "0.75rem", padding: "4px 10px", flexShrink: 0, marginLeft: "auto" }}
    >
      {busy ? <RefreshCw size={12} className="ws-spin" /> : <Server size={12} />}
      {busy ? "Enabling..." : "Enable Docker Control"}
    </button>
  );
}


/* ═══════════════════════════════════════════
   PLAN PREVIEW (Mission Brief)
   ═══════════════════════════════════════════ */
function PlanPreview({ plan, deployment, deploying, deployLabel, deployDisabled, canDeployPlan, deployPlan, approvalPending, approvalClosed, approvalStatus, currentApproval, approveApproval, denyApproval, lifecycle, enableDockerControl }) {
  const isLocalhost = plan.securityChecks?.localhostOnly;
  const deployFailed = deployment?.status === "failed";
  const deployDone = deployment?.status === "registered";
  // The docker banners below supersede the backend's plain-text warnings
  // about the same conditions.
  const dockerReady = plan.dockerControlEnabled && plan.dockerCliAvailable;
  const planWarnings = (plan.warnings || []).filter(
    (w) => dockerReady || !w.startsWith("Docker control is")
  );

  return (
    <div className="ws-mission-brief">
      {/* Brief Header */}
      <div className="ws-brief-header">
        <div>
          <div className="ws-brief-label">Mission Brief</div>
          <h3 className="ws-brief-title">{plan.protocolName}</h3>
          <div className="ws-brief-subtitle">
            {plan.runtime} · port {plan.hostPort} · {plan.executionEnabled ? "Execution enabled" : "Plan only"}
          </div>
        </div>
        <span className={`ws-binding-badge ${isLocalhost ? "is-safe" : "is-warn"}`}>
          {isLocalhost ? <ShieldCheck size={11} /> : <AlertTriangle size={11} />}
          {isLocalhost ? "localhost only" : "review binding"}
        </span>
      </div>

      {/* Spec Grid */}
      <div className="ws-brief-specs">
        <div className="ws-brief-spec">
          <span>Model</span>
          <strong>{plan.modelRef || plan.modelPath || "Not set"}</strong>
        </div>
        <div className="ws-brief-spec">
          <span>Container</span>
          <strong>{plan.containerName}</strong>
        </div>
        <div className="ws-brief-spec">
          <span>Endpoint</span>
          <strong>{plan.expectedModelRegistryEntry?.baseUrl || plan.endpoint}</strong>
        </div>
        <div className="ws-brief-spec">
          <span>Profile</span>
          <strong>{plan.resourceProfile?.label || plan.strengthProfile}</strong>
        </div>
      </div>

      {/* Lifecycle progress rail */}
      {lifecycle.length > 0 && (
        <div className="ws-lifecycle-rail">
          {lifecycle.map(phase => {
            const st = phase.status || "pending";
            return (
              <div key={phase.id} className={`ws-lifecycle-step is-${st}`}>
                <div className="ws-lifecycle-dot" />
                <div className="ws-lifecycle-body">
                  <strong>{phase.label || labelize(phase.id)}</strong>
                  {phase.message && <span>{phase.message}</span>}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Docker command preview */}
      {plan.dockerRun && (
        <div className="ws-docker-cmd">
          <div className="ws-docker-cmd-label"><Server size={11} /> docker run command</div>
          <pre>{plan.dockerRun}</pre>
        </div>
      )}

      {/* Docker control gate — offer the fix inline instead of sending the
          user to Settings > Security */}
      {!plan.dockerControlEnabled && (
        <div className="ws-exec-warning">
          <AlertTriangle size={13} />
          <span>Docker control is off, so this plan cannot launch a container yet.</span>
          <EnableDockerButton enableDockerControl={enableDockerControl} />
        </div>
      )}
      {plan.dockerControlEnabled && !plan.dockerCliAvailable && (
        <div className="ws-exec-warning" style={{ flexWrap: "wrap" }}>
          <AlertTriangle size={13} />
          <span>
            Docker control is on, but this Rasputin container was started without Docker CLI
            access, so deploys will fail. Restart the stack with the docker-control overlay:
          </span>
          <pre style={{ width: "100%", margin: 0, padding: "8px 10px", borderRadius: "6px", background: "var(--cc-surface)", fontSize: "0.6875rem", overflowX: "auto" }}>
            docker compose -f docker-compose.yml -f docker-compose.docker-control.yml up --build -d
          </pre>
        </div>
      )}

      {/* Warnings */}
      {planWarnings.length > 0 && (
        <div className="ws-brief-warnings">
          {planWarnings.map((w, i) => (
            <div key={i} className="ws-brief-warning">
              <AlertTriangle size={12} /> {w}
            </div>
          ))}
        </div>
      )}

      {/* Action zone */}
      <div className="ws-brief-actions">
        {approvalPending && currentApproval?.id && (
          <>
            <button className="ws-brief-btn is-approve" type="button" onClick={() => approveApproval?.(currentApproval.id)}>
              <CheckCircle2 size={14} /> Approve
            </button>
            <button className="ws-brief-btn is-deny" type="button" onClick={() => denyApproval?.(currentApproval.id)}>
              Deny
            </button>
          </>
        )}
        <button
          className={`ws-brief-btn ${canDeployPlan ? "is-deploy" : ""} ${deploying ? "is-loading" : ""}`}
          type="button"
          disabled={deployDisabled}
          onClick={deployPlan}
        >
          {deploying ? <RefreshCw size={14} className="ws-spin" /> : <Play size={14} />}
          {deployLabel}
        </button>
      </div>

      {/* Result banner */}
      {deployment && (
        <div className={`ws-deploy-result ${deployFailed ? "is-fail" : deployDone ? "is-done" : "is-info"}`}>
          {deployFailed ? <AlertTriangle size={14} /> : <CheckCircle2 size={14} />}
          <div>
            <strong>{deployFailed ? "Deployment failed" : deployDone ? "Model registered" : "Deploy updated"}</strong>
            {deployment.lastError && <div className="ws-result-detail">{deployment.lastError}</div>}
            {deployment.endpoint && <div className="ws-result-detail">Endpoint: {deployment.endpoint}</div>}
          </div>
        </div>
      )}
    </div>
  );
}


/* ═══════════════════════════════════════════
   CONTAINERS TAB
   ═══════════════════════════════════════════ */
function ContainersTab({ containers, runtimes, logs, handleLoadLogs, handleRuntimeAction, operation, approvals, handleRefresh, enableDockerControl, loadModels, go }) {
  const [activeLogContainer, setActiveLogContainer] = useState(null);
  const [discovering, setDiscovering] = useState(false);
  const [discovered, setDiscovered] = useState(null);
  const [importingKey, setImportingKey] = useState(null);
  const [importedKeys, setImportedKeys] = useState(new Set());
  const operationApproval = (approvals?.approvals || []).find(a => a.id === (operation?.approval?.id || operation?.approvalId)) || operation?.approval;

  // status is raw docker text ("Up 50 seconds"); state is the normalized flag.
  const isUp = (c) => ["running", "healthy", "reachable"].includes(c.state || "") || (c.status || "").toLowerCase().startsWith("up");
  const running = containers.filter(isUp);
  const stopped = containers.filter(c => !isUp(c));

  function toggleLogs(name) {
    if (activeLogContainer === name) {
      setActiveLogContainer(null);
    } else {
      setActiveLogContainer(name);
      handleLoadLogs(name);
    }
  }

  async function runDiscover() {
    setDiscovering(true);
    setDiscovered(null);
    try {
      const res = await api("/api/warsat/discover");
      setDiscovered(res);
    } catch (err) {
      setDiscovered({ error: err.message || "Discovery failed", discovered: [] });
    } finally {
      setDiscovering(false);
    }
  }

  async function importModel(item) {
    const k = `${item.containerName}::${item.modelId}`;
    setImportingKey(k);
    try {
      await postJson("/api/warsat/import-discovered", {
        modelId: item.modelId,
        baseUrl: item.baseUrl,
        containerName: item.containerName,
        protocolHint: item.protocolHint,
      });
      setImportedKeys(prev => new Set([...prev, k]));
      await loadModels?.();
      // Navigate to chat — give the user 400ms to see the success state
      setTimeout(() => go?.("home"), 400);
    } catch (err) {
      alert(`Import failed: ${err.message}`);
    } finally {
      setImportingKey(null);
    }
  }

  return (
    <div className="w2-section" style={{ flex: 1 }}>

      {/* Discover panel */}
      <div className="ws-discover-panel">
        <div className="ws-discover-header">
          <div className="ws-discover-title">
            <Search size={14} />
            <span>Model Discovery</span>
            <span className="ws-discover-hint">Find AI models running in Docker on this machine</span>
          </div>
          <button
            className={`w2-button primary ${discovering ? "is-loading" : ""}`}
            type="button"
            onClick={runDiscover}
            disabled={discovering}
          >
            {discovering ? <RefreshCw size={13} className="ws-spin" /> : <Search size={13} />}
            {discovering ? "Scanning..." : "Scan for Models"}
          </button>
        </div>

        {discovered && (
          <div className="ws-discover-results">
            {discovered.error && (
              <div className="ws-exec-warning"><AlertTriangle size={13} /> {discovered.error}</div>
            )}
            {!discovered.error && (discovered.discovered || []).length === 0 && (
              <div className="ws-discover-empty">
                No unregistered AI model endpoints found. If a model is running,
                make sure Docker control is enabled and its port is exposed.
              </div>
            )}
            {(discovered.discovered || []).map(item => {
              const k = `${item.containerName}::${item.modelId}`;
              const imported = importedKeys.has(k);
              const loading = importingKey === k;
              return (
                <div key={k} className="ws-discover-card">
                  <div className="ws-discover-card-left">
                    <span className="ws-status-pulse is-running" />
                    <div>
                      <div className="ws-discover-model-id">{item.modelId}</div>
                      <div className="ws-discover-meta">
                        <span><Server size={10} /> {item.containerName}</span>
                        <span><MonitorSpeaker size={10} /> {item.baseUrl}</span>
                        <span className="ws-protocol-badge">{item.protocolHint}</span>
                      </div>
                    </div>
                  </div>
                  <button
                    className={`ws-brief-btn ${imported ? "" : "is-deploy"}`}
                    type="button"
                    disabled={imported || loading}
                    onClick={() => importModel(item)}
                    style={{ fontSize: "0.8125rem", padding: "7px 14px" }}
                  >
                    {loading ? <RefreshCw size={12} className="ws-spin" /> : imported ? <CheckCircle2 size={12} /> : <Play size={12} />}
                    {loading ? "Importing..." : imported ? "Added — Starting chat…" : "Add to Chat"}
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Summary banner */}
      <div className="ws-runtime-banner">
        <div className="ws-runtime-banner-stat">
          <span className="ws-status-pulse is-running" />
          <strong style={{ color: "var(--ras-safe)" }}>{running.length}</strong>
          <span>Running</span>
        </div>
        <div className="ws-runtime-banner-stat">
          <span className="ws-status-pulse is-stopped" />
          <strong>{stopped.length}</strong>
          <span>Stopped</span>
        </div>
        <div className="ws-runtime-banner-stat">
          <Server size={13} color="var(--cc-muted)" />
          <strong>{containers.length}</strong>
          <span>Total</span>
        </div>
        <div style={{ flex: 1 }} />
        <button className="w2-button" type="button" onClick={handleRefresh} style={{ fontSize: "0.75rem", padding: "4px 10px" }}>
          <RefreshCw size={12} /> Refresh
        </button>
      </div>

      {/* Execution disabled warning — runtimes reports `enabled`, and when it
          is true the message is informational, not a warning */}
      {runtimes && runtimes.enabled === false && (
        <div className="ws-exec-warning">
          <AlertTriangle size={13} />
          <span>{runtimes?.message || "Docker control is off, so WarSat cannot manage containers."}</span>
          {!runtimes?.dockerControlEnabled && (
            <EnableDockerButton enableDockerControl={enableDockerControl} />
          )}
        </div>
      )}

      {/* Container cards */}
      {containers.map(container => {
        const st = container.status || container.state || "unknown";
        const isRunning = isUp(container);
        const isLogOpen = activeLogContainer === container.name;
        const logsForThis = logs?.containerName === container.name ? logs : null;

        /* Parse port string into clickable links */
        const portMatches = (container.ports || "").match(/(\d+\.\d+\.\d+\.\d+):(\d+)/g) || [];
        const localPort = portMatches.map(p => p.split(":")[1]).find(Boolean);

        return (
          <div key={container.name || container.id} className={`ws-runtime-card ${isRunning ? "is-running" : "is-stopped"}`}>
            {/* Card header */}
            <div className="ws-runtime-card-head">
              <div className="ws-runtime-status-wrap">
                <span className={`ws-status-pulse ${isRunning ? "is-running" : "is-stopped"}`} />
                <div>
                  <div className="ws-runtime-name">{container.name || "Unnamed container"}</div>
                  <div className="ws-runtime-image">{container.image || "Unknown image"}</div>
                </div>
              </div>
              <div className="ws-runtime-badges">
                {container.protocolId && (
                  <span className="ws-protocol-badge">{container.protocolId}</span>
                )}
                <span className={`ws-status-badge is-${st}`}>{labelize(st)}</span>
              </div>
            </div>

            {/* Meta row */}
            <div className="ws-runtime-meta">
              {container.runtime && <span><Cpu size={11} /> {container.runtime}</span>}
              {localPort && (
                <a
                  href={`http://127.0.0.1:${localPort}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="ws-runtime-endpoint"
                >
                  <MonitorSpeaker size={11} /> 127.0.0.1:{localPort}
                </a>
              )}
              {!localPort && container.ports && (
                <span><Package size={11} /> {container.ports}</span>
              )}
            </div>

            {/* Actions */}
            <div className="ws-runtime-actions">
              <button
                className={`ws-runtime-btn ${isLogOpen ? "is-active" : ""}`}
                type="button"
                onClick={() => toggleLogs(container.name)}
              >
                <Eye size={12} /> Logs
              </button>
              <button
                className="ws-runtime-btn"
                type="button"
                onClick={() => handleRuntimeAction("restart", container.name)}
              >
                {isRunning ? <RefreshCw size={12} /> : <Play size={12} />}
                {isRunning ? "Restart" : "Start"}
              </button>
              {isRunning && (
                <button
                  className="ws-runtime-btn is-danger"
                  type="button"
                  onClick={() => handleRuntimeAction("stop", container.name)}
                >
                  <Power size={12} /> Stop
                </button>
              )}
            </div>

            {/* Inline log panel */}
            {isLogOpen && (
              <div className="ws-log-panel">
                <div className="ws-log-header">
                  <span><Eye size={11} /> {container.name} — stdout / stderr</span>
                  <button type="button" className="ws-log-close" onClick={() => setActiveLogContainer(null)}>✕</button>
                </div>
                <pre className="ws-log-body">
                  {logsForThis ? (logsForThis.logs || "No log output.") : "Loading..."}
                </pre>
              </div>
            )}
          </div>
        );
      })}

      {/* Empty state */}
      {!containers.length && (
        <div className="ws-empty-state">
          <Server size={32} color="var(--cc-border)" />
          <strong>No managed containers</strong>
          <span>Deploy a model from the Deploy tab to spin up a container here.</span>
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
                {check.nextStep && <div style={{ color: "var(--ras-warn)", fontSize: "0.6875rem" }}>{check.nextStep}</div>}
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
          <h3 style={{ margin: 0, fontSize: "0.875rem" }}><AlertTriangle size={14} style={{ verticalAlign: "-2px", color: "var(--ras-warn)" }} /> Pending Approvals ({pendingApprovals.length})</h3>
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
   PLANNER TAB
   ═══════════════════════════════════════════ */
function PlannerTab({ models, createTask }) {
  const [objective, setObjective] = useState("");
  const [model, setModel] = useState("dry-run");
  const [skill, setSkill] = useState("general");

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!objective.trim()) return;
    createTask({ objective, model, skill, mode: "agent" });
    setObjective("");
  };

  return (
    <div className="w2-section" style={{ flex: 1 }}>
      <div className="w2-card">
        <h3 style={{ margin: 0, fontSize: "0.875rem" }}>Mission Planner</h3>
        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "12px", marginTop: "12px" }}>
          <label style={{ fontSize: "0.75rem", color: "var(--cc-muted)", display: "flex", flexDirection: "column", gap: "4px" }}>
            Objective
            <textarea className="w2-input" rows={4} value={objective} onChange={e => setObjective(e.target.value)} required placeholder="What should the agent accomplish?" />
          </label>
          <div style={{ display: "flex", gap: "12px" }}>
            <label style={{ fontSize: "0.75rem", color: "var(--cc-muted)", display: "flex", flexDirection: "column", gap: "4px", flex: 1 }}>
              Model
              <select className="w2-input" value={model} onChange={e => setModel(e.target.value)}>
                <option value="dry-run">Dry Run (No inference)</option>
                {models?.filter(m => m.key !== "local-embeddings").map(m => (
                  <option key={m.key} value={m.key}>{m.name}</option>
                ))}
              </select>
            </label>
            <label style={{ fontSize: "0.75rem", color: "var(--cc-muted)", display: "flex", flexDirection: "column", gap: "4px", flex: 1 }}>
              Skill / Role
              <select className="w2-input" value={skill} onChange={e => setSkill(e.target.value)}>
                <option value="general">General AI</option>
                <option value="coder">Software Engineer</option>
                <option value="researcher">Researcher</option>
              </select>
            </label>
          </div>
          <button className="w2-button primary" type="submit" disabled={!objective.trim()} style={{ alignSelf: "flex-start" }}>
            <Play size={14} /> Launch Mission
          </button>
        </form>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════
   TIMELINE TAB
   ═══════════════════════════════════════════ */
function TimelineTab({ tasks }) {
  const latestTasks = (tasks || []).slice(0, 10);
  return (
    <div className="w2-section" style={{ flex: 1 }}>
      <h2 style={{ margin: 0, fontSize: "1rem", marginBottom: "8px" }}>Execution Timeline</h2>
      {!latestTasks.length && <div style={{ padding: "32px", textAlign: "center", color: "var(--cc-muted)", backgroundColor: "var(--cc-surface)", borderRadius: "8px" }}>No activity recorded yet.</div>}
      <div style={{ display: "flex", flexDirection: "column", gap: "0" }}>
        {latestTasks.map((task, i) => (
          <div key={task.id} style={{ display: "flex", gap: "12px", padding: "12px 0", borderBottom: i < latestTasks.length - 1 ? "1px solid var(--cc-border)" : "none" }}>
            <div style={{ paddingTop: "2px" }}>{taskStatusIcon(task.status)}</div>
            <div>
              <div style={{ fontSize: "0.875rem", fontWeight: 500, color: "var(--cc-text)" }}>{task.objective || "Unnamed mission"}</div>
              <div style={{ fontSize: "0.75rem", color: "var(--cc-muted)", marginTop: "4px" }}>
                {labelize(task.status)} · {new Date(task.createdAt * 1000).toLocaleTimeString()} · {task.model}
              </div>
              {task.logs?.length > 0 && (
                <div style={{ fontSize: "0.6875rem", fontFamily: "monospace", color: "var(--cc-muted)", marginTop: "6px", background: "var(--cc-surface)", padding: "6px", borderRadius: "4px" }}>
                  {task.logs[task.logs.length - 1]}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════
   AGENTS TAB
   ═══════════════════════════════════════════ */
function AgentsTab({ agentState }) {
  const agents = agentState?.tasks || [];
  return (
    <div className="w2-section" style={{ flex: 1 }}>
      <h2 style={{ margin: 0, fontSize: "1rem", marginBottom: "8px" }}>Active Agents ({agentState?.active_agents || 0})</h2>
      {!agents.length && <div style={{ padding: "32px", textAlign: "center", color: "var(--cc-muted)", backgroundColor: "var(--cc-surface)", borderRadius: "8px" }}>No agents currently active.</div>}
      {agents.map(agent => (
        <div key={agent.id} className="w2-card" style={{ gap: "8px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
              <Database size={16} color="var(--cc-accent)" />
              <div>
                <strong style={{ fontSize: "0.875rem" }}>{labelize(agent.skill || "general")} Agent</strong>
                <div style={{ fontSize: "0.6875rem", color: "var(--cc-muted)" }}>Workspace: {displayWorkspaceName(agent.workspace)}</div>
              </div>
            </div>
            <span style={{ fontSize: "0.6875rem", padding: "2px 10px", borderRadius: "999px", background: `color-mix(in srgb, ${statusColor(agent.status)} 15%, var(--cc-surface))`, color: statusColor(agent.status), fontWeight: 600 }}>
              {labelize(agent.status)}
            </span>
          </div>
          <div style={{ fontSize: "0.75rem", color: "var(--cc-text)" }}>Mission: {agent.objective}</div>
          <div style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>Model: {agent.model}</div>
        </div>
      ))}
    </div>
  );
}

/* ═══════════════════════════════════════════
   TELEMETRY TAB
   ═══════════════════════════════════════════ */
function TelemetryTab({ telemetry }) {
  if (!telemetry) return <div className="w2-section" style={{ flex: 1, padding: "32px", textAlign: "center", color: "var(--cc-muted)" }}>Connecting to telemetry...</div>;
  const { cpu, ram, disk, gpus } = telemetry;
  // API responses are camelized; accept legacy snake_case too.
  const gb = (o, key, alt) => o?.[key] ?? o?.[alt];
  
  return (
    <div className="w2-section" style={{ flex: 1 }}>
      <h2 style={{ margin: 0, fontSize: "1rem", marginBottom: "8px" }}>System Telemetry</h2>
      
      <div className="w2-card" style={{ gap: "12px" }}>
        <h3 style={{ margin: 0, fontSize: "0.875rem" }}>Host Resources</h3>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem", marginBottom: "4px" }}>
              <span>CPU Utilization</span>
              <strong>{cpu.percent}%</strong>
            </div>
            <div style={{ height: "6px", background: "var(--cc-border)", borderRadius: "3px", overflow: "hidden" }}>
              <div style={{ height: "100%", width: `${cpu.percent}%`, background: "var(--cc-accent)", transition: "width 0.5s ease" }} />
            </div>
          </div>
          
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem", marginBottom: "4px" }}>
              <span>RAM ({gb(ram, "usedGb", "used_gb")} / {gb(ram, "totalGb", "total_gb")} GB)</span>
              <strong>{ram.percent}%</strong>
            </div>
            <div style={{ height: "6px", background: "var(--cc-border)", borderRadius: "3px", overflow: "hidden" }}>
              <div style={{ height: "100%", width: `${ram.percent}%`, background: "var(--ras-warn)", transition: "width 0.5s ease" }} />
            </div>
          </div>
          
          <div style={{ gridColumn: "1 / -1" }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem", marginBottom: "4px" }}>
              <span>Disk ({gb(disk, "usedGb", "used_gb")} / {gb(disk, "totalGb", "total_gb")} GB)</span>
              <strong>{disk.percent}%</strong>
            </div>
            <div style={{ height: "6px", background: "var(--cc-border)", borderRadius: "3px", overflow: "hidden" }}>
              <div style={{ height: "100%", width: `${disk.percent}%`, background: "var(--cc-muted)", transition: "width 0.5s ease" }} />
            </div>
          </div>
        </div>
      </div>
      
      {gpus && gpus.length > 0 && (
        <div className="w2-card" style={{ gap: "12px", marginTop: "16px" }}>
          <h3 style={{ margin: 0, fontSize: "0.875rem" }}>GPU Clusters</h3>
          {gpus.map(gpu => {
            const usedMb = gb(gpu, "memoryUsedMb", "memory_used_mb") || 0;
            const totalMb = gb(gpu, "memoryTotalMb", "memory_total_mb") || 0;
            const vramPct = totalMb ? Math.round((usedMb / totalMb) * 100) : 0;
            return (
            <div key={gpu.index} style={{ border: "1px solid var(--cc-border)", padding: "12px", borderRadius: "6px", display: "flex", flexDirection: "column", gap: "8px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <strong style={{ fontSize: "0.875rem" }}>GPU {gpu.index}: {gpu.name}</strong>
                <span style={{ fontSize: "0.75rem", color: "var(--cc-muted)", background: "var(--cc-surface)", padding: "2px 6px", borderRadius: "4px" }}>{gpu.temperature}°C</span>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", marginTop: "8px" }}>
                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem", marginBottom: "4px" }}>
                    <span>Compute</span>
                    <strong>{gpu.utilization}%</strong>
                  </div>
                  <div style={{ height: "6px", background: "var(--cc-border)", borderRadius: "3px", overflow: "hidden" }}>
                    <div style={{ height: "100%", width: `${gpu.utilization}%`, background: "var(--ras-danger)", transition: "width 0.5s ease" }} />
                  </div>
                </div>

                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem", marginBottom: "4px" }}>
                    <span>VRAM ({Math.round(usedMb / 1024 * 10)/10} / {Math.round(totalMb / 1024 * 10)/10} GB)</span>
                    <strong>{vramPct}%</strong>
                  </div>
                  <div style={{ height: "6px", background: "var(--cc-border)", borderRadius: "3px", overflow: "hidden" }}>
                    <div style={{ height: "100%", width: `${vramPct}%`, background: "var(--ras-safe)", transition: "width 0.5s ease" }} />
                  </div>
                </div>
              </div>
            </div>
            );
          })}
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
            <strong style={{ color: security?.privacyLock ? "var(--ras-safe)" : "var(--ras-warn)" }}>
              {security?.privacyLock ? "LOCKED" : "OPEN"}
            </strong>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span>Remote Models</span>
            <strong style={{ color: !security?.allowRemoteModels ? "var(--ras-safe)" : "var(--ras-warn)" }}>
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
            {gpus.map((gpu, i) => {
              const vramMb = gpu.memoryTotalMb || gpu.memory_total_mb;
              return (
                <div key={i} style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>
                  <strong style={{ color: "var(--cc-text)" }}>{gpu.name}</strong>
                  <div>{vramMb ? `${(vramMb / 1024).toFixed(1)} GB VRAM` : "Unknown VRAM"}</div>
                </div>
              );
            })}
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
