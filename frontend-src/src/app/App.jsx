import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AppShell } from "../components/AppShell.jsx";
import { useToast } from "../components/Toast.jsx";
import { Onboarding } from "../components/Onboarding.jsx";
import { api, postJson, postJsonStream } from "../api/client.js";
import { LoginShell } from "../features/auth/LoginShell.jsx";
import { HomeView } from "../features/chat/HomeView.jsx";
import { DashboardView } from "../features/dashboard/DashboardView.jsx";
import { ModelsView } from "../features/models/ModelsView.jsx";
import { SettingsView } from "../features/settings/SettingsView.jsx";
import { ActivityView } from "../features/tasks/TasksView.jsx";
import { TaskDetailsDrawer } from "../features/tasks/TaskDetailsDrawer.jsx";
import { WorkspacesView } from "../features/workspaces/WorkspacesView.jsx";
import { AuditView } from "../features/audit/AuditView.jsx";
import {
  AgentsView,
  ApprovalsView,
  MemoryView,
  SchedulesView,
  SessionsView,
  SkillsView,
  TelegramView,
} from "../features/runtime/RuntimeViews.jsx";
import { ArchiveView } from "../features/archive/ArchiveView.jsx";
import { WarsatView } from "../features/warsat/WarsatView.jsx";
import { TrialsView } from "../features/trials/TrialsView.jsx";
import { readStoredFlag, useLocalStorageFlag } from "../hooks/useLocalStorageFlag.js";
import {
  settingsItems,
  themeOptions,
} from "../lib/constants.js";
import {
  displayModelName,
  displayWorkspaceName,
  isModelHealthy,
  isUserFacingModel,
} from "../lib/display.js";
import { useSettingsStore } from "../features/settings/settingsStore.js";
import { loadSettings } from "../features/settings/settingsActions.js";
import { ENGINE_PROTOCOLS } from "../lib/engines.js";

const routedViews = new Set([
  "home",
  "chat",
  "workspaces",
  "activity",
  "models",
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
]);

const routedSettingsSections = new Set(settingsItems.map(([section]) => section));

function parseAppRouteHash() {
  const raw = window.location.hash.replace(/^#\/?/, "").trim();
  if (!raw) return { view: "home", section: undefined };
  const [rawView, rawSection] = raw.split("/");
  const routeView = routedViews.has(rawView) ? rawView : "home";
  const routeSection = routeView === "settings" && routedSettingsSections.has(rawSection) ? rawSection : undefined;
  return { view: routeView, section: routeSection };
}

function routeHashFor(view, section) {
  if (view === "settings") return `#settings/${section || "general"}`;
  return `#${view || "home"}`;
}

export function App() {
  const queryClient = useQueryClient();
  const [ready, setReady] = useState(false);
  const [loginVisible, setLoginVisible] = useState(true);
  const [loginStatus, setLoginStatus] = useState("");
  const [session, setSession] = useState(null);
  const [view, setView] = useState("home");
  const [settingsSection, setSettingsSection] = useState("general");
  const [sidebarCollapsed, setSidebarCollapsed] = useLocalStorageFlag("rasputin-sidebar-collapsed", false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [theme, setTheme] = useState(() => normalizeTheme(localStorage.getItem("rasputin-theme") || "rasputin-light"));
  const [models, setModels] = useState([]);
  const [modelProviders, setModelProviders] = useState([]);
  const [modelCatalog, setModelCatalog] = useState({ items: [], categories: [], runtimes: [], source: {} });
  const [modelCatalogLoading, setModelCatalogLoading] = useState(false);
  const [modelCatalogError, setModelCatalogError] = useState("");
  const [selectedModel, setSelectedModel] = useState(null);
  const [testingMode, setTestingMode] = useState(false);
  const [taskMode, setTaskMode] = useState("chat");
  const [reasoningMode, setReasoningMode] = useState("auto");
  const [modeModelOverrides, setModeModelOverrides] = useState({});
  const [subagentCount, setSubagentCount] = useState(0);
  const [queuedMessages, setQueuedMessages] = useState([]);
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
  const [globalStatus, setGlobalStatus] = useState("");
  const toast = useToast();
  const eventSourceRef = useRef(null);
  const selectedTaskIdRef = useRef(null);
  const taskDetailsReturnRef = useRef(null);
  const bootPhaseRef = useRef("starting");
  const modeModelOverridesRef = useRef(modeModelOverrides);
  const authenticated = !!session?.authenticated && !loginVisible;

  // First-run onboarding: show once when the model registry is empty and the
  // flag is unset. Auto-mark onboarded once any model exists.
  const [onboarded, setOnboarded] = useLocalStorageFlag("rasputin-onboarded", false);
  const showOnboarding = authenticated && ready && !onboarded && models.length === 0;
  useEffect(() => {
    if (authenticated && ready && !onboarded && models.length > 0) setOnboarded(true);
  }, [authenticated, ready, onboarded, models.length, setOnboarded]);

  const visibleModels = useMemo(() => {
    const shown = models.filter((model) => isUserFacingModel(model, testingMode));
    const selected = models.find((model) => model.key === selectedModel);
    if (selected && selected.key !== "local-embeddings" && !shown.some((model) => model.key === selected.key)) {
      return [selected, ...shown];
    }
    return shown.length ? shown : models.filter(
      (model) => model.key !== "local-embeddings" && (testingMode || model.key !== "dry-run"),
    );
  }, [models, selectedModel, testingMode]);

  const selectedModelObject = useMemo(
    () => models.find((model) => model.key === selectedModel) || visibleModels.find((model) => model.role === "main") || visibleModels[0] || null,
    [models, selectedModel, visibleModels],
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
  useEffect(() => {
    if (!models.length) return;
    const current = models.find((model) => model.key === selectedModel);
    if (current && isUserFacingModel(current, testingMode)) return;
    const fallback = models.find((model) => model.role === "main" && isUserFacingModel(model, testingMode))
      || models.find((model) => isUserFacingModel(model, testingMode));
    if (fallback) setSelectedModel(fallback.key);
    else if (!testingMode && selectedModel === "dry-run") setSelectedModel(null);
  }, [testingMode, selectedModel, models]);

  const activeWorkspaceName = workspace.activeName || displayWorkspaceName(workspace.activePath);
  const activeWorkspaceEntry = (workspace.workspaces || []).find(
    (item) => item.id === (workspace.activeId || workspace.active_id)
  );
  const trustedWorkspace = activeWorkspaceEntry?.trusted
    ? { active: true, id: activeWorkspaceEntry.id, name: activeWorkspaceEntry.displayName || activeWorkspaceEntry.name || activeWorkspaceName }
    : null;
  const healthy = isModelHealthy(selectedModelObject);
  const homeTasks = tasks.filter((task) => !task.parentId && homeTaskIds.has(task.id));
  const runningTasks = tasks.filter((task) => ["queued", "running", "paused"].includes(task.status));
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
    boot();
    return () => eventSourceRef.current?.close();
  }, []);

  useEffect(() => {
    function applyHashRoute() {
      const route = parseAppRouteHash();
      go(route.view, route.section, { fromHistory: true });
    }
    applyHashRoute();
    window.addEventListener("hashchange", applyHashRoute);
    window.addEventListener("popstate", applyHashRoute);
    return () => {
      window.removeEventListener("hashchange", applyHashRoute);
      window.removeEventListener("popstate", applyHashRoute);
    };
  }, []);

  useEffect(() => {
    if (ready) return undefined;
    const timer = window.setTimeout(() => {
      const loginRendered = document.querySelector("#loginShell");
      if (loginRendered && ["login", "error"].includes(bootPhaseRef.current)) {
        document.body.dataset.ready = "true";
        setReady(true);
      }
    }, 12000);
    return () => window.clearTimeout(timer);
  }, [ready]);

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
        selectedModel,
        testingMode,
        activeWorkspace: workspace.activePath || ".",
        skill: "general",
        taskMode,
        reasoning: reasoningMode,
        modeModelOverrides: modeModelOverridesRef.current,
        subagents: subagentCount,
        workspaceExplorer,
        activeView: view,
        activeSettingsSection: settingsSection,
        activeChatFolder,
      }).catch(() => {});
    }, 450);
    return () => window.clearTimeout(timer);
  }, [theme, sidebarCollapsed, selectedModel, testingMode, taskMode, reasoningMode, modeModelOverrides, subagentCount, workspace.activePath, workspaceExplorer, view, settingsSection, activeChatFolder, session, ready]);

  async function boot() {
    const markReady = () => {
      document.body.dataset.ready = "true";
      setReady(true);
    };
    try {
      bootPhaseRef.current = "starting";
      const authSession = await api("/api/auth/session");
      setSession(authSession);
      if (!authSession.authenticated) {
        bootPhaseRef.current = "login";
        setLoginVisible(true);
        markReady();
        return;
      }
      bootPhaseRef.current = "loadingApp";
      await loadBasics();
      setLoginVisible(false);
      connectEvents();
      bootPhaseRef.current = "ready";
      markReady();
    } catch (error) {
      bootPhaseRef.current = "error";
      setLoginStatus(error.message);
      markReady();
    }
  }

  async function loadBasics() {
    const data = await api("/api/ui/bootstrap");
    const prefs = data.preferences || {};
    setModels(data.models || []);
    setModelProviders(data.modelProviders || []);
    setModelCatalog(data.modelCatalog || { items: [], categories: [], runtimes: [], source: {} });
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
    const localSidebarCollapsed = readStoredFlag("rasputin-sidebar-collapsed");
    setTheme(normalizeTheme(localTheme || prefs.theme || "rasputin-light"));
    setSidebarCollapsed(localSidebarCollapsed === null ? !!prefs.sidebarCollapsed : localSidebarCollapsed);
    setTestingMode(!!prefs.testingMode);
    setSelectedModel(!prefs.testingMode && prefs.selectedModel === "dry-run" ? null : prefs.selectedModel || null);
    setTaskMode(prefs.taskMode || "chat");
    setReasoningMode(prefs.reasoning || "auto");
    setModeModelOverrides(prefs.modeModelOverrides || {});
    setSubagentCount(Math.max(0, Math.min(Number(prefs.subagents || 0), 4)));
    setWorkspaceExplorer(prefs.workspaceExplorer || {});
    const route = parseAppRouteHash();
    const hasExplicitRoute = Boolean(window.location.hash.replace(/^#\/?/, "").trim());
    setView(hasExplicitRoute ? route.view : prefs.activeView || "home");
    setSettingsSection(hasExplicitRoute && route.view === "settings" ? route.section || "general" : prefs.activeSettingsSection || "general");
    setActiveChatFolder(prefs.activeChatFolder || "all");
    loadWorkspaceRoots(data.workspace?.activePath || ".", prefs.workspaceExplorer || {}).catch((error) => {
      setWorkspaceRoots([]);
      setWorkspaceBrowse(null);
      setGlobalStatus(`Workspace browser will retry when opened: ${error.message}`);
    });
    // Platform settings (Default Inference Engine etc.) affect behavior
    // outside the Settings view, so load them at boot, not on first visit.
    loadSettings();
    // The bootstrap catalog has no VRAM-based fit labels; swap in the
    // hardware-aware copy in the background.
    api("/api/model-catalog?fit=true").then(setModelCatalog).catch(() => {});
  }

  async function loadModels() {
    const nextModels = await queryClient.fetchQuery({ queryKey: ["model-registry"], queryFn: fetchModels });
    setModels(nextModels);
    return nextModels;
  }

  async function loadModelCatalog(refresh = false) {
    setModelCatalogLoading(true);
    setModelCatalogError("");
    try {
      if (refresh) {
        await postJson("/api/model-catalog/refresh", { force: false });
      }
      // fit=true runs the hardware probe so catalog entries carry real
      // VRAM-based fit labels instead of generic estimates.
      const nextCatalog = await api("/api/model-catalog?fit=true");
      setModelCatalog(nextCatalog);
      setGlobalStatus(refresh
        ? `Model catalog refreshed. ${nextCatalog.count || 0} entries available.`
        : "Model catalog loaded.");
      return nextCatalog;
    } catch (error) {
      setModelCatalogError(error.message);
      setGlobalStatus(error.message);
      return null;
    } finally {
      setModelCatalogLoading(false);
    }
  }

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

  async function loadMcpRelays() {
    const nextRelays = await api("/api/mcp/servers");
    setMcpRelays(nextRelays || { servers: [] });
    return nextRelays;
  }

  async function registerMcpRelay(payload) {
    const registered = await postJson("/api/mcp/servers", payload);
    await Promise.allSettled([loadMcpRelays(), refreshApprovals()]);
    setGlobalStatus(registered.approval?.code ? `MCP registration approval ${registered.approval.code} created.` : "MCP server registered.");
    return registered;
  }

  async function registerMcpFixture() {
    const registered = await postJson("/api/mcp/fixtures/operator/register", {});
    await Promise.allSettled([loadMcpRelays(), refreshApprovals()]);
    setGlobalStatus(registered.approval?.code ? `Operator fixture approval ${registered.approval.code} created.` : "Operator MCP fixture registered.");
    return registered;
  }

  async function startMcpRelay(server) {
    const approvalId = server?.pendingApprovalId || "";
    const started = await postJson(`/api/mcp/servers/${server.id}/start`, { approvalId });
    await Promise.allSettled([loadMcpRelays(), loadTools(), refreshApprovals()]);
    setGlobalStatus(`${started.name || server.id} started.`);
    return started;
  }

  async function stopMcpRelay(server) {
    const stopped = await postJson(`/api/mcp/servers/${server.id}/stop`, {});
    await Promise.allSettled([loadMcpRelays(), loadTools()]);
    setGlobalStatus(`${stopped.name || server.id} stopped.`);
    return stopped;
  }

  async function discoverMcpRelay(server) {
    const discovered = await postJson(`/api/mcp/servers/${server.id}/discover`, {});
    await Promise.allSettled([loadMcpRelays(), loadTools()]);
    setGlobalStatus(discovered.message || `Discovered tools for ${server.name || server.id}.`);
    return discovered;
  }

  async function testMcpRelay(server) {
    const tested = await postJson(`/api/mcp/servers/${server.id}/test`, {});
    await Promise.allSettled([loadMcpRelays(), loadTools()]);
    setGlobalStatus(tested.message || `${server.name || server.id} initialized.`);
    return tested;
  }

  async function classifyMcpTool(toolId, payload) {
    const classified = await postJson(`/api/mcp/tools/${encodeURIComponent(toolId)}/classify`, payload);
    await Promise.allSettled([loadMcpRelays(), loadTools()]);
    setGlobalStatus(`${classified.displayName || classified.id} classified.`);
    return classified;
  }

  async function callMcpTestTool(toolId, message = "operator fixture ok") {
    const detail = await postJson(`/api/mcp/tools/${encodeURIComponent(toolId)}/test-call`, { message });
    await Promise.allSettled([loadTasks(), loadTools(), loadMcpRelays()]);
    const taskId = detail?.task?.id;
    if (taskId) openTaskDetails(taskId);
    setGlobalStatus("MCP fixture tool call recorded in task details.");
    return detail;
  }

  async function refreshActivity() {
    const [nextTasks] = await Promise.all([loadTasks(), loadTools(), loadMcpRelays()]);
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
    const routedModel = modelKeyForMode(mode);
    if (routedModel) setSelectedModel(routedModel);
  }, [modelKeyForMode]);

  const setModeModelOverride = useCallback((mode, modelKey) => {
    setModeModelOverrides((current) => {
      const next = { ...current };
      if (!modelKey) {
        delete next[mode];
      } else {
        next[mode] = modelKey;
      }
      modeModelOverridesRef.current = next;
      if (mode === taskMode) {
        const routedModel = modelKeyForMode(mode, next);
        if (routedModel) setSelectedModel(routedModel);
      }
      return next;
    });
  }, [modelKeyForMode, taskMode]);

  function connectEvents() {
    eventSourceRef.current?.close();
    const source = new EventSource("/api/events");
    eventSourceRef.current = source;
    source.onmessage = (message) => {
      try {
        const data = JSON.parse(message.data);
        if (data.tasks) {
          queryClient.setQueryData(["tasks"], data.tasks);
          setTasks(data.tasks);
        }
        if (data.task) {
          setTasks((current) => [data.task, ...current.filter((task) => task.id !== data.task.id)]);
          queryClient.setQueryData(["tasks"], (current = []) => [data.task, ...current.filter((task) => task.id !== data.task.id)]);
          if (selectedTaskIdRef.current === data.task.id) {
            // Merge the streamed snapshot straight into the open drawer so
            // tokens/steps paint live; only refetch the full detail (events,
            // approvals, children) once the task leaves the running state.
            setTaskDetails((current) =>
              current?.task?.id === data.task.id ? { ...current, task: { ...current.task, ...data.task } } : current,
            );
            if (!["running", "queued"].includes(data.task.status)) {
              loadTaskDetails(selectedTaskIdRef.current, { silent: true });
            }
          } else if (selectedTaskIdRef.current) {
            loadTaskDetails(selectedTaskIdRef.current, { silent: true });
          }
        }
        if (data.approvals) setApprovals(data.approvals);
        if (data.memoryReview) setMemoryReview(data.memoryReview);
        if (data.telegram) setTelegramConfig(data.telegram);
      } catch {
        setGlobalStatus("Live update failed.");
      }
    };
  }

  function applyView(nextView, section) {
    setView(nextView);
    if (section) setSettingsSection(section);
    if (nextView === "workspaces") {
      loadWorkspaceRoots().catch((error) => setGlobalStatus(error.message));
    }
    if (["activity", "agents", "sessions", "approvals", "memory", "skills", "telegram", "schedules"].includes(nextView)) {
      loadRuntimeData().catch((error) => setGlobalStatus(error.message));
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
    setMobileSidebarOpen(false);
  }

  function go(nextView, section, options = {}) {
    applyView(nextView, section);
    if (options.fromHistory) return;
    const nextHash = routeHashFor(nextView, section);
    if (window.location.hash !== nextHash) {
      window.history.pushState(null, "", nextHash);
    }
  }

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
      await loadBasics();
      connectEvents();
    } catch (error) {
      setLoginStatus(error.message);
    }
  }

  async function logout() {
    eventSourceRef.current?.close();
    await api("/api/auth/logout", { method: "POST" });
    setSession(null);
    setLoginVisible(true);
  }

  async function startNewChat() {
    try {
      const detail = await postJson("/api/sessions", {
        title: "New chat",
        workspace: workspace.activePath || ".",
        model: selectedModel,
        mode: taskMode,
        skill: "general",
        folder: activeChatFolder && !["all", "unfiled"].includes(activeChatFolder) ? activeChatFolder : "",
      });
      const sessionId = detail?.session?.id;
      setHomeTaskIds(new Set());
      setSelectedSession(detail);
      setActiveChatSessionId(sessionId || null);
      setObjective("");
      setQueuedMessages([]);
      go("chat");
      loadChatFolders().catch((error) => setGlobalStatus(error.message));
      setGlobalStatus("New chat created.");
      return detail;
    } catch (error) {
      setGlobalStatus(error.message);
      return null;
    }
  }

  async function sendTask(event, customMessage = null, options = {}) {
    if (event) event.preventDefault();
    const message = customMessage || objective.trim();
    const mode = options.mode || taskMode;
    const reasoning = options.reasoning || reasoningMode;
    const modelKey = options.model || selectedModel;
    if (!healthy) {
      setComposerStatus("Select Testing Mode or test a healthy local model before sending.");
      return false;
    }
    if (!message) {
      setComposerStatus("Write a message first.");
      return false;
    }
    const tempId = `pending-${Date.now()}`;
    const tempTask = {
      id: tempId,
      sessionId: activeChatSessionId,
      objective: message,
      model: modelKey,
      skill: "general",
      mode,
      reasoning,
      status: "queued",
      progress: 0,
      logs: ["queued"],
      result: "",
      outputs: [],
      sources: [],
      graph: [],
      trace: [],
      workspace: workspace.activePath || ".",
      parentId: null,
      createdAt: Date.now() / 1000,
    };
    setTasks((current) => [tempTask, ...current.filter((item) => item.id !== tempId)]);
    setHomeTaskIds((current) => new Set([...current, tempId]));
    if (!options.fromQueue) setObjective("");
    try {
      setComposerStatus("");
      const task = await postJson("/api/tasks", {
        objective: message,
        model: modelKey,
        skill: "general",
        mode,
        reasoning,
        subagents: subagentCount,
        workspacePath: workspace.activePath || ".",
        sessionId: activeChatSessionId || undefined,
      });
      setTasks((current) => [task, ...current.filter((item) => item.id !== task.id && item.id !== tempId)]);
      queryClient.setQueryData(["tasks"], (current = []) => [task, ...current.filter((item) => item.id !== task.id && item.id !== tempId)]);
      setHomeTaskIds((current) => {
        const next = new Set(current);
        next.delete(tempId);
        next.add(task.id);
        return next;
      });
      setActiveChatSessionId(task.sessionId || activeChatSessionId);
      api("/api/sessions").then(setSessions).catch(() => {});
      setGlobalStatus(subagentCount ? `Agent run started with ${subagentCount} sub-agent${subagentCount === 1 ? "" : "s"}.` : "Task started.");
      return true;
    } catch (error) {
      setTasks((current) => current.filter((item) => item.id !== tempId));
      setHomeTaskIds((current) => {
        const next = new Set(current);
        next.delete(tempId);
        return next;
      });
      if (!options.fromQueue) setObjective(message);
      setComposerStatus(error.message);
      return false;
    }
  }

  const queueMessage = useCallback((text, options = {}) => {
    const trimmed = String(text || "").trim();
    if (!trimmed) return null;
    const entry = {
      id: `queued-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      text: trimmed,
      mode: options.mode || taskMode,
      reasoning: options.reasoning || reasoningMode,
    };
    setQueuedMessages((current) => [...current, entry]);
    return entry;
  }, [taskMode, reasoningMode]);

  const removeQueuedMessage = useCallback((id) => {
    setQueuedMessages((current) => current.filter((item) => item.id !== id));
  }, []);

  const clearQueuedMessages = useCallback(() => setQueuedMessages([]), []);

  // Drain the queue: whenever the current chat has no active task, send the
  // next queued message. Failures land in composerStatus and drop the entry
  // from the queue so a broken runtime can't retry-loop.
  const queueDispatchRef = useRef(false);
  useEffect(() => {
    if (!queuedMessages.length || queueDispatchRef.current || !healthy) return;
    const busy = tasks.some((task) => !task.parentId && homeTaskIds.has(task.id)
      && ["queued", "running", "paused"].includes(task.status));
    if (busy) return;
    const [next, ...rest] = queuedMessages;
    queueDispatchRef.current = true;
    setQueuedMessages(rest);
    sendTask(null, next.text, { mode: next.mode, reasoning: next.reasoning, fromQueue: true })
      .then((sent) => {
        if (!sent) {
          // Recover the text into the composer (if it's free) so nothing is lost.
          setObjective((current) => current || next.text);
          setGlobalStatus("A queued message failed to send. Its text was returned to the composer.");
        }
      })
      .finally(() => {
        queueDispatchRef.current = false;
      });
  }, [tasks, queuedMessages, healthy, homeTaskIds]);

  async function cancelTask(taskId) {
    try {
      await postJson(`/api/tasks/${taskId}/cancel`, {});
      setGlobalStatus("Task stop requested.");
      await loadTasks();
      if (selectedTaskIdRef.current) await loadTaskDetails(selectedTaskIdRef.current, { silent: true });
    } catch (error) {
      setGlobalStatus(error.message);
    }
  }

  async function pauseTask(taskId) {
    try {
      await postJson(`/api/tasks/${taskId}/pause`, {});
      setGlobalStatus("Task paused.");
      await loadTasks();
      if (selectedTaskIdRef.current) await loadTaskDetails(selectedTaskIdRef.current, { silent: true });
    } catch (error) {
      setGlobalStatus(error.message);
    }
  }

  async function resumeTask(taskId) {
    try {
      await postJson(`/api/tasks/${taskId}/resume`, {});
      setGlobalStatus("Task resumed.");
      await loadTasks();
      if (selectedTaskIdRef.current) await loadTaskDetails(selectedTaskIdRef.current, { silent: true });
    } catch (error) {
      setGlobalStatus(error.message);
    }
  }

  async function runModelAction(action, key = selectedModelObject?.key || selectedModel) {
    try {
      const result = await postJson(`/api/model-registry/${action}`, { key });
      setGlobalStatus(action === "repair" && result.repaired ? "Model repaired." : `${action} finished.`);
      await loadModels();
    } catch (error) {
      setGlobalStatus(error.message);
    }
  }

  async function registerLocalModel(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const model = {
      key: form.get("key") || undefined,
      name: form.get("name") || form.get("model") || "Local Model",
      provider: form.get("provider") || "openai-compatible",
      role: form.get("role") || "helper",
      baseUrl: form.get("baseUrl"),
      model: form.get("model"),
      runtime: "external-local",
      contextWindow: Number(form.get("contextWindow") || 0) || undefined,
      maxTokens: Number(form.get("maxTokens") || 0) || undefined,
      enabled: true,
      managed: false,
      notes: form.get("notes") || "Connected from the Models tab.",
    };
    if (!model.baseUrl || !model.model) {
      setGlobalStatus("Enter a local endpoint and model id.");
      return null;
    }
    try {
      const saved = await postJson("/api/model-registry/upsert", model);
      await loadModels();
      setSelectedModel(saved.key);
      setGlobalStatus(`Connected ${saved.name || saved.model}. Run Test health next.`);
      event.currentTarget.reset();
      return saved;
    } catch (error) {
      setGlobalStatus(error.message);
      return null;
    }
  }

  async function registerApiModel(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const provider = form.get("provider") || "openai";
    const modelId = form.get("model");
    const apiKey = form.get("apiKey");
    const apiKeyEnv = form.get("apiKeyEnv");
    const model = {
      name: form.get("name") || modelId || "API Model",
      provider,
      role: form.get("role") || "helper",
      baseUrl: form.get("baseUrl"),
      model: modelId,
      apiKey: apiKey || undefined,
      apiKeyEnv: apiKeyEnv || undefined,
      anthropicVersion: form.get("anthropicVersion") || undefined,
      runtime: "remote-api",
      contextWindow: Number(form.get("contextWindow") || 0) || undefined,
      maxTokens: Number(form.get("maxTokens") || 0) || undefined,
      enabled: true,
      managed: false,
      notes: form.get("notes") || "External API model. Requires remote models to be enabled in Safety.",
    };
    if (!model.model) {
      setGlobalStatus("Enter a provider model id.");
      return null;
    }
    if (!model.apiKey && !model.apiKeyEnv) {
      setGlobalStatus("Use an environment variable name or paste a key into the local secret store.");
      return null;
    }
    try {
      const saved = await postJson("/api/model-registry/upsert", model);
      await loadModels();
      setSelectedModel(saved.key);
      setGlobalStatus(`Registered ${saved.name || saved.model}. Run Test health after Safety allows remote models.`);
      event.currentTarget.reset();
      return saved;
    } catch (error) {
      setGlobalStatus(error.message);
      return null;
    }
  }

  async function scanGguf() {
    try {
      const result = await postJson("/api/model-registry/scan-gguf", {});
      setGlobalStatus(`GGUF scan found ${result.count || 0} model files.`);
      await loadModels();
    } catch (error) {
      setGlobalStatus(error.message);
    }
  }

  async function browseWorkspace(rootId, path) {
    const browsed = await postJson("/api/workspace/browse", { rootId, path });
    setWorkspaceBrowse(browsed);
    setWorkspaceExplorer({ rootId, path: browsed.path });
  }

  async function previewWorkspaceFile(rootId, path) {
    return postJson("/api/workspace/preview-file", { rootId, path });
  }

  async function refreshKnowledgeStats() {
    const [nextRagStats, nextGraphStats] = await Promise.all([
      api("/api/rag/stats"),
      api("/api/graph/stats"),
    ]);
    setRagStats(nextRagStats);
    setGraphStats(nextGraphStats);
    return { ragStats: nextRagStats, graphStats: nextGraphStats };
  }

  async function indexWorkspaceKnowledge(path) {
    const targetPath = path || workspace.activePath || ".";
    const ragResult = await postJson("/api/rag/ingest", { path: targetPath, label: displayWorkspaceName(targetPath) });
    const graphResult = await postJson("/api/graph/build", { path: targetPath });
    await refreshKnowledgeStats();
    setWorkspace(await api("/api/workspace"));
    await loadWorkspaceRoots(targetPath, { rootId: workspaceBrowse?.root?.id || workspaceExplorer?.rootId, path: targetPath });
    setGlobalStatus(`Knowledge indexed for ${displayWorkspaceName(targetPath)}.`);
    return { ragResult, graphResult };
  }

  async function searchWorkspaceKnowledge(query, path) {
    const targetPath = path || workspace.activePath || ".";
    const [ragResult, graphResult] = await Promise.all([
      postJson("/api/rag/search", { query, path: targetPath, limit: 5 }),
      postJson("/api/graph/search", { query, limit: 8 }),
    ]);
    return { ragResult, graphResult };
  }

  async function approvePath(path) {
    const approved = await postJson("/api/workspace/approve", {
      path,
      name: displayWorkspaceName(path),
      readOnly: true,
    });
    const active = await postJson("/api/workspace/select", { path: approved.id || path });
    setWorkspace(active);
    await loadWorkspaceRoots(active.activePath);
  }

  async function selectWorkspace(path) {
    try {
      const active = await postJson("/api/workspace/select", { path });
      setWorkspace(active);
      await loadWorkspaceRoots(active.activePath);
      setGlobalStatus(`Workspace set to ${active.activeName || displayWorkspaceName(active.activePath)}.`);
    } catch (error) {
      setGlobalStatus(error.message);
    }
  }

  async function setWorkspaceTrust(workspaceId, trusted) {
    try {
      await postJson("/api/workspace/trust", { workspaceId, trusted });
      setWorkspace(await api("/api/workspace"));
      await loadWorkspaceRoots(workspace.activePath);
      setGlobalStatus(
        trusted
          ? "Trusted Dev Mode enabled. Shell, file writes, and git run without per-action approval in this workspace."
          : "Trusted Dev Mode revoked for this workspace."
      );
    } catch (error) {
      setGlobalStatus(error.message);
    }
  }

  async function previewMount(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      const plan = await postJson("/api/workspace/mount-plan", {
        hostPath: form.get("hostPath"),
        name: form.get("name") || undefined,
        readOnly: form.get("readOnly") === "on",
      });
      setMountPlan(plan);
    } catch (error) {
      setMountPlan({ error: error.message });
    }
  }

  async function requestMount(plan) {
    if (!plan?.hostPath) return;
    try {
      const saved = await postJson("/api/workspace/mount-apply", {
        hostPath: plan.hostPath,
        name: plan.displayName || undefined,
        readOnly: !!plan.readOnly,
      });
      setMountPlan({ ...saved, saved: true });
      setGlobalStatus("Mount request saved. Restart Rasputin with the generated volume before browsing that folder.");
    } catch (error) {
      setMountPlan({ ...plan, applyError: error.message });
      setGlobalStatus(error.message);
    }
  }

  async function saveSafety(event) {
    let payload = event;
    if (event?.preventDefault) {
      event.preventDefault();
      const form = new FormData(event.currentTarget);
      const keys = [
        "privacyLock", "allowFileRead", "allowFileWrite", "allowFileReorganize", "allowShellExecution",
        "allowWebSearch", "allowDockerControl", "allowModelTests", "allowModelRegistryEdit", "allowRemoteModels",
        "approvalRequiredFileWrite", "approvalRequiredFileMove", "approvalRequiredWebSearch", "auditEnabled",
      ];
      payload = Object.fromEntries(keys.map((key) => [key, form.get(key) === "on"]));
      payload.webSearchMaxChars = Number(form.get("webSearchMaxChars") || 180);
    }
    setSecurity(await postJson("/api/security", payload));
    setGlobalStatus("Safety settings saved.");
  }

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
    const [nextSessions, nextChatFolders, nextApprovals, nextMemoryReview, nextSkills, nextTelegram, nextSchedules] = await Promise.all([
      api("/api/sessions"),
      api("/api/chat-folders"),
      api("/api/approvals"),
      api("/api/memory/review"),
      api("/api/skills"),
      api("/api/integrations/telegram"),
      api("/api/schedules"),
    ]);
    setSessions(nextSessions);
    setChatFolders(nextChatFolders);
    setApprovals(nextApprovals);
    setMemoryReview(nextMemoryReview);
    setSkillRegistry(nextSkills);
    setTelegramConfig(nextTelegram);
    setSchedulesList(nextSchedules);
  }

  async function loadArchive() {
    const nextArchive = await api("/api/archive/sessions");
    setArchiveSessions(nextArchive);
    return nextArchive;
  }

  async function saveArchiveDraft(payload) {
    setArchiveStatus("");
    const saved = await postJson("/api/archive/sessions", payload);
    const nextArchive = await loadArchive();
    setArchiveStatus(`Saved ${saved.title}.`);
    return { saved, archive: nextArchive };
  }

  async function exportArchiveDraft(id) {
    setArchiveStatus("");
    const exported = await postJson("/api/archive/export", { id });
    setArchiveStatus(`Exported to ${exported.path}.`);
    return exported;
  }

  async function searchArchiveCitations(query) {
    const targetPath = workspace.activePath || ".";
    return postJson("/api/archive/citations", {
      query,
      path: targetPath,
      limit: 6,
    });
  }

  async function loadTrials() {
    const nextTrials = await api("/api/trials");
    setTrialsRuns(nextTrials);
    return nextTrials;
  }

  async function refreshSetupStatus() {
    const nextSetup = await api("/api/setup/status");
    setSetup(nextSetup);
    return nextSetup;
  }

  async function runTrialCompare(payload) {
    setTrialsStatus("Running blind comparison.");
    const run = await postJson("/api/trials/compare", payload);
    const nextTrials = await loadTrials();
    setTrialsStatus(`Trial ${run.id} finished.`);
    return { run, trials: nextTrials };
  }

  async function revealTrial(runId) {
    const run = await postJson(`/api/trials/${runId}/reveal`, {});
    await loadTrials();
    setTrialsStatus(`Revealed trial ${run.id}.`);
    return run;
  }

  async function saveTrialRoute(runId, outputId, mode) {
    const result = await postJson(`/api/trials/${runId}/routing`, { outputId, mode });
    const route = result.route || {};
    const routeModelKey = route.modelKey || route.model_key;
    const overrides = result.preferences?.modeModelOverrides || result.preferences?.mode_model_overrides || (
      routeModelKey ? { ...modeModelOverridesRef.current, [mode]: routeModelKey } : modeModelOverridesRef.current
    );
    modeModelOverridesRef.current = overrides;
    setModeModelOverrides(overrides);
    await postJson("/api/preferences", { modeModelOverrides: overrides });
    if (mode === taskMode && routeModelKey) {
      setSelectedModel(routeModelKey);
    }
    await loadTrials();
    setTrialsStatus(`Saved ${route.modelName || route.model_name || routeModelKey || "model route"} for ${mode}.`);
    return result;
  }

  async function loadChatFolders() {
    const [nextSessions, nextFolders] = await Promise.all([
      api("/api/sessions"),
      api("/api/chat-folders"),
    ]);
    setSessions(nextSessions);
    setChatFolders(nextFolders);
    return { sessions: nextSessions, chatFolders: nextFolders };
  }

  async function createChatFolder(event) {
    event.preventDefault();
    // currentTarget is nulled once the handler's synchronous phase ends, so
    // grab the form element before any await.
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const name = String(form.get("name") || "").trim();
    if (!name) {
      setGlobalStatus("Enter a folder name.");
      return null;
    }
    const nextFolders = await postJson("/api/chat-folders", { name });
    setChatFolders(nextFolders);
    formElement.reset();
    setGlobalStatus("Chat folder created.");
    return nextFolders;
  }

  async function assignSessionFolder(sessionId, folder) {
    if (!sessionId) return null;
    const detail = await postJson(`/api/sessions/${sessionId}/folder`, { folder: folder || "" });
    await loadChatFolders();
    if (selectedSession?.session?.id === sessionId) setSelectedSession(detail);
    setGlobalStatus(folder ? "Chat moved to folder." : "Chat moved to Unfiled.");
    return detail;
  }

  async function loadSession(sessionId) {
    try {
      setSelectedSession(await api(`/api/sessions/${sessionId}`));
    } catch (error) {
      setGlobalStatus(error.message);
    }
  }

  async function resumeSession(sessionId) {
    try {
      const detail = await api(`/api/sessions/${sessionId}`);
      const sessionTasks = detail.tasks || [];
      setSelectedSession(detail);
      setActiveChatSessionId(sessionId);
      setHomeTaskIds(new Set(sessionTasks.filter((task) => !task.parentId).map((task) => task.id)));
      setTasks((current) => {
        const next = new Map(current.map((task) => [task.id, task]));
        sessionTasks.forEach((task) => next.set(task.id, task));
        return Array.from(next.values()).sort((a, b) => Number(b.createdAt || 0) - Number(a.createdAt || 0));
      });
      setObjective("");
      setQueuedMessages([]);
      go("chat");
      setGlobalStatus("Chat restored.");
    } catch (error) {
      setGlobalStatus(error.message);
    }
  }

  async function refreshApprovals() {
    setApprovals(await api("/api/approvals"));
  }

  async function approveApproval(id) {
    const approval = await postJson(`/api/approvals/${id}/approve`, {});
    await refreshApprovals();
    if (selectedTaskIdRef.current) await loadTaskDetails(selectedTaskIdRef.current, { silent: true });
    
    // Auto-resume Warsat deployments
    if (approval.action_type === "warsat_deploy" || approval.actionType === "warsat_deploy") {
      setGlobalStatus("Approval accepted. Starting deployment...");
      deployWarsatPlan();
    } else {
      setGlobalStatus("Approval accepted.");
    }
  }

  async function denyApproval(id) {
    await postJson(`/api/approvals/${id}/deny`, {});
    await refreshApprovals();
    if (selectedTaskIdRef.current) await loadTaskDetails(selectedTaskIdRef.current, { silent: true });
    setGlobalStatus("Approval denied.");
  }

  async function searchMemory(query) {
    if (!query.trim()) return;
    setMemorySearchResults(await postJson("/api/memory/search", { query, limit: 10 }));
  }

  async function approveMemory(id) {
    await postJson("/api/memory/review", { id, action: "approve" });
    setMemoryReview(await api("/api/memory/review"));
    setGlobalStatus("Memory saved.");
  }

  async function rejectMemory(id) {
    await postJson("/api/memory/review", { id, action: "reject" });
    setMemoryReview(await api("/api/memory/review"));
    setGlobalStatus("Memory rejected.");
  }

  async function createSkillFromSession(sessionId) {
    if (!sessionId) return;
    setSkillPreview(await postJson("/api/skills/create-from-session", { sessionId, save: false }));
    setGlobalStatus("Skill preview created.");
  }

  async function enableSkill(name) {
    await postJson(`/api/skills/${name}/enable`, {});
    setSkillRegistry(await api("/api/skills"));
  }

  async function disableSkill(name) {
    await postJson(`/api/skills/${name}/disable`, {});
    setSkillRegistry(await api("/api/skills"));
  }

  async function configureTelegram(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setTelegramConfig(await postJson("/api/integrations/telegram/configure", {
      botToken: form.get("botToken") || undefined,
      allowedChatId: form.get("allowedChatId"),
      redactionMode: form.get("redactionMode") || "summary",
      enabled: form.get("enabled") === "on",
    }));
    setGlobalStatus("Telegram settings saved.");
  }

  async function testTelegram() {
    try {
      const result = await postJson("/api/integrations/telegram/test", {});
      setTelegramConfig(result.result || telegramConfig);
      setGlobalStatus(result.sent ? "Telegram test sent." : "Telegram test skipped.");
    } catch (error) {
      setGlobalStatus(error.message);
    }
  }

  async function createSchedule(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await postJson("/api/schedules", {
      name: form.get("name"),
      prompt: form.get("prompt"),
      intervalSeconds: Number(form.get("intervalSeconds") || 0),
      enabled: form.get("enabled") === "on",
    });
    event.currentTarget.reset();
    setSchedulesList(await api("/api/schedules"));
    setGlobalStatus("Schedule saved.");
  }

  async function loadWarsat() {
    const [nextWarsat, runtimes, hardware] = await Promise.all([
      api("/api/warsat/protocols"),
      api("/api/warsat/runtimes"),
      api("/api/warsat/hardware").catch((error) => ({
        ok: false,
        status: "blocked",
        checks: [],
        warnings: [],
        blockedReasons: [error.message],
        recommendations: ["Check the Rasputin backend logs for Warsat hardware probe errors."],
        detectedHardware: {},
      })),
    ]);
    setWarsat(nextWarsat);
    setWarsatRuntimes(runtimes);
    setWarsatHardware(hardware);
    return nextWarsat;
  }

  async function prepareCatalogModelForWarsat(item, options = {}) {
    if (!item) return null;
    // Honor the Default Inference Engine setting when this model actually
    // offers that runtime; explicit choices and API-only entries still win.
    const preferredProtocol = ENGINE_PROTOCOLS[useSettingsStore.getState().models?.defaultEngine];
    const engineProtocol = preferredProtocol && item.runtimeOptions?.some((option) => option.protocolId === preferredProtocol)
      ? preferredProtocol
      : null;
    const protocolId = options.protocolId || engineProtocol || item.recommendedProtocol || item.runtimeOptions?.[0]?.protocolId || "vllmCudaOpenai";
    if (!protocolId || protocolId === "apiOnly") {
      setGlobalStatus("This catalog entry is API-only. Register it as an API model instead of sending it to Warsat.");
      return null;
    }
    const profile = options.strengthProfile || item.recommendedProfile || "balanced";
    const modelRef = item.warsatModelRef || item.modelId || item.id;
    const port = Number(options.hostPort || 0) || undefined;
    setWarsatError("");
    try {
      await loadWarsat();
      const plan = await postJson("/api/warsat/plan", {
        protocolId,
        modelRef,
        // Only a real local file/folder goes in modelPath; for HF repos the
        // backend resolves a GGUF file and lets llama.cpp download it.
        modelPath: item.modelPath || undefined,
        strengthProfile: profile,
        hostPort: port,
        role: options.role || (item.purpose === "coding" ? "coder" : item.purpose === "research" ? "researcher" : "helper"),
        maxModelLen: item.contextWindow && item.contextWindow <= 32768 ? item.contextWindow : undefined,
        containerName: options.containerName || undefined,
      });
      setWarsatPlan(plan);
      setWarsatDeployment(null);
      go("warsat");
      // Surface fit problems the moment the plan lands, not at deploy time.
      const fitWarning = (plan.warnings || []).find((w) => w.includes("VRAM"));
      setGlobalStatus(fitWarning
        ? `Plan created for ${item.name || modelRef} — heads-up: ${fitWarning}`
        : `Warsat launch plan created for ${item.name || modelRef}.`);
      return plan;
    } catch (error) {
      setWarsatError(error.message);
      setGlobalStatus(error.message);
      return null;
    }
  }

  async function loadWarsatRuntimes() {
    const runtimes = await api("/api/warsat/runtimes");
    setWarsatRuntimes(runtimes);
    return runtimes;
  }

  async function loadWarsatLogs(containerName) {
    if (!containerName) return null;
    try {
      const logs = await postJson("/api/warsat/logs", { containerName, limit: 160 });
      setWarsatLogs(logs);
      return logs;
    } catch (error) {
      setGlobalStatus(error.message);
      return null;
    }
  }

  async function requestWarsatOperation(action, containerName) {
    if (!containerName) return null;
    const currentApprovalId = warsatOperation?.containerName === containerName && warsatOperation?.action === action
      ? warsatOperation?.approval?.id || warsatOperation?.approvalId
      : null;
    try {
      const result = await postJson(`/api/warsat/${action}`, { containerName, approvalId: currentApprovalId });
      setWarsatOperation({ ...result, action });
      if (result.approvalRequired) {
        await refreshApprovals();
        setGlobalStatus(`Approval ${result.approval?.code || ""} created. Approve it before Warsat can ${action} ${containerName}.`);
      } else {
        await Promise.allSettled([loadWarsatRuntimes(), loadModels(), refreshApprovals()]);
        setGlobalStatus(`Warsat ${action} completed for ${containerName}.`);
      }
      return result;
    } catch (error) {
      setGlobalStatus(error.message);
      return null;
    }
  }

  async function createWarsatPlan(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setWarsatError("");
    try {
      const plan = await postJson("/api/warsat/plan", {
        protocolId: form.get("protocolId"),
        modelRef: form.get("modelRef") || undefined,
        modelPath: form.get("modelPath") || undefined,
        strengthProfile: form.get("strengthProfile") || undefined,
        contextWindow: Number(form.get("contextWindow") || 0) || undefined,
        maxModelLen: Number(form.get("maxModelLen") || 0) || undefined,
        gpuMemoryUtilization: Number(form.get("gpuMemoryUtilization") || 0) || undefined,
        gpuLayers: form.get("gpuLayers") === "" ? undefined : Number(form.get("gpuLayers") || 0),
        tensorParallelSize: Number(form.get("tensorParallelSize") || 0) || undefined,
        cpuThreads: Number(form.get("cpuThreads") || 0) || undefined,
        batchSize: Number(form.get("batchSize") || 0) || undefined,
        maxNumSeqs: Number(form.get("maxNumSeqs") || 0) || undefined,
        dtype: form.get("dtype") || undefined,
        quantization: form.get("quantization") || undefined,
        kvCacheDtype: form.get("kvCacheDtype") || undefined,
        swapSpaceGb: Number(form.get("swapSpaceGb") || 0) || undefined,
        memoryLimitGb: Number(form.get("memoryLimitGb") || 0) || undefined,
        cpuLimit: Number(form.get("cpuLimit") || 0) || undefined,
        shmSizeGb: Number(form.get("shmSizeGb") || 0) || undefined,
        gpuDevice: form.get("gpuDevice") || undefined,
        hostPort: Number(form.get("hostPort") || 0) || undefined,
        role: form.get("role") || undefined,
        containerName: form.get("containerName") || undefined,
      });
      setWarsatPlan(plan);
      setWarsatDeployment(null);
      setGlobalStatus("Launch plan ready — review the Mission Brief below, then request deploy approval.");
      return plan;
    } catch (error) {
      setWarsatError(error.message);
      setWarsatPlan(null);
      return null;
    }
  }

  async function enableDockerControl() {
    try {
      const saved = await postJson("/api/security", { ...security, allowDockerControl: true });
      setSecurity(saved);
      await loadWarsat();
      // Plans snapshot the docker flags at creation time, so refresh the
      // active plan or the deploy button stays locked on stale data.
      if (warsatPlan) {
        const plan = await postJson("/api/warsat/plan", {
          protocolId: warsatPlan.protocolId,
          modelRef: warsatPlan.modelRef || undefined,
          modelPath: warsatPlan.modelPath || undefined,
          strengthProfile: warsatPlan.strengthProfile || undefined,
          hostPort: warsatPlan.hostPort || undefined,
          role: warsatPlan.role || undefined,
          containerName: warsatPlan.containerName || undefined,
        });
        setWarsatPlan(plan);
        setWarsatDeployment(null);
      }
      setGlobalStatus("Docker control enabled. WarSat can now launch containers.");
      return true;
    } catch (error) {
      setGlobalStatus(error.message);
      return false;
    }
  }

  async function deployWarsatPlan() {
    if (!warsatPlan) return null;
    setWarsatError("");
    setWarsatDeploying(true);
    const approvalId = warsatDeployment?.approval?.id || warsatDeployment?.approvalId;
    setGlobalStatus(approvalId || warsatPlan.approvalGranted
      ? "Warsat is starting the deployment. Large image pulls stream their progress below."
      : "Creating Warsat deployment approval.");
    try {
      // The endpoint streams NDJSON progress when the deploy executes and
      // answers plain JSON when it only creates an approval request —
      // postJsonStream handles both.
      const deployment = await postJsonStream("/api/warsat/deploy", { plan: warsatPlan, approvalId }, (partial) => {
        setWarsatDeployment(partial);
      });
      setWarsatDeployment(deployment);
      if (deployment.approvalRequired) {
        await refreshApprovals();
        setGlobalStatus(`Approval ${deployment.approval?.code || ""} created. Approve it in Warsat, then run the approved deploy.`);
      } else if (deployment.status === "failed") {
        await Promise.allSettled([loadWarsat(), refreshApprovals()]);
        setGlobalStatus(`Warsat deployment failed during ${deployment.failedPhase || deployment.phase || "deployment"}. Check the launch plan details.`);
      } else {
        await Promise.allSettled([loadWarsat(), loadModels(), refreshApprovals()]);
        setGlobalStatus(`Warsat registered ${deployment.modelKey}. You can test and select it from Models.`);
      }
      return deployment;
    } catch (error) {
      setWarsatError(error.message);
      setGlobalStatus(error.message);
      return null;
    } finally {
      setWarsatDeploying(false);
    }
  }

  if (loginVisible) {
    return <LoginShell onSubmit={login} status={loginStatus} />;
  }

  return (
    <AppShell
      globalStatus={globalStatus}
      clearGlobalStatus={() => setGlobalStatus("")}
      trustedWorkspace={trustedWorkspace}
      onRevokeTrust={() => trustedWorkspace && setWorkspaceTrust(trustedWorkspace.id, false)}
      sidebarProps={{
        collapsed: sidebarCollapsed,
        toggleSidebar,
        view,
        settingsSection,
        go,
        taskCount: tasks.length,
        runningCount: runningTasks.length,
        workspaceName: activeWorkspaceName,
        modelName: displayModelName(selectedModelObject, models),
        locked: security.privacyLock,
        mobileOpen: mobileSidebarOpen,
        newTask: startNewChat,
        recentSessions: sessions?.sessions || [],
        chatFolders,
        activeChatFolder,
        setActiveChatFolder,
        activeSessionId: activeChatSessionId,
        resumeSession,
        createChatFolder,
        assignSessionFolder,
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
        selectedModelObject={selectedModelObject}
        objective={objective}
        setObjective={setObjective}
        sendTask={sendTask}
        healthy={healthy}
      />
      <HomeView
        activeWorkspaceName={activeWorkspaceName}
        view={view}
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
        reasoningMode={reasoningMode}
        setReasoningMode={setReasoningMode}
        queuedMessages={queuedMessages}
        queueMessage={queueMessage}
        removeQueuedMessage={removeQueuedMessage}
        clearQueuedMessages={clearQueuedMessages}
        startNewChat={startNewChat}
        modeModelOverrides={modeModelOverrides}
        setModeModelOverride={setModeModelOverride}
        modelKeyForMode={modelKeyForMode}
        subagentCount={subagentCount}
        setSubagentCount={setSubagentCount}
        runningTasks={runningTasks}
        openTaskDetails={openTaskDetails}
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
        models={models}
        modeModelOverrides={modeModelOverrides}
        setModeModelOverride={setModeModelOverride}
        loadWorkspaceRoots={() => loadWorkspaceRoots(workspace.activePath)}
        previewMount={previewMount}
        requestMount={requestMount}
        mountPlan={mountPlan}
        security={security}
        ragStats={ragStats}
        graphStats={graphStats}
        indexWorkspaceKnowledge={indexWorkspaceKnowledge}
        searchWorkspaceKnowledge={searchWorkspaceKnowledge}
        refreshKnowledgeStats={refreshKnowledgeStats}
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
        memoryReview={memoryReview}
        memorySearchResults={memorySearchResults}
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
        tasks={tasks}
        models={models}
        security={security}
        cancelTask={cancelTask}
        pauseTask={pauseTask}
        resumeTask={resumeTask}
        enableDockerControl={enableDockerControl}
        go={go}
      />
      <ArchiveView
        view={view}
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
      <ModelsView
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
        openWarsat={() => go("warsat")}
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
        openTaskDetails={openTaskDetails}
      />
      <SettingsView
        view={view}
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
        setTheme={setTheme}
        logout={logout}
        loadModels={loadModels}
        tools={tools}
        mcpRelays={mcpRelays}
        registerMcpRelay={registerMcpRelay}
        registerMcpFixture={registerMcpFixture}
        startMcpRelay={startMcpRelay}
        stopMcpRelay={stopMcpRelay}
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
          onScanModels={() => { setOnboarded(true); go("warsat"); }}
          onOpenRegistry={() => { setOnboarded(true); go("models"); }}
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

async function fetchAuditEvents() {
  const audit = await api("/api/audit");
  return audit.events || [];
}

function normalizeTheme(value) {
  return window.rasputinTheme?.normalize?.(value) || (themeOptions.some(([key]) => key === value) ? value : "rasputin-light");
}

function updateThemeChrome(theme) {
  window.rasputinTheme?.apply?.(theme);
}
