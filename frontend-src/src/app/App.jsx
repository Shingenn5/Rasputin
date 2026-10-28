import { useWarsatActions } from "./useWarsatActions.js";
import { useIntegrationActions } from "./useIntegrationActions.js";
import { useApprovalMemoryActions } from "./useApprovalMemoryActions.js";
import { useSessionActions } from "./useSessionActions.js";
import { useArchiveTrialActions } from "./useArchiveTrialActions.js";
import { useAssistantActions } from "./useAssistantActions.js";
import { useWorkspaceActions } from "./useWorkspaceActions.js";
import { useModelRegistryActions } from "./useModelRegistryActions.js";
import { useTaskActions } from "./useTaskActions.js";
import { useEventConnection } from "./useEventConnection.js";
import { useMcpActions } from "./useMcpActions.js";
import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AppShell } from "../components/AppShell.jsx";
import { useToast } from "../components/Toast.jsx";
import { Onboarding } from "../components/Onboarding.jsx";
import { api, postJson } from "../api/client.js";
import { LoginShell } from "../features/auth/LoginShell.jsx";
import { HomeView } from "../features/chat/HomeView.jsx";
import { DashboardView } from "../features/dashboard/DashboardView.jsx";
import { usesNativeModels } from "../features/models/nativeDeployment.js";
import { ModelsView } from "../features/models/ModelsView.jsx";
import { AssistantView } from "../features/assistant/AssistantView.jsx";
import { SettingsView } from "../features/settings/SettingsView.jsx";
import { ActivityView } from "../features/tasks/TasksView.jsx";
import { TaskDetailsDrawer } from "../features/tasks/TaskDetailsDrawer.jsx";
import { WorkspacesView } from "../features/workspaces/WorkspacesView.jsx";
import { AuditView } from "../features/audit/AuditView.jsx";
import { AgentsView } from "../features/runtime/AgentsView.jsx";
import { SessionsView } from "../features/runtime/SessionsView.jsx";
import { ApprovalsView } from "../features/runtime/ApprovalsView.jsx";
import { MemoryView } from "../features/runtime/MemoryView.jsx";
import { SkillsView } from "../features/runtime/SkillsView.jsx";
import { TelegramView } from "../features/runtime/TelegramView.jsx";
import { SchedulesView } from "../features/runtime/SchedulesView.jsx";
import { ArchiveView } from "../features/archive/ArchiveView.jsx";
import { WarsatView } from "../features/warsat/WarsatView.jsx";
import { TrialsView } from "../features/trials/TrialsView.jsx";
import { readStoredFlag, useLocalStorageFlag } from "../hooks/useLocalStorageFlag.js";
import {
  settingsItems,
  themeOptions,
} from "../lib/constants.js";
import { displayModelName, displayWorkspaceName, isModelHealthy, isModelRouteable, isUserFacingModel } from "../lib/display.js";

import { loadSettings } from "../features/settings/settingsActions.js";

import { canAccessRoute } from "../lib/access.js";
import { applyMotionMode, normalizeMotionMode, readStoredMotionMode } from "../lib/motion.js";

const ApiView = lazy(() => import("../features/workstation/ApiView.jsx").then((module) => ({ default: module.ApiView })));
const TrainingView = lazy(() => import("../features/workstation/TrainingView.jsx").then((module) => ({ default: module.TrainingView })));

const routedViews = new Set([
  "home",
  "chat",
  "workspaces",
  "activity",
  "discover",
  "models",
  "assistant",
  "warsat",
  "archive",
  "trials",
  "settings",
  "agents",
  "sessions",
  "approvals",
  "memory",
  "skills",
  "telegram",
  "schedules",
  "api",
  "training",
]);

const routedSettingsSections = new Set(settingsItems.map(([section]) => section));

function parseAppRouteHash(defaultView = "home") {
  const raw = window.location.hash.replace(/^#\/?/, "").trim();
  if (!raw) return { view: defaultView, section: undefined };
  const [rawView, rawSection] = raw.split("/");
  const aliasedView = rawView === "project" ? "workspaces" : rawView === "history" ? "activity" : rawView;
  const routeView = routedViews.has(aliasedView) ? aliasedView : defaultView;
  const routeSection = routeView === "settings" && routedSettingsSections.has(rawSection) ? rawSection : undefined;
  return { view: routeView, section: routeSection };
}

function routeHashFor(view, section) {
  if (view === "settings") return `#settings/${section || "general"}`;
  if (view === "workspaces") return "#project";
  if (view === "activity") return "#history";
  return `#${view || "home"}`;
}

function assistantProfileToWarsatStrengthProfile(profile) {
  const normalized = String(profile || "balanced").trim().toLowerCase().replace(/[\s-]+/g, "_");
  if (["fast", "fastest", "fastest_practical"].includes(normalized)) return "fast";
  if (["maximum_quality", "maximumquality", "largest", "largest_capable", "maximum"].includes(normalized)) return "maximum_quality";
  return "balanced";
}

const taskLifecycleRank = (status) => {
  if (["done", "error", "cancelled"].includes(status)) return 2;
  if (["running", "paused"].includes(status)) return 1;
  return 0;
};

function reconcileCreatedTaskSnapshot(currentTasks, createdTask, temporaryId) {
  const current = Array.isArray(currentTasks) ? currentTasks : [];
  const existing = current.find((item) => item.id === createdTask.id);
  // Testing Mode can finish before POST /api/tasks resolves. In that race the
  // SSE snapshot is newer than the queued creation response, so never move a
  // task backwards through its lifecycle when replacing the optimistic row.
  const resolved = existing && taskLifecycleRank(existing.status) > taskLifecycleRank(createdTask.status)
    ? existing
    : { ...(existing || {}), ...createdTask };
  return [resolved, ...current.filter((item) => item.id !== createdTask.id && item.id !== temporaryId)];
}

function supportsAgenticMode(model, mode) {
  if (!model) return false;
  if (mode === "chat") return true;
  const certifiedModes = model.compatibility?.supportedModes;
  const certificationAllowsMode = !Array.isArray(certifiedModes) || certifiedModes.includes(mode);
  return certificationAllowsMode && (
    !model.managed
    || model.toolSupport === "agentic"
    || Boolean(model.toolCallParser)
  );
}

export function App() {
  const queryClient = useQueryClient();
  const [ready, setReady] = useState(false);
  // The packaged Desktop Runtime supplies a loopback-only automatic session.
  // Keep the server-mode login fallback, but do not flash it during desktop boot.
  const [loginVisible, setLoginVisible] = useState(false);
  const [loginStatus, setLoginStatus] = useState("");
  const [session, setSession] = useState(null);
  const [view, setView] = useState("home");
  const [settingsSection, setSettingsSection] = useState("general");
  const [sidebarCollapsed, setSidebarCollapsed] = useLocalStorageFlag("rasputin-sidebar-collapsed", false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [theme, setTheme] = useState(readInitialTheme);
  const [motionMode, setMotionMode] = useState(readStoredMotionMode);
  const [models, setModels] = useState([]);
  const [modelProviders, setModelProviders] = useState([]);
  const [modelCatalog, setModelCatalog] = useState({ items: [], categories: [], runtimes: [], source: {} });
  const [modelCatalogLoading, setModelCatalogLoading] = useState(false);
  const [modelCatalogError, setModelCatalogError] = useState("");
  const [selectedModel, setSelectedModel] = useState(null);
  const [testingMode, setTestingMode] = useState(false);
  const [taskMode, setTaskMode] = useState("chat");
  const [memoryMode, setMemoryMode] = useState("auto");
  const [reasoningMode, setReasoningMode] = useState("auto");
  const [modeModelOverrides, setModeModelOverrides] = useState({});
  const [subagentCount, setSubagentCount] = useState(0);
  const [isolateWorkspace, setIsolateWorkspace] = useState(false);
  const [tasks, setTasks] = useState([]);
  const [selectedTaskId, setSelectedTaskId] = useState(null);
  const [taskDetails, setTaskDetails] = useState(null);
  const [taskDetailsLoading, setTaskDetailsLoading] = useState(false);
  const [taskDetailsError, setTaskDetailsError] = useState("");
  const [homeTaskIds, setHomeTaskIds] = useState(new Set());
  const [activeChatSessionId, setActiveChatSessionId] = useState(null);
  const [objective, setObjective] = useState("");
  const [composerStatus, setComposerStatus] = useState("");
  const [workspace, setWorkspace] = useState({ activePath: ".", activeName: "Project Root", workspaces: [] });
  const [workspaceRoots, setWorkspaceRoots] = useState([]);
  const [workspaceBrowse, setWorkspaceBrowse] = useState(null);
  const [workspaceExplorer, setWorkspaceExplorer] = useState({});
  const [mountPlan, setMountPlan] = useState(null);
  const [pendingMounts, setPendingMounts] = useState([]);
  const [security, setSecurity] = useState({});
  const [auditEvents, setAuditEvents] = useState([]);
  const [ragStats, setRagStats] = useState(null);
  const [graphStats, setGraphStats] = useState(null);
  const [output, setOutput] = useState(null);
  const [sessions, setSessions] = useState({ sessions: [] });
  const [chatFolders, setChatFolders] = useState({ folders: [], unfiledCount: 0 });
  const [activeChatFolder, setActiveChatFolder] = useState("all");
  const [selectedSession, setSelectedSession] = useState(null);
  const [approvals, setApprovals] = useState({ approvals: [] });
  const [memoryItems, setMemoryItems] = useState({ items: [] });
  const [memoryExpiredItems, setMemoryExpiredItems] = useState({ items: [] });
  const [memoryReview, setMemoryReview] = useState({ items: [] });
  const [memorySearchResults, setMemorySearchResults] = useState({ items: [] });
  const [skillRegistry, setSkillRegistry] = useState({ skills: [] });
  const [skillPreview, setSkillPreview] = useState(null);
  const [telegramConfig, setTelegramConfig] = useState(null);
  const [schedulesList, setSchedulesList] = useState({ schedules: [] });
  const [warsat, setWarsat] = useState({ protocols: [], count: 0, dockerControlEnabled: false, executionEnabled: false });
  const [warsatPlan, setWarsatPlan] = useState(null);
  const [warsatError, setWarsatError] = useState("");
  const [warsatDeployment, setWarsatDeployment] = useState(null);
  const [warsatDeploying, setWarsatDeploying] = useState(false);
  const [warsatRuntimes, setWarsatRuntimes] = useState({ containers: [], count: 0 });
  const [warsatHardware, setWarsatHardware] = useState(null);
  const [warsatLogs, setWarsatLogs] = useState(null);
  const [warsatOperation, setWarsatOperation] = useState(null);
  const [tools, setTools] = useState({ tools: [], groups: [] });
  const [mcpRelays, setMcpRelays] = useState({ servers: [] });
  const [archiveSessions, setArchiveSessions] = useState({ sessions: [] });
  const [archiveStatus, setArchiveStatus] = useState("");
  const [trialsRuns, setTrialsRuns] = useState({ runs: [] });
  const [trialsStatus, setTrialsStatus] = useState("");
  const [setup, setSetup] = useState(null);
  const [assistantProfile, setAssistantProfile] = useState(null);
  const [assistantCapabilities, setAssistantCapabilities] = useState(null);
  const [assistantPlans, setAssistantPlans] = useState({ plans: [] });
  const [assistantContextCapsules, setAssistantContextCapsules] = useState({ capsules: [] });
  const [selectedTaskContextCapsuleId, setSelectedTaskContextCapsuleId] = useState("");
  const [assistantModelPacks, setAssistantModelPacks] = useState({ packs: [] });
  const [assistantHandoffs, setAssistantHandoffs] = useState({ handoffs: [] });
  const [assistantModelRequests, setAssistantModelRequests] = useState({ requests: [] });
  const [assistantVoicePreview, setAssistantVoicePreview] = useState(null);
  const [assistantCommandPreview, setAssistantCommandPreview] = useState(null);
  const [assistantContextPreview, setAssistantContextPreview] = useState(null);
  const [assistantLoading, setAssistantLoading] = useState(false);
  const [assistantError, setAssistantError] = useState("");
  const [globalStatus, setGlobalStatus] = useState("");
  const [eventConnectionStatus, setEventConnectionStatus] = useState("disconnected");
  const toast = useToast();
  const eventSourceRef = useRef(null);
  const eventReconnectTimerRef = useRef(null);
  const eventFallbackTimerRef = useRef(null);
  const eventRetryAttemptRef = useRef(0);
  const eventGenerationRef = useRef(0);
  const mountedRef = useRef(true);
  const modelCatalogRef = useRef(modelCatalog);
  const modelCatalogRequestRef = useRef(null);
  const modelCatalogAutoAttemptedRef = useRef(false);
  const selectedTaskIdRef = useRef(null);
  const taskDetailsReturnRef = useRef(null);
  const modeModelOverridesRef = useRef(modeModelOverrides);
  const authenticated = !!session?.authenticated && !loginVisible;
  const desktopOnly = Boolean(security?.desktopOnly);
  const nativeModels = usesNativeModels(security);

  // First-run onboarding is about launch readiness, not registry cardinality:
  // seeded entries can still be stopped or unhealthy and cannot start a chat.
  // Desktop uses a new port each launch, so browser storage cannot remember this.
  const [onboarded, setOnboarded] = useState(false);
  const hasHealthyRouteableChatModel = useMemo(
    () => models.some((model) => isUserFacingModel(model, testingMode) && isModelRouteable(model) && isModelHealthy(model)),
    [models, testingMode],
  );
  const showOnboarding = authenticated && ready && !onboarded && !hasHealthyRouteableChatModel;
  useEffect(() => {
    if (authenticated && ready && !onboarded && hasHealthyRouteableChatModel) setOnboarded(true);
  }, [authenticated, ready, onboarded, hasHealthyRouteableChatModel, setOnboarded]);

  const visibleModels = useMemo(() => {
    return models.filter(
      (model) => isUserFacingModel(model, testingMode) && isModelRouteable(model),
    );
  }, [models, testingMode]);

  // No implicit fallback here: a null/unmatched selectedModel means "no
  // model selected" and should render that way, not silently show some
  // other registered-but-possibly-inactive model as if it were chosen.
  const selectedModelObject = useMemo(
    () => models.find((model) => model.key === selectedModel) || null,
    [models, selectedModel],
  );

  const updateTestingMode = useCallback((on) => {
    setTestingMode(!!on);
    if (on) {
      if (models.some((model) => model.key === "dry-run")) setSelectedModel("dry-run");
      return;
    }
    if (selectedModel === "dry-run") {
      const fallback = models.find((model) => model.role === "main" && model.key !== "dry-run")
        || models.find((model) => isUserFacingModel(model, false));
      setSelectedModel(fallback ? fallback.key : null);
    }
  }, [models, selectedModel]);

  // Keep the selection valid: never the dry-run model while testing mode is
  // off, and never a key that doesn't resolve to a registered, visible model.
  // A null selection is left alone -- that's the intentional "no model
  // selected" state, not a stale key to recover from. And recovery only ever
  // lands on a model that's actually running; otherwise it clears to null
  // rather than silently pretending some inactive model is selected.
  useEffect(() => {
    if (!models.length || selectedModel === null) return;
    const current = models.find((model) => model.key === selectedModel);
    const isActive = (model) => (
      isUserFacingModel(model, testingMode) && isModelRouteable(model)
    );
    if (current && isActive(current)) return;
    const fallback = models.find((model) => model.role === "main" && isActive(model)) || models.find(isActive);
    setSelectedModel(fallback ? fallback.key : null);
  }, [testingMode, selectedModel, models]);

  const activeWorkspaceName = workspace.activeName || displayWorkspaceName(workspace.activePath);
  const activeWorkspaceEntry = (workspace.workspaces || []).find(
    (item) => item.id === (workspace.activeId || workspace.active_id)
  );
  const trustedWorkspace = activeWorkspaceEntry?.trusted
    ? { active: true, id: activeWorkspaceEntry.id, name: activeWorkspaceEntry.displayName || activeWorkspaceEntry.name || activeWorkspaceName }
    : null;
  const healthy = isModelHealthy(selectedModelObject);
  const modeBlocked = taskMode !== "chat" && !supportsAgenticMode(selectedModelObject, taskMode);
  const approvedContextCapsules = (assistantContextCapsules?.capsules || []).filter((capsule) => capsule.status === "approved");
  const homeTasks = tasks.filter((task) => !task.parentId && homeTaskIds.has(task.id));
  const runningTasks = tasks.filter((task) => ["queued", "running", "paused"].includes(task.status));
  const queuedMessages = tasks
    .filter((task) => !task.parentId && task.status === "queued" && (!activeChatSessionId || task.sessionId === activeChatSessionId))
    .sort((a, b) => Number(b.priority || 0) - Number(a.priority || 0) || Number(a.queueOrder || a.createdAt || 0) - Number(b.queueOrder || b.createdAt || 0))
    .map((task) => ({ id: task.id, text: task.objective, mode: task.mode, reasoning: task.reasoning }));
  const approvalCount = (approvals?.approvals || []).filter((approval) => approval.status === "pending").length;

  const loadTaskDetails = useCallback(async (taskId, options = {}) => {
    if (!taskId) return null;
    if (!options.silent) setTaskDetailsLoading(true);
    setTaskDetailsError("");
    try {
      const detail = await api(`/api/tasks/${taskId}`);
      setTaskDetails(detail);
      return detail;
    } catch (error) {
      setTaskDetailsError(error.message);
      return null;
    } finally {
      if (!options.silent) setTaskDetailsLoading(false);
    }
  }, []);

  const closeTaskDetails = useCallback(() => {
    setSelectedTaskId(null);
    setTaskDetails(null);
    setTaskDetailsError("");
    setTaskDetailsLoading(false);
  }, []);

  const openTaskDetails = useCallback((taskId) => {
    if (!taskId) return;
    taskDetailsReturnRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setSelectedTaskId(taskId);
    loadTaskDetails(taskId);
  }, [loadTaskDetails]);

  const modelsQuery = useQuery({
    queryKey: ["model-registry"],
    queryFn: fetchModels,
    enabled: authenticated,
  });
  const tasksQuery = useQuery({
    queryKey: ["tasks"],
    queryFn: () => api("/api/tasks"),
    enabled: authenticated,
    // SSE normally keeps task cards live, but reconnects can be delayed by a
    // browser/proxy. Poll only while work is active so a completed task cannot
    // remain visually stuck at its initial queued snapshot.
    refetchInterval: (query) => {
      const active = (query.state.data || []).some((task) => ["queued", "running", "paused"].includes(task?.status));
      return active ? 1000 : false;
    },
  });
  const inboxQuery = useQuery({
    queryKey: ["inbox"],
    queryFn: () => api("/api/inbox"),
    enabled: authenticated,
  });
  const auditQuery = useQuery({
    queryKey: ["audit-events"],
    queryFn: fetchAuditEvents,
    enabled: authenticated,
  });

  useEffect(() => {
    document.body.classList.toggle("sidebar-collapsed", sidebarCollapsed);
    document.body.classList.toggle("mobile-sidebar-open", mobileSidebarOpen);
    document.body.dataset.ready = ready ? "true" : "false";
    localStorage.setItem("rasputin-theme", theme);
    updateThemeChrome(theme);
  }, [theme, sidebarCollapsed, mobileSidebarOpen, ready]);

  useEffect(() => {
    applyMotionMode(motionMode);
  }, [motionMode]);

  // Bridge: route every legacy setGlobalStatus(...) call through the toast
  // system so all existing call sites surface as stacked, non-clobbering
  // toasts without per-site edits. Cleared immediately so the legacy status
  // bar no longer renders (toast is now the channel).
  const toastRef = useRef(toast);
  toastRef.current = toast;
  useEffect(() => {
    if (!globalStatus) return;
    toastRef.current.info(globalStatus);
    setGlobalStatus("");
  }, [globalStatus]);

  useEffect(() => {
    mountedRef.current = true;
    boot();
    return () => {
      mountedRef.current = false;
      disconnectEvents();
    };
  }, []);

  useEffect(() => {
    if (!session) return undefined;
    function applyHashRoute() {
      const route = parseAppRouteHash(desktopOnly ? "chat" : "home");
      if (!canAccessRoute(session.role, route.view, route.section)) {
        applyView("home");
        setGlobalStatus("This account does not include this area.");
        window.history.replaceState(null, "", routeHashFor("home"));
        return;
      }
      go(route.view, route.section, { fromHistory: true });
    }
    applyHashRoute();
    window.addEventListener("hashchange", applyHashRoute);
    window.addEventListener("popstate", applyHashRoute);
    return () => {
      window.removeEventListener("hashchange", applyHashRoute);
      window.removeEventListener("popstate", applyHashRoute);
    };
  }, [desktopOnly, nativeModels, session]);

  useEffect(() => {
    if (modelsQuery.data) setModels(modelsQuery.data);
  }, [modelsQuery.data]);

  useEffect(() => {
    if (tasksQuery.data) setTasks(tasksQuery.data);
  }, [tasksQuery.data]);

  useEffect(() => {
    selectedTaskIdRef.current = selectedTaskId;
  }, [selectedTaskId]);

  useEffect(() => {
    modeModelOverridesRef.current = modeModelOverrides;
  }, [modeModelOverrides]);

  useEffect(() => {
    if (!selectedTaskId) return;
    const liveTask = tasks.find((task) => task.id === selectedTaskId);
    if (!liveTask) return;
    setTaskDetails((current) => current ? {
      ...current,
      task: liveTask,
      children: (current.children || []).map((child) => tasks.find((task) => task.id === child.id) || child),
    } : current);
  }, [tasks, selectedTaskId]);

  useEffect(() => {
    if (auditQuery.data) setAuditEvents(auditQuery.data);
  }, [auditQuery.data]);

  useEffect(() => {
    if (!session?.authenticated || !ready) return;
    const timer = window.setTimeout(() => {
      postJson("/api/preferences", {
        theme,
        sidebarCollapsed,
        onboarded,
        selectedModel,
        testingMode,
        activeWorkspace: workspace.activePath || ".",
        skill: "general",
        taskMode,
        memoryMode,
        reasoning: reasoningMode,
        modeModelOverrides: modeModelOverridesRef.current,
        subagents: subagentCount,
        workspaceExplorer,
        activeView: view,
        activeSettingsSection: settingsSection,
        activeChatFolder,
        motionMode,
      }).catch(() => {});
    }, 450);
    return () => window.clearTimeout(timer);
  }, [theme, sidebarCollapsed, onboarded, selectedModel, testingMode, taskMode, memoryMode, reasoningMode, modeModelOverrides, subagentCount, workspace.activePath, workspaceExplorer, view, settingsSection, activeChatFolder, motionMode, session, ready]);

  async function boot() {
    const markReady = () => {
      document.body.dataset.ready = "true";
      setReady(true);
    };
    try {
      const authSession = await api("/api/auth/session");
      setSession(authSession);
      if (!authSession.authenticated) {
        // This remains reachable for a non-desktop native/server run. The
        // packaged Desktop Runtime receives an automatic session above.
        setLoginVisible(true);
        markReady();
        return;
      }
      await loadBasics(authSession.role);
      setLoginVisible(false);
      connectEvents();
      markReady();
    } catch (error) {
      setLoginStatus(error.message);
      setLoginVisible(true);
      markReady();
    }
  }

  async function loadBasics(activeRole = session?.role) {
    const data = await api("/api/ui/bootstrap");
    const prefs = data.preferences || {};
    // Migrate Desktop's old dismissal flag while keeping Native Host users separate.
    setOnboarded(Boolean(prefs.onboarded || (data.security?.desktopOnly && readStoredFlag("rasputin-onboarded"))));
    setModels(data.models || []);
    setModelProviders(data.modelProviders || []);
    const bootstrapCatalog = data.modelCatalog || { items: [], categories: [], runtimes: [], source: {} };
    modelCatalogRef.current = bootstrapCatalog;
    setModelCatalog(bootstrapCatalog);
    setTasks(data.tasks || []);
    queryClient.setQueryData(["model-registry"], data.models || []);
    queryClient.setQueryData(["tasks"], data.tasks || []);
    queryClient.setQueryData(["audit-events"], data.audit?.events || []);
    setWorkspace(data.workspace || { activePath: ".", activeName: "Project Root", workspaces: [] });
    setSecurity(data.security || {});
    setAuditEvents(data.audit?.events || []);
    setRagStats(data.ragStats || null);
    setGraphStats(data.graphStats || null);
    setOutput(data.output || null);
    setSessions(data.sessions || { sessions: [] });
    setChatFolders(data.chatFolders || { folders: [], unfiledCount: 0 });
    setApprovals(data.approvals || { approvals: [] });
    setMemoryItems(data.memoryItems || { items: [] });
    setMemoryExpiredItems(data.memoryExpiredItems || { items: [] });
    setMemoryReview(data.memoryReview || { items: [] });
    setSkillRegistry(data.skillRegistry || { skills: [] });
    setTelegramConfig(data.telegram || null);
    setSchedulesList(data.schedules || { schedules: [] });
    setWarsat(data.warsat || { protocols: [], count: 0, dockerControlEnabled: false, executionEnabled: false });
    setWarsatRuntimes(data.warsat?.runtimes || { containers: [], count: 0 });
    setTools(data.tools || { tools: [], groups: [] });
    setMcpRelays(data.mcpRelays || { servers: [] });
    setArchiveSessions(data.archive || { sessions: [] });
    setTrialsRuns(data.trials || { runs: [] });
    setSetup(data.setup || null);
    const localTheme = localStorage.getItem("rasputin-theme");
    const localMotionMode = localStorage.getItem("rasputin-motion-mode");
    const localSidebarCollapsed = readStoredFlag("rasputin-sidebar-collapsed");
    const themeWasExplicitlyChosen = localStorage.getItem("rasputin-theme-explicit") === "1";
    const storedTheme = localTheme || prefs.theme;
    setTheme(normalizeTheme(!themeWasExplicitlyChosen && storedTheme === "rasputin-light" ? "rasputin-dark" : storedTheme || "rasputin-dark"));
    setMotionMode(normalizeMotionMode(localMotionMode || prefs.motionMode || "full"));
    setSidebarCollapsed(localSidebarCollapsed === null ? !!prefs.sidebarCollapsed : localSidebarCollapsed);
    setTestingMode(!!prefs.testingMode);
    setSelectedModel(pickBootModel(data.models || [], prefs));
    setTaskMode(prefs.taskMode || "chat");
    setMemoryMode(prefs.memoryMode || "auto");
    setReasoningMode(prefs.reasoning || "auto");
    setModeModelOverrides(prefs.modeModelOverrides || {});
    setSubagentCount(Math.max(0, Math.min(Number(prefs.subagents || 0), 4)));
    setWorkspaceExplorer(prefs.workspaceExplorer || {});
    const desktopDefaultView = data.security?.desktopOnly ? "chat" : "home";
    const route = parseAppRouteHash(desktopDefaultView);
    const hasExplicitRoute = Boolean(window.location.hash.replace(/^#\/?/, "").trim());
    const rememberedView = prefs.activeView || desktopDefaultView;
    const desktopPrimaryViews = new Set(["chat", "workspaces", "activity", "discover", "models", "settings", "api", "training", "schedules"]);
    const requestedView = hasExplicitRoute
      ? route.view
      : data.security?.desktopOnly && !desktopPrimaryViews.has(rememberedView)
        ? desktopDefaultView
        : rememberedView;
    const nativeRequestedView = usesNativeModels(data.security) && requestedView === "warsat" ? "models" : requestedView;
    const requestedSection = hasExplicitRoute && route.view === "settings" ? route.section || "general" : prefs.activeSettingsSection || "general";
    const routeAllowed = canAccessRoute(activeRole, nativeRequestedView, requestedSection);
    setView(routeAllowed ? nativeRequestedView : "home");
    setSettingsSection(routeAllowed ? requestedSection : "accounts");
    if (usesNativeModels(data.security) && requestedView !== nativeRequestedView) {
      setGlobalStatus("Use Models to load GGUF files with the native llama.cpp runtime.");
      window.history.replaceState(null, "", routeHashFor(nativeRequestedView, requestedSection));
    } else if (!routeAllowed) {
      setGlobalStatus("This account does not include this area.");
      window.history.replaceState(null, "", routeHashFor("home"));
    }
    setActiveChatFolder(prefs.activeChatFolder || "all");
    loadWorkspaceRoots(data.workspace?.activePath || ".", prefs.workspaceExplorer || {}).catch((error) => {
      setWorkspaceRoots([]);
      setWorkspaceBrowse(null);
      setGlobalStatus(`Workspace browser will retry when opened: ${error.message}`);
    });
    // Platform settings are administrator-owned. Loading them for a member
    // creates a guaranteed 403 and makes a read-only session look broken.
    if (activeRole === "admin") loadSettings();
    // The bootstrap catalog has no VRAM-based fit labels; swap in the
    // hardware-aware copy in the background. This shares the same guarded
    // loader as the WarSat route so an empty result is still terminal.
    loadModelCatalog(false, { automatic: true }).catch(() => {});
    if (["discover", "models"].includes(nativeRequestedView)) {
      loadWarsatHardware(usesNativeModels(data.security)).catch(() => {});
    }
  }

  async function loadModels() {
    const nextModels = await queryClient.fetchQuery({ queryKey: ["model-registry"], queryFn: fetchModels });
    setModels(nextModels);
    return nextModels;
  }

  const loadModelCatalog = useCallback(async (refresh = false, options = {}) => {
    const automatic = options?.automatic === true;
    const inFlight = modelCatalogRequestRef.current;
    if (inFlight) {
      // A deliberate request joining an automatic request still gets the one
      // status notification promised by the explicit caller. Joining also
      // counts as the automatic attempt, so an empty result cannot retrigger.
      if (automatic) modelCatalogAutoAttemptedRef.current = true;
      if (!automatic) inFlight.notify = true;
      return inFlight.promise;
    }
    if (automatic && modelCatalogAutoAttemptedRef.current) return modelCatalogRef.current;

    if (automatic) modelCatalogAutoAttemptedRef.current = true;
    const request = { notify: !automatic, promise: null };
    const promise = (async () => {
      if (mountedRef.current) {
        setModelCatalogLoading(true);
        setModelCatalogError("");
      }
      try {
        if (refresh) {
          await postJson("/api/model-catalog/refresh", { force: false });
        }
        // fit=true runs the hardware probe so catalog entries carry real
        // VRAM-based fit labels instead of generic estimates.
        const nextCatalog = await api("/api/model-catalog?fit=true");
        modelCatalogRef.current = nextCatalog;
        if (mountedRef.current) {
          setModelCatalog(nextCatalog);
          if (request.notify) {
            setGlobalStatus(refresh
              ? `Model catalog refreshed. ${nextCatalog.count || 0} entries available.`
              : "Model catalog loaded.");
          }
        }
        return nextCatalog;
      } catch (error) {
        if (mountedRef.current) {
          setModelCatalogError(error.message);
          if (request.notify) setGlobalStatus(error.message);
        }
        return null;
      } finally {
        if (mountedRef.current) setModelCatalogLoading(false);
        if (modelCatalogRequestRef.current === request) modelCatalogRequestRef.current = null;
      }
    })();
    request.promise = promise;
    modelCatalogRequestRef.current = request;
    return promise;
  }, []);

  async function loadTasks() {
    const nextTasks = await queryClient.fetchQuery({ queryKey: ["tasks"], queryFn: () => api("/api/tasks") });
    setTasks(nextTasks);
    return nextTasks;
  }

  async function loadTools() {
    const nextTools = await api("/api/tools");
    setTools(nextTools || { tools: [], groups: [] });
    return nextTools;
  }

  const {
    loadMcpRelays,
    registerMcpRelay,
    registerMcpFixture,
    startMcpRelay,
    stopMcpRelay,
    restartMcpRelay,
    removeMcpRelay,
    discoverMcpRelay,
    testMcpRelay,
    classifyMcpTool,
    callMcpTestTool,
  } = useMcpActions({
    setMcpRelays,
    get refreshApprovals() { return refreshApprovals; },
    setGlobalStatus,
    loadTools,
    loadTasks,
    openTaskDetails,
  });

  async function refreshActivity() {
    const [nextTasks] = await Promise.all([
      loadTasks(),
      loadTools(),
      loadMcpRelays(),
      queryClient.fetchQuery({ queryKey: ["inbox"], queryFn: () => api("/api/inbox") }),
    ]);
    return nextTasks;
  }

  async function loadAuditEvents() {
    const nextEvents = await queryClient.fetchQuery({ queryKey: ["audit-events"], queryFn: fetchAuditEvents });
    setAuditEvents(nextEvents);
    return nextEvents;
  }

  async function loadWorkspaceRoots(activePath = workspace.activePath || ".", explorer = workspaceExplorer) {
    const rootsPayload = await api("/api/workspace/roots");
    const roots = rootsPayload.roots || [];
    setWorkspaceRoots(roots);
    const preferred = roots.find((root) => root.id === explorer?.rootId) || roots.find((root) => root.path === activePath) || roots[0];
    if (preferred) {
      const browsePayload = { rootId: preferred.id };
      if (explorer?.rootId === preferred.id && explorer?.path) browsePayload.path = explorer.path;
      const browsed = await postJson("/api/workspace/browse", browsePayload);
      setWorkspaceBrowse(browsed);
      setWorkspaceExplorer({ rootId: preferred.id, path: browsed.path });
    }
  }

  const modelKeyForMode = useCallback((mode, overrides = modeModelOverrides) => {
    const roles = {
      chat: "main",
      analyze: "executor",
      research: "researcher",
      code: "coder",
      write: "summarizer",
      organize: "executor",
      review: "summarizer",
    };
    const overrideKey = overrides?.[mode];
    if (overrideKey && models.some((model) => model.key === overrideKey)) return overrideKey;
    const role = roles[mode] || "main";
    const roleModel = models.find((model) => model.role === role && isUserFacingModel(model, testingMode));
    if (roleModel) return roleModel.key;
    const mainModel = models.find((model) => model.role === "main" && isUserFacingModel(model, testingMode));
    if (mainModel) return mainModel.key;
    return selectedModel;
  }, [models, modeModelOverrides, selectedModel, testingMode]);

  const chooseTaskMode = useCallback((mode) => {
    setTaskMode(mode);
    const currentModel = models.find((model) => model.key === selectedModel) || null;
    if (mode !== "chat" && !supportsAgenticMode(currentModel, mode)) {
      setGlobalStatus("This model is not certified for the selected workflow. Choose a compatible deployment before sending.");
    }
  }, [models, selectedModel]);

  async function openAssistantWorkflow(workflowId) {
    const workflow = workflowId === "coding"
      ? { id: "coding", label: "Coding", mode: "code", role: "coder", title: "Coding workspace" }
      : { id: "assistant", label: "Assistant", mode: "chat", role: "main", title: "Assistant chat" };
    const exactRoleModel = models.find(
      (model) => model.role === workflow.role && isUserFacingModel(model, testingMode) && isModelRouteable(model),
    );
    const routedModel = exactRoleModel?.key || (workflow.mode === "chat" ? modelKeyForMode("chat") : null);
    const routedModelObject = models.find((model) => model.key === routedModel) || null;

    // Keep the requested workflow selected even when its model is unavailable.
    // The composer will show the blocker instead of silently converting a
    // coding request into ordinary chat.
    setTaskMode(workflow.mode);
    setSelectedModel(routedModel || null);
    setObjective("");
    setComposerStatus("");
    setHomeTaskIds(new Set());

    try {
      const detail = await postJson("/api/sessions", {
        title: workflow.title,
        workspace: workspace.activePath || ".",
        model: routedModel || "dry-run",
        mode: workflow.mode,
        skill: "general",
        folder: "",
      });
      const sessionId = detail?.session?.id;
      setSelectedSession(detail);
      setActiveChatSessionId(sessionId || null);
      go("chat");
      setGlobalStatus(routedModelObject
        ? `${workflow.label} workflow ready. Its task mode is independent from the other workflow.`
        : `${workflow.label} workflow selected. Register a healthy ${workflow.role} model before sending.`);
      await loadChatFolders();
      return detail;
    } catch (error) {
      setGlobalStatus(error.message);
      return null;
    }
  }

  const setModeModelOverride = useCallback((mode, modelKey) => {
    setModeModelOverrides((current) => {
      const next = { ...current };
      if (!modelKey) {
        delete next[mode];
      } else {
        next[mode] = modelKey;
      }
      modeModelOverridesRef.current = next;
      return next;
    });
  }, [modelKeyForMode, taskMode]);

  const {
    disconnectEvents,
    connectEvents,
  } = useEventConnection({
    eventReconnectTimerRef,
    eventFallbackTimerRef,
    eventGenerationRef,
    eventSourceRef,
    mountedRef,
    setEventConnectionStatus,
    eventRetryAttemptRef,
    loadTasks,
    queryClient,
    setTasks,
    selectedTaskIdRef,
    setTaskDetails,
    loadTaskDetails,
    setApprovals,
    setMemoryReview,
    setTelegramConfig,
    setGlobalStatus,
  });

  function applyView(nextView, section) {
    setView(nextView);
    if (section) setSettingsSection(section);
    if (nextView === "workspaces") {
      loadWorkspaceRoots().catch((error) => setGlobalStatus(error.message));
      loadPendingMounts().catch((error) => setGlobalStatus(error.message));
    }
    if (["activity", "agents", "sessions", "approvals", "memory", "skills", "telegram", "schedules"].includes(nextView)) {
      loadRuntimeData().catch((error) => setGlobalStatus(error.message));
    }
    if (nextView === "assistant") {
      loadAssistantData().catch((error) => setGlobalStatus(error.message));
    }
    if (nextView === "archive") {
      loadArchive().catch((error) => setGlobalStatus(error.message));
    }
    if (nextView === "trials") {
      loadTrials().catch((error) => setGlobalStatus(error.message));
    }
    if (nextView === "warsat") {
      loadWarsat().catch((error) => setGlobalStatus(error.message));
    }
    if (["discover", "models"].includes(nextView)) {
      loadWarsatHardware().catch((error) => setGlobalStatus(error.message));
    }
    setMobileSidebarOpen(false);
  }

  function go(nextView, section, options = {}) {
    const effectiveView = nativeModels && nextView === "warsat" ? "models" : nextView;
    if (nativeModels && nextView === "warsat") {
      setGlobalStatus("Models uses the native llama.cpp runtime. The old deployment console is retired.");
    }
    if (!canAccessRoute(session?.role, effectiveView, section)) {
      setGlobalStatus("This account does not include this area.");
      return;
    }
    applyView(effectiveView, section);
    const nextHash = routeHashFor(effectiveView, section);
    if (options.fromHistory) {
      if (effectiveView !== nextView) window.history.replaceState(null, "", nextHash);
      return;
    }
    if (window.location.hash !== nextHash) {
      window.history.pushState(null, "", nextHash);
    }
  }

  useEffect(() => {
    if (!session || canAccessRoute(session.role, view, settingsSection)) return;
    setGlobalStatus("This account does not include this area.");
    setView("home");
    window.history.replaceState(null, "", routeHashFor("home"));
  }, [session, settingsSection, view]);

  useEffect(() => {
    if (!nativeModels || view !== "warsat") return;
    setGlobalStatus("Use Models to load GGUF files with the native llama.cpp runtime.");
    setView("models");
    window.history.replaceState(null, "", routeHashFor("models"));
  }, [nativeModels, view]);

  function toggleSidebar() {
    // < sm breakpoint (639px) → overlay mode; sm+ → collapse/expand rail
    if (window.matchMedia("(max-width: 639px)").matches) {
      setMobileSidebarOpen((current) => !current);
      return;
    }
    setSidebarCollapsed((current) => !current);
  }

  async function login(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      setLoginStatus("Signing in...");
      const authSession = await postJson("/api/auth/login", {
        username: form.get("username") || "admin",
        password: form.get("password"),
      });
      setSession(authSession);
      setLoginVisible(false);
      setLoginStatus("");
      await loadBasics(authSession.role);
      connectEvents();
    } catch (error) {
      setLoginStatus(error.message);
    }
  }

  async function logout() {
    if (desktopOnly) return;
    disconnectEvents();
    await api("/api/auth/logout", { method: "POST" });
    setSession(null);
    setLoginVisible(true);
  }

  const {
    startNewChat,
    sendTask,
    queueMessage,
    removeQueuedMessage,
    clearQueuedMessages,
    cancelTask,
    pauseTask,
    resumeTask,
    retryTask,
    setTaskPriority,
    updateInboxEvent,
    markAllInboxRead,
  } = useTaskActions({
    sessions,
    activeChatSessionId,
    selectedSession,
    setObjective,
    go,
    setGlobalStatus,
    workspace,
    selectedModel,
    taskMode,
    activeChatFolder,
    setHomeTaskIds,
    setSelectedSession,
    setActiveChatSessionId,
    get loadChatFolders() { return loadChatFolders; },
    objective,
    memoryMode,
    reasoningMode,
    selectedTaskContextCapsuleId,
    models,
    setComposerStatus,
    isolateWorkspace,
    setTasks,
    subagentCount,
    queryClient,
    setSessions,
    queuedMessages,
    loadTasks,
    selectedTaskIdRef,
    loadTaskDetails,
    supportsAgenticMode,
    reconcileCreatedTaskSnapshot,
  });

  const {
    runModelAction,
    registerLocalModel,
    registerApiModel,
    scanGguf,
  } = useModelRegistryActions({
    setGlobalStatus,
    loadModels,
    setSelectedModel,
  });

  const {
    browseWorkspace,
    previewWorkspaceFile,
    refreshKnowledgeStats,
    indexWorkspaceKnowledge,
    exportWorkspaceGraphToObsidian,
    searchWorkspaceKnowledge,
    approvePath,
    selectWorkspace,
    setWorkspaceTrust,
    setWorkspaceHostShell,
    saveWorkspaceCommands,
    previewMount,
    requestMount,
    loadPendingMounts,
    removePendingMount,
    approvePendingMount,
    saveSafety,
  } = useWorkspaceActions({
    setWorkspaceBrowse,
    setWorkspaceExplorer,
    workspace,
    setRagStats,
    setGraphStats,
    setWorkspace,
    loadWorkspaceRoots,
    workspaceBrowse,
    workspaceExplorer,
    setGlobalStatus,
    setMountPlan,
    setPendingMounts,
    setSecurity,
  });

  async function saveOutputConfig(payload) {
    try {
      const saved = await postJson("/api/output", payload);
      setOutput(saved);
      setGlobalStatus("Output settings saved.");
      return saved;
    } catch (error) {
      setGlobalStatus(error.message);
      throw error;
    }
  }

  async function loadRuntimeData() {
    const [nextSessions, nextChatFolders, nextApprovals, nextMemoryItems, nextMemoryExpiredItems, nextMemoryReview, nextSkills, nextTelegram, nextSchedules] = await Promise.all([
      api("/api/sessions"),
      api("/api/chat-folders"),
      api("/api/approvals"),
      api("/api/memory/items?status=saved&limit=200"),
      api("/api/memory/items?status=expired&limit=200"),
      api("/api/memory/review"),
      api("/api/skills"),
      api("/api/integrations/telegram"),
      api("/api/schedules"),
    ]);
    setSessions(nextSessions);
    setChatFolders(nextChatFolders);
    setApprovals(nextApprovals);
    setMemoryItems(nextMemoryItems);
    setMemoryExpiredItems(nextMemoryExpiredItems);
    setMemoryReview(nextMemoryReview);
    setSkillRegistry(nextSkills);
    setTelegramConfig(nextTelegram);
    setSchedulesList(nextSchedules);
  }

  const {
    loadAssistantData,
    requestAssistantModel,
    prepareAssistantModelRequest,
    createAssistantPlan,
    saveAssistantModelPack,
    saveAssistantProfile,
    reviewAssistantPlan,
    requestAssistantHandoff,
    prepareAssistantHandoff,
    dispatchAssistantHandoff,
    previewAssistantVoice,
    previewAssistantCommand,
    previewAssistantContext,
    createAssistantContextCapsule,
    reviewAssistantContextCapsule,
  } = useAssistantActions({
    setAssistantLoading,
    setAssistantError,
    setAssistantProfile,
    setAssistantCapabilities,
    setAssistantPlans,
    setAssistantContextCapsules,
    setSelectedTaskContextCapsuleId,
    setAssistantModelPacks,
    setAssistantHandoffs,
    setAssistantModelRequests,
    setGlobalStatus,
    get prepareCatalogModelForWarsat() { return prepareCatalogModelForWarsat; },
    get refreshApprovals() { return refreshApprovals; },
    setAssistantVoicePreview,
    workspace,
    setAssistantCommandPreview,
    setAssistantContextPreview,
    assistantProfileToWarsatStrengthProfile,
  });

  const {
    loadArchive,
    saveArchiveDraft,
    exportArchiveDraft,
    searchArchiveCitations,
    loadTrials,
    refreshSetupStatus,
    runTrialCompare,
    revealTrial,
    saveTrialRoute,
  } = useArchiveTrialActions({
    setArchiveSessions,
    setArchiveStatus,
    workspace,
    setTrialsRuns,
    setSetup,
    setTrialsStatus,
    modeModelOverridesRef,
    setModeModelOverrides,
    taskMode,
    setSelectedModel,
  });

  const {
    loadChatFolders,
    deleteSession,
    cleanupEmptySessions,
    createChatFolder,
    assignSessionFolder,
    loadSession,
    resumeSession,
  } = useSessionActions({
    setSessions,
    setChatFolders,
    selectedSession,
    setSelectedSession,
    activeChatSessionId,
    setActiveChatSessionId,
    setHomeTaskIds,
    setObjective,
    setGlobalStatus,
    setTasks,
    go,
  });

  const {
    refreshApprovals,
    approveApproval,
    denyApproval,
    searchMemory,
    addMemory,
    updateMemory,
    deleteMemory,
    approveMemory,
    rejectMemory,
  } = useApprovalMemoryActions({
    setApprovals,
    selectedTaskIdRef,
    loadTaskDetails,
    setGlobalStatus,
    get deployWarsatPlan() { return deployWarsatPlan; },
    setMemorySearchResults,
    setMemoryItems,
    setMemoryExpiredItems,
    setMemoryReview,
  });

  const {
    createSkillFromSession,
    enableSkill,
    disableSkill,
    configureTelegram,
    testTelegram,
    createSchedule,
  } = useIntegrationActions({
    setSkillPreview,
    setGlobalStatus,
    setSkillRegistry,
    setTelegramConfig,
    telegramConfig,
    setSchedulesList,
  });

  const {
    loadWarsatHardware,
    loadWarsat,
    prepareCatalogModelForWarsat,
    loadWarsatLogs,
    requestWarsatOperation,
    createWarsatPlan,
    deployWarsatPlan,
  } = useWarsatActions({
    security,
    setWarsatHardware,
    nativeModels,
    setWarsat,
    setWarsatRuntimes,
    loadModels,
    setSelectedModel,
    setGlobalStatus,
    setWarsatError,
    warsatHardware,
    setWarsatPlan,
    setWarsatDeployment,
    go,
    setWarsatLogs,
    warsatOperation,
    setWarsatOperation,
    refreshApprovals,
    warsatPlan,
    setWarsatDeploying,
    warsatDeployment,
    loadAssistantData,
  });

  if (loginVisible) {
    return <LoginShell onSubmit={login} status={loginStatus} />;
  }

  return (
    <AppShell
      models={models}
      globalStatus={globalStatus}
      clearGlobalStatus={() => setGlobalStatus("")}
      trustedWorkspace={trustedWorkspace}
      onRevokeTrust={() => trustedWorkspace && setWorkspaceTrust(trustedWorkspace.id, false)}
      commandPaletteProps={{
        commands: [
          { label: "Start a new chat", hint: "Create a clean Rasputin conversation.", keywords: "new message", action: startNewChat },
          { label: "Open chat", hint: "Continue the active conversation.", action: () => go("chat") },
          { label: "Open project", hint: "Choose a folder and work from it.", keywords: "folder workspace", action: () => go("workspaces") },
          { label: "Open history", hint: "Review conversations, runs, failures, and notifications.", keywords: "activity notifications queue", action: () => go("activity") },
          { label: "Open models", hint: "Browse, download, and load local models.", action: () => go("models") },
          { label: "Open Model Hub", hint: "Find and download model variants.", action: () => go("discover") },
          { label: "Open API", hint: "Create API keys and connect local models to other tools.", action: () => go("api") },
          { label: "Open Training", hint: "Prepare datasets and fine-tune a local model.", action: () => go("training") },
          { label: "Open Scheduled", hint: "Review saved schedule definitions.", action: () => go("schedules") },
          { label: "Open Rasputin assistant", hint: "Review identity, model packs, plans, and broker handoffs.", keywords: "jarvis friday voice orchestration", action: () => go("assistant") },
          { label: "Open artifacts", hint: "Browse generated files and evidence.", keywords: "archive output", action: () => go("archive") },
          ...[
            ["memory", "Memory", "Recall and manage saved context"],
            ["skills", "Skills", "Manage local skills"],
            ["agents", "Agents", "Inspect agent runtime"],
            ["approvals", "Approvals", "Review pending tool actions"],
            ["telegram", "Telegram", "Manage Telegram integration"],
            ["trials", "Trials", "Evaluate local models"],
          ].filter(([route]) => canAccessRoute(session?.role, route)).map(([route, label, hint]) => ({ label: `Open ${label}`, hint, action: () => go(route) })),
          { label: "Open settings", hint: "Configure the application, models, hardware, and integrations.", action: () => go("settings", "general") },
        ],
        onOpenTask: openTaskDetails,
        onOpenSession: resumeSession,
      }}
      sidebarProps={{
        collapsed: sidebarCollapsed,
        toggleSidebar,
        view,
        settingsSection,
        go,
        taskCount: tasks.length,
        runningCount: runningTasks.length,
        workspaceName: activeWorkspaceName,
        workspaceRoots,
        activeWorkspacePath: workspace.activePath,
        activeWorkspaceId: workspace.activeId || workspace.active_id,
        onSelectProject: async (project) => {
          await selectWorkspace(project.id || project.path || project.root);
          go("chat");
        },
        graphifyProject: async (project) => {
          const projectPath = project.path || project.root;
          const projectName = project.displayName || project.display_name || project.name || displayWorkspaceName(projectPath);
          setGlobalStatus(`Indexing and Graphifying ${projectName}...`);
          try {
            const result = await indexWorkspaceKnowledge(projectPath);
            const docs = result?.rag?.documents ?? result?.documents ?? 0;
            const nodes = result?.graph?.nodes ?? result?.nodes ?? 0;
            setGlobalStatus(`${projectName} is ready - ${docs} indexed files - ${nodes} graph nodes.`);
          } catch (error) {
            setGlobalStatus(`Could not Graphify ${projectName}: ${error?.message || "unknown error"}`);
          }
        },
        modelName: displayModelName(selectedModelObject, models),
        locked: security.privacyLock,
        runtimeMode: security.desktopOnly || security.native ? "native" : "docker",
        desktopOnly,
        motionMode,
        mobileOpen: mobileSidebarOpen,
        newTask: startNewChat,
        recentSessions: sessions?.sessions || [],
        emptySessionCount: sessions?.emptyTotal || 0,
        deleteSession,
        cleanupEmptySessions,
        chatFolders,
        activeChatFolder,
        setActiveChatFolder,
        activeSessionId: activeChatSessionId,
        resumeSession,
        createChatFolder,
        assignSessionFolder,
        session,
        logout: desktopOnly ? undefined : logout,
      }}
    >
      <DashboardView
        view={view}
        models={models}
        homeTasks={homeTasks}
        runningTasks={runningTasks}
        approvalCount={approvalCount}
        go={go}
        openTaskDetails={openTaskDetails}
        security={security}
        session={session}
        role={session?.role}
        selectedModelObject={selectedModelObject}
        objective={objective}
        setObjective={setObjective}
        sendTask={sendTask}
        healthy={healthy}
      />
      <HomeView
        activeWorkspaceName={activeWorkspaceName}
        view={desktopOnly && view === "settings" ? "chat" : view}
        selectedModel={selectedModel}
        selectedModelObject={selectedModelObject}
        models={models}
        visibleModels={visibleModels}
        setSelectedModel={setSelectedModel}
        security={security}
        logout={logout}
        go={go}
        sidebarCollapsed={sidebarCollapsed}
        toggleSidebar={toggleSidebar}
        homeTasks={homeTasks}
        objective={objective}
        setObjective={setObjective}
        sendTask={sendTask}
        cancelTask={cancelTask}
        pauseTask={pauseTask}
        resumeTask={resumeTask}
        healthy={healthy}
        composerStatus={composerStatus}
        approvalCount={approvalCount}
        taskMode={taskMode}
        setTaskMode={chooseTaskMode}
        memoryMode={memoryMode}
        setMemoryMode={setMemoryMode}
        reasoningMode={reasoningMode}
        setReasoningMode={setReasoningMode}
        queuedMessages={queuedMessages}
        queueMessage={queueMessage}
        removeQueuedMessage={removeQueuedMessage}
        clearQueuedMessages={clearQueuedMessages}
        startNewChat={startNewChat}
        modeModelOverrides={modeModelOverrides}
        setModeModelOverride={setModeModelOverride}
        role={session?.role}
        modelKeyForMode={modelKeyForMode}
        subagentCount={subagentCount}
        setSubagentCount={setSubagentCount}
        isolateWorkspace={isolateWorkspace}
        setIsolateWorkspace={setIsolateWorkspace}
        runningTasks={runningTasks}
        openTaskDetails={openTaskDetails}
        contextCapsules={approvedContextCapsules}
        selectedContextCapsuleId={selectedTaskContextCapsuleId}
        setSelectedContextCapsuleId={setSelectedTaskContextCapsuleId}
        hasHealthyRouteableChatModel={hasHealthyRouteableChatModel}
        onOpenModels={() => go("models")}
        onConnectLocalEndpoint={() => go("models")}
        onEnableTestingMode={() => {
          updateTestingMode(true);
          setOnboarded(true);
          go("home");
        }}
        eventConnectionStatus={eventConnectionStatus}
        modeBlocked={modeBlocked}
        setPrompt={(prompt, mode) => {
          setObjective(prompt);
          chooseTaskMode(mode === "analyze files" ? "analyze" : mode || "chat");
          go("home");
          setGlobalStatus(`${mode} prompt loaded.`);
        }}
      />
      <WorkspacesView
        view={view}
        workspace={workspace}
        workspaceRoots={workspaceRoots}
        workspaceBrowse={workspaceBrowse}
        browseWorkspace={browseWorkspace}
        previewWorkspaceFile={previewWorkspaceFile}
        approvePath={approvePath}
        selectWorkspace={selectWorkspace}
        setWorkspaceTrust={setWorkspaceTrust}
        setWorkspaceHostShell={setWorkspaceHostShell}
        saveWorkspaceCommands={saveWorkspaceCommands}
        models={models}
        modeModelOverrides={modeModelOverrides}
        setModeModelOverride={setModeModelOverride}
        role={session?.role}
        loadWorkspaceRoots={() => loadWorkspaceRoots(workspace.activePath)}
        previewMount={previewMount}
        requestMount={requestMount}
        mountPlan={mountPlan}
        pendingMounts={pendingMounts}
        removePendingMount={removePendingMount}
        approvePendingMount={approvePendingMount}
        security={security}
        ragStats={ragStats}
        graphStats={graphStats}
        indexWorkspaceKnowledge={indexWorkspaceKnowledge}
        exportWorkspaceGraphToObsidian={exportWorkspaceGraphToObsidian}
        searchWorkspaceKnowledge={searchWorkspaceKnowledge}
        refreshKnowledgeStats={refreshKnowledgeStats}
        go={go}
        setPrompt={(prompt, mode) => {
          setObjective(prompt);
          chooseTaskMode(mode === "analyze files" ? "analyze" : mode || "analyze");
          go("home");
          setGlobalStatus("Workspace analysis prompt loaded.");
        }}
      />
      <AgentsView view={view} tasks={tasks} models={models} />
      <SessionsView
        view={view}
        sessions={sessions}
        chatFolders={chatFolders}
        activeChatFolder={activeChatFolder}
        setActiveChatFolder={setActiveChatFolder}
        selectedSession={selectedSession}
        loadSession={loadSession}
        resumeSession={resumeSession}
        createChatFolder={createChatFolder}
        assignSessionFolder={assignSessionFolder}
        deleteSession={deleteSession}
        cleanupEmptySessions={cleanupEmptySessions}
        canDeleteSessions={session?.role !== "viewer"}
        createSkillFromSession={createSkillFromSession}
      />
      <ApprovalsView
        view={view}
        approvals={approvals}
        approveApproval={approveApproval}
        denyApproval={denyApproval}
        refreshApprovals={refreshApprovals}
        openTaskDetails={openTaskDetails}
      />
      <MemoryView
        view={view}
        workspace={workspace}
        memoryItems={memoryItems}
        memoryExpiredItems={memoryExpiredItems}
        memoryReview={memoryReview}
        memorySearchResults={memorySearchResults}
        addMemory={addMemory}
        updateMemory={updateMemory}
        deleteMemory={deleteMemory}
        searchMemory={searchMemory}
        approveMemory={approveMemory}
        rejectMemory={rejectMemory}
      />
      <SkillsView
        view={view}
        skills={skillRegistry}
        skillPreview={skillPreview}
        sessions={sessions}
        createSkillFromSession={createSkillFromSession}
        enableSkill={enableSkill}
        disableSkill={disableSkill}
      />
      <TelegramView
        view={view}
        telegram={telegramConfig}
        configureTelegram={configureTelegram}
        testTelegram={testTelegram}
      />
      <SchedulesView
        view={view}
        schedules={schedulesList}
        createSchedule={createSchedule}
      />
      {["api", "training"].includes(view) && <Suspense fallback={<div role="status" className="p-6">Loading workstation…</div>}>
        {view === "api" && <ApiView view={view} models={models} />}
        {view === "training" && <TrainingView view={view} models={models} />}
      </Suspense>}
      {!nativeModels && (
      <WarsatView
        view={view}
        warsat={warsat}
        hardware={warsatHardware}
        runtimes={warsatRuntimes}
        plan={warsatPlan}
        error={warsatError}
        createPlan={createWarsatPlan}
        deployPlan={deployWarsatPlan}
        deploying={warsatDeploying}
        deployment={warsatDeployment}
        operation={warsatOperation}
        logs={warsatLogs}
        loadLogs={loadWarsatLogs}
        runtimeAction={requestWarsatOperation}
        approvals={approvals}
        approveApproval={approveApproval}
        denyApproval={denyApproval}
        clearPlan={() => {
          setWarsatPlan(null);
          setWarsatError("");
          setWarsatDeployment(null);
          setGlobalStatus("");
        }}
        refresh={loadWarsat}
        loadModels={loadModels}
        tasks={tasks}
        models={models}
        security={security}
        cancelTask={cancelTask}
        pauseTask={pauseTask}
        resumeTask={resumeTask}
        modelCatalog={modelCatalog}
        modelCatalogLoading={modelCatalogLoading}
        modelCatalogError={modelCatalogError}
        loadModelCatalog={loadModelCatalog}
        prepareCatalogModelForWarsat={prepareCatalogModelForWarsat}
        go={go}
      />
      )}
      <ArchiveView
        view={view}
        openTaskDetails={openTaskDetails}
        archive={archiveSessions}
        status={archiveStatus}
        saveArchiveDraft={saveArchiveDraft}
        exportArchiveDraft={exportArchiveDraft}
        searchArchiveCitations={searchArchiveCitations}
      />
      <TrialsView
        view={view}
        trials={trialsRuns}
        models={visibleModels}
        status={trialsStatus}
        runTrialCompare={runTrialCompare}
        revealTrial={revealTrial}
        saveTrialRoute={saveTrialRoute}
        modeModelOverrides={modeModelOverrides}
      />
      {/* Onboarding owns focus until dismissed. */}
      {!showOnboarding && <ModelsView
        view={view}
        models={models}
        selectedModelObject={selectedModelObject}
        selectedModel={selectedModel}
        setSelectedModel={setSelectedModel}
        testingMode={testingMode}
        updateTestingMode={updateTestingMode}
        runModelAction={runModelAction}
        loadModels={loadModels}
        scanGguf={scanGguf}
        registerLocalModel={registerLocalModel}
        registerApiModel={registerApiModel}
        modelProviders={modelProviders}
        modelCatalog={modelCatalog}
        modelCatalogLoading={modelCatalogLoading}
        modelCatalogError={modelCatalogError}
        loadModelCatalog={loadModelCatalog}
        prepareCatalogModelForWarsat={prepareCatalogModelForWarsat}
        warsat={warsat}
        warsatHardware={warsatHardware}
        warsatRuntimes={warsatRuntimes}
        warsatPlan={warsatPlan}
        security={security}
        openWarsat={() => (nativeModels ? go("models") : go("warsat"))}
        go={go}
      />}
      <AssistantView
        view={view}
        profile={assistantProfile}
        capabilities={assistantCapabilities}
        sessions={sessions}
        plans={assistantPlans}
        contextCapsules={assistantContextCapsules}
        modelPacks={assistantModelPacks}
        handoffs={assistantHandoffs}
        tools={tools}
        mcpRelays={mcpRelays}
        voicePreview={assistantVoicePreview}
        commandPreview={assistantCommandPreview}
        contextPreview={assistantContextPreview}
        loading={assistantLoading}
        error={assistantError}
        refresh={loadAssistantData}
        createPlan={createAssistantPlan}
        saveModelPack={saveAssistantModelPack}
        reviewPlan={reviewAssistantPlan}
        requestHandoff={requestAssistantHandoff}
        prepareHandoff={prepareAssistantHandoff}
        dispatchHandoff={dispatchAssistantHandoff}
        modelRequests={assistantModelRequests}
        requestModel={requestAssistantModel}
        prepareModelRequest={prepareAssistantModelRequest}
        openModels={() => go("models")}
        previewVoice={previewAssistantVoice}
        previewCommand={previewAssistantCommand}
        previewContext={previewAssistantContext}
        saveProfile={saveAssistantProfile}
        createContextCapsule={createAssistantContextCapsule}
        reviewContextCapsule={reviewAssistantContextCapsule}
        openWorkflow={openAssistantWorkflow}
      />
      <ActivityView
        view={view}
        tasks={tasks}
        models={models}
        refresh={refreshActivity}
        approvals={approvals}
        sessions={sessions}
        auditEvents={auditEvents}
        tools={tools}
        go={go}
        cancelTask={cancelTask}
        pauseTask={pauseTask}
        resumeTask={resumeTask}
        retryTask={retryTask}
        setTaskPriority={setTaskPriority}
        openTaskDetails={openTaskDetails}
        inbox={inboxQuery.data || []}
        markInboxRead={(id) => updateInboxEvent(id, "read")}
        archiveInbox={(id) => updateInboxEvent(id, "archive")}
        markAllInboxRead={markAllInboxRead}
      />
      <SettingsView
        view={view}
        session={session}
        section={settingsSection}
        setSection={(section) => go("settings", section)}
        models={models}
        modeModelOverrides={modeModelOverrides}
        setModeModelOverride={setModeModelOverride}
        selectedModelObject={selectedModelObject}
        selectedModel={selectedModel}
        testingMode={testingMode}
        updateTestingMode={updateTestingMode}
        runModelAction={runModelAction}
        scanGguf={scanGguf}
        workspace={workspace}
        workspaceRoots={workspaceRoots}
        workspaceBrowse={workspaceBrowse}
        browseWorkspace={browseWorkspace}
        approvePath={approvePath}
        loadWorkspaceRoots={() => loadWorkspaceRoots(workspace.activePath)}
        previewMount={previewMount}
        mountPlan={mountPlan}
        security={security}
        saveSafety={saveSafety}
        ragStats={ragStats}
        graphStats={graphStats}
        indexWorkspaceKnowledge={indexWorkspaceKnowledge}
        searchWorkspaceKnowledge={searchWorkspaceKnowledge}
        refreshKnowledgeStats={refreshKnowledgeStats}
        output={output}
        saveOutputConfig={saveOutputConfig}
        themeOptions={themeOptions}
        theme={theme}
        setTheme={(nextTheme) => {
          localStorage.setItem("rasputin-theme-explicit", "1");
          setTheme(normalizeTheme(nextTheme));
        }}
        motionMode={motionMode}
        setMotionMode={setMotionMode}
        logout={logout}
        loadModels={loadModels}
        tools={tools}
        mcpRelays={mcpRelays}
        registerMcpRelay={registerMcpRelay}
        registerMcpFixture={registerMcpFixture}
        startMcpRelay={startMcpRelay}
        stopMcpRelay={stopMcpRelay}
        restartMcpRelay={restartMcpRelay}
        removeMcpRelay={removeMcpRelay}
        discoverMcpRelay={discoverMcpRelay}
        testMcpRelay={testMcpRelay}
        classifyMcpTool={classifyMcpTool}
        callMcpTestTool={callMcpTestTool}
        approveApproval={approveApproval}
        refreshApprovals={refreshApprovals}
        setup={setup}
        refreshSetupStatus={refreshSetupStatus}
        go={go}
      />
      <AuditView view={view} events={auditEvents} refresh={loadAuditEvents} />
      <TaskDetailsDrawer
        taskId={selectedTaskId}
        detail={taskDetails}
        loading={taskDetailsLoading}
        error={taskDetailsError}
        models={models}
        closeTaskDetails={closeTaskDetails}
        refreshTaskDetails={loadTaskDetails}
        cancelTask={cancelTask}
        pauseTask={pauseTask}
        resumeTask={resumeTask}
        openTaskDetails={openTaskDetails}
        approveApproval={approveApproval}
        denyApproval={denyApproval}
        returnFocusRef={taskDetailsReturnRef}
      />
      {showOnboarding && (
        <Onboarding
          hasSeededModels={models.length > 0}
          onDiscoverModels={() => { setOnboarded(true); go("discover"); }}
          onOpenRegistry={() => { setOnboarded(true); go("models"); }}
          onConnectLocalEndpoint={() => { setOnboarded(true); go("models"); }}
          onEnableTestingMode={() => { updateTestingMode(true); setOnboarded(true); go("home"); }}
          onDismiss={() => setOnboarded(true)}
        />
      )}
    </AppShell>
  );
}

async function fetchModels() {
  const registry = await api("/api/model-registry");
  return registry.models || [];
}

// Start every normal session deliberately unselected. A runtime may still be
// loaded in the background, but chat should not silently attach to yesterday's
// model. Testing Mode is the only explicit boot-time selection.
function pickBootModel(models, prefs) {
  if (prefs.testingMode) {
    return models.some((model) => model.key === "dry-run") ? "dry-run" : null;
  }
  return null;
}

async function fetchAuditEvents() {
  const audit = await api("/api/audit");
  return audit.events || [];
}

function normalizeTheme(value) {
  return window.rasputinTheme?.normalize?.(value) || (themeOptions.some(([key]) => key === value) ? value : "rasputin-dark");
}

function readInitialTheme() {
  const storedTheme = localStorage.getItem("rasputin-theme");
  const themeWasExplicitlyChosen = localStorage.getItem("rasputin-theme-explicit") === "1";
  return normalizeTheme(!themeWasExplicitlyChosen && storedTheme === "rasputin-light" ? "rasputin-dark" : storedTheme || "rasputin-dark");
}

function updateThemeChrome(theme) {
  window.rasputinTheme?.apply?.(theme);
}
