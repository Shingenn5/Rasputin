import { TimelineTab, AgentsTab, TelemetryTab, QuickActionsPanel } from "./OperationsPanels.jsx";
import { PlannerTab } from "./PlannerTab.jsx";
import { SafetyTab, SafetyLockPanel } from "./SafetyTab.jsx";
import { ContainersTab } from "./ContainersTab.jsx";

import { DeployTab } from "./DeployTab.jsx";
import { QueueTab } from "./QueueTab.jsx";

import { useState, useMemo, useEffect } from "react";
import { Activity, Cpu, Database, Layers, Play, RefreshCw, Satellite, Server, Shield, SlidersHorizontal } from "lucide-react";
import { Button as UIButton } from "@/components/ui/button.jsx";
import { Badge } from "@/components/ui/badge.jsx";
import { isModelHealthy, labelize } from "../../lib/display.js";
import { useReliableAction } from "../../lib/actionRegistry.js";
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
  const selectionMode = useSettingsStore(state => state.models?.selectionMode) || "automatic";
  const performancePreference = useSettingsStore(state => state.models?.performancePreference) || "balanced";
  const defaultEngine = useSettingsStore(state => state.models?.defaultEngine) || "llamacpp";
  const defaultEngineLabel = ENGINE_LABELS[defaultEngine] || labelize(defaultEngine);
  const runtimeStrategyLabel = selectionMode === "automatic"
    ? "Automatic · " + labelize(performancePreference)
    : defaultEngineLabel;
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
    if (view === "warsat" && !catalogItems.length && !modelCatalogLoading) {
      // Automatic catalog discovery is intentionally silent and bounded. The
      // App-level loader deduplicates concurrent calls and records an empty
      // successful catalog as a completed attempt.
      loadModelCatalog?.(false, { automatic: true });
    }
  }, [view, catalogItems.length, modelCatalogLoading, loadModelCatalog]);

  useEffect(() => {
    if (protocolId) return;
    // Manual mode honors the engine override. Automatic mode leaves protocol
    // selection to the model recommendation path instead of silently pinning
    // every launch to the advanced engine setting.
    const preferred = selectionMode === "manual" ? ENGINE_PROTOCOLS[defaultEngine] : null;
    const initial = protocols.some(p => p.id === preferred) ? preferred : firstProtocol?.id;
    if (initial) setProtocolId(initial);
  }, [firstProtocol?.id, protocolId, defaultEngine, protocols, selectionMode]);

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
  const resourceAdmission = plan?.resourceAdmission || null;
  const resourceAdmissionStatus = resourceAdmission?.status || "unmeasured";
  const resourceAdmissionBlocked = ["blocked", "queued"].includes(resourceAdmissionStatus);
  const canDeployPlan = !!plan?.executionEnabled
    && !!plan?.dockerControlEnabled
    && !!plan?.dockerCliAvailable
    && !resourceAdmissionBlocked;
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
    : resourceAdmissionStatus === "blocked"
      ? "Resource admission blocked"
    : resourceAdmissionStatus === "queued"
      ? "Waiting for capacity"
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
    <section className={`w2-layout app-view warsat-view tw ${view === "warsat" ? "active" : ""}`} id="warsatView" data-app-view="warsat" data-testid="warsat-view">
      <div className="fx-rise mx-auto flex w-full min-w-0 max-w-[1500px] flex-col gap-5 p-7">

      {/* ── Commander Dashboard ── */}
      <div className="flex min-w-0 flex-wrap items-start justify-between gap-5">
        <div className="min-w-0">
          <h1 className="flex items-center gap-2 text-3xl font-bold tracking-tight">
            <Satellite size={26} className="text-primary" /> WarSat <span className="text-muted-foreground">Command</span>
          </h1>
          <p className="mt-1.5 text-sm text-muted-foreground">Mission control for local AI operations.</p>
        </div>
        <div className="flex min-w-0 max-w-full flex-wrap justify-end gap-3">
          {[
            { v: runtimeStrategyLabel, l: "Runtime Strategy", c: "text-primary" },
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
      <div className="warsat-tabbar flex items-center gap-2">
        <div className="warsat-tabs flex min-w-0 flex-1 items-center gap-2 overflow-x-auto" role="tablist" aria-label="WarSat views" data-testid="warsat-tabs">
        {warsatTabs.map((t, index) => {
          const Icon = t.icon;
          return (
            <UIButton
              key={t.id}
              variant={activeTab === t.id ? "default" : "outline"}
              size="sm"
              type="button"
              role="tab"
              aria-selected={activeTab === t.id}
              tabIndex={activeTab === t.id ? 0 : -1}
              className="warsat-tab"
              onClick={() => setActiveTab(t.id)}
              onKeyDown={(event) => {
                if (!["ArrowRight", "ArrowLeft", "Home", "End"].includes(event.key)) return;
                event.preventDefault();
                const tabList = event.currentTarget.parentElement;
                const nextIndex = event.key === "Home"
                  ? 0
                  : event.key === "End"
                    ? warsatTabs.length - 1
                    : (index + (event.key === "ArrowRight" ? 1 : -1) + warsatTabs.length) % warsatTabs.length;
                setActiveTab(warsatTabs[nextIndex].id);
                requestAnimationFrame(() => tabList?.querySelectorAll('[role="tab"]')[nextIndex]?.focus());
              }}
            >
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
        </div>
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
              runtimeStrategyLabel={runtimeStrategyLabel}
              enableDockerControl={enableDockerControl}
              go={go}
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
