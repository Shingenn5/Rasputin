import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AppShell } from "../components/AppShell.jsx";
import { api, postJson } from "../api/client.js";
import { LoginShell } from "../features/auth/LoginShell.jsx";
import { HomeView } from "../features/chat/HomeView.jsx";
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
  WarsatView,
} from "../features/runtime/RuntimeViews.jsx";
import { readStoredFlag, useLocalStorageFlag } from "../hooks/useLocalStorageFlag.js";
import {
  displayModelName,
  displayWorkspaceName,
  isModelHealthy,
  isUserFacingModel,
} from "../lib/display.js";

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
  const [theme, setTheme] = useState(() => localStorage.getItem("rasputin-theme") || "rasputin-light");
  const [models, setModels] = useState([]);
  const [selectedModel, setSelectedModel] = useState("main-vllm");
  const [testingMode, setTestingMode] = useState(false);
  const [taskMode, setTaskMode] = useState("chat");
  const [subagentCount, setSubagentCount] = useState(0);
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
  const [mountPlan, setMountPlan] = useState(null);
  const [security, setSecurity] = useState({});
  const [auditEvents, setAuditEvents] = useState([]);
  const [ragStats, setRagStats] = useState(null);
  const [graphStats, setGraphStats] = useState(null);
  const [output, setOutput] = useState(null);
  const [sessions, setSessions] = useState({ sessions: [] });
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
  const [globalStatus, setGlobalStatus] = useState("");
  const eventSourceRef = useRef(null);
  const selectedTaskIdRef = useRef(null);
  const taskDetailsReturnRef = useRef(null);
  const authenticated = !!session?.authenticated && !loginVisible;

  const selectedModelObject = useMemo(
    () => models.find((model) => model.key === selectedModel) || models.find((model) => model.role === "main") || models[0],
    [models, selectedModel],
  );

  const visibleModels = useMemo(() => {
    const shown = models.filter((model) => isUserFacingModel(model, testingMode));
    return shown.length ? shown : models.filter((model) => model.key !== "local-embeddings");
  }, [models, testingMode]);

  const activeWorkspaceName = workspace.activeName || displayWorkspaceName(workspace.activePath);
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
    document.documentElement.dataset.theme = theme;
    document.documentElement.dataset.bsTheme = theme === "rasputin-dark" ? "dark" : "light";
    document.documentElement.dataset.contrast = theme === "contrast" ? "true" : "false";
    document.body.classList.toggle("sidebar-collapsed", sidebarCollapsed);
    document.body.classList.toggle("mobile-sidebar-open", mobileSidebarOpen);
    document.body.dataset.ready = ready ? "true" : "false";
    localStorage.setItem("rasputin-theme", theme);
    updateThemeChrome(theme);
  }, [theme, sidebarCollapsed, mobileSidebarOpen, ready]);

  useEffect(() => {
    if (!globalStatus) return undefined;
    const timer = window.setTimeout(() => setGlobalStatus(""), 5500);
    return () => window.clearTimeout(timer);
  }, [globalStatus]);

  useEffect(() => {
    boot();
    return () => eventSourceRef.current?.close();
  }, []);

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
        subagents: subagentCount,
        activeView: view,
        activeSettingsSection: settingsSection,
      }).catch(() => {});
    }, 450);
    return () => window.clearTimeout(timer);
  }, [theme, sidebarCollapsed, selectedModel, testingMode, taskMode, subagentCount, workspace.activePath, view, settingsSection, session, ready]);

  async function boot() {
    try {
      const authSession = await api("/api/auth/session");
      setSession(authSession);
      if (!authSession.authenticated) {
        setLoginVisible(true);
        setReady(true);
        return;
      }
      setLoginVisible(false);
      await loadBasics();
      connectEvents();
      setReady(true);
    } catch (error) {
      setLoginStatus(error.message);
      setReady(true);
    }
  }

  async function loadBasics() {
    const data = await api("/api/ui/bootstrap");
    const prefs = data.preferences || {};
    setModels(data.models || []);
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
    setApprovals(data.approvals || { approvals: [] });
    setMemoryReview(data.memoryReview || { items: [] });
    setSkillRegistry(data.skillRegistry || { skills: [] });
    setTelegramConfig(data.telegram || null);
    setSchedulesList(data.schedules || { schedules: [] });
    setWarsat(data.warsat || { protocols: [], count: 0, dockerControlEnabled: false, executionEnabled: false });
    const localTheme = localStorage.getItem("rasputin-theme");
    const localSidebarCollapsed = readStoredFlag("rasputin-sidebar-collapsed");
    setTheme(localTheme || prefs.theme || "rasputin-light");
    setSidebarCollapsed(localSidebarCollapsed === null ? !!prefs.sidebarCollapsed : localSidebarCollapsed);
    setTestingMode(!!prefs.testingMode);
    setSelectedModel(prefs.selectedModel || "main-vllm");
    setTaskMode(prefs.taskMode || "chat");
    setSubagentCount(Math.max(0, Math.min(Number(prefs.subagents || 0), 4)));
    setView(prefs.activeView || "home");
    setSettingsSection(prefs.activeSettingsSection || "general");
    await loadWorkspaceRoots(data.workspace?.activePath || ".");
  }

  async function loadModels() {
    const nextModels = await queryClient.fetchQuery({ queryKey: ["model-registry"], queryFn: fetchModels });
    setModels(nextModels);
    return nextModels;
  }

  async function loadTasks() {
    const nextTasks = await queryClient.fetchQuery({ queryKey: ["tasks"], queryFn: () => api("/api/tasks") });
    setTasks(nextTasks);
    return nextTasks;
  }

  async function loadAuditEvents() {
    const nextEvents = await queryClient.fetchQuery({ queryKey: ["audit-events"], queryFn: fetchAuditEvents });
    setAuditEvents(nextEvents);
    return nextEvents;
  }

  async function loadWorkspaceRoots(activePath = workspace.activePath || ".") {
    const rootsPayload = await api("/api/workspace/roots");
    const roots = rootsPayload.roots || [];
    setWorkspaceRoots(roots);
    const preferred = roots.find((root) => root.path === activePath) || roots[0];
    if (preferred) {
      const browsed = await postJson("/api/workspace/browse", { rootId: preferred.id });
      setWorkspaceBrowse(browsed);
    }
  }

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
          if (selectedTaskIdRef.current) {
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

  function go(nextView, section) {
    setView(nextView);
    if (section) setSettingsSection(section);
    if (nextView === "workspaces") {
      loadWorkspaceRoots().catch((error) => setGlobalStatus(error.message));
    }
    if (["activity", "agents", "sessions", "approvals", "memory", "skills", "telegram", "schedules"].includes(nextView)) {
      loadRuntimeData().catch((error) => setGlobalStatus(error.message));
    }
    if (nextView === "warsat") {
      loadWarsat().catch((error) => setGlobalStatus(error.message));
    }
    setMobileSidebarOpen(false);
  }

  function toggleSidebar() {
    if (window.matchMedia("(max-width: 760px)").matches) {
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

  async function sendTask(event) {
    event.preventDefault();
    if (!healthy) {
      setComposerStatus("Select Testing Mode or test a healthy local model before sending.");
      return;
    }
    if (!objective.trim()) {
      setComposerStatus("Write a message first.");
      return;
    }
    try {
      setComposerStatus("");
      const task = await postJson("/api/tasks", {
        objective: objective.trim(),
        model: selectedModel,
        skill: "general",
        mode: taskMode,
        subagents: subagentCount,
        workspacePath: workspace.activePath || ".",
        sessionId: activeChatSessionId || undefined,
      });
      setTasks((current) => [task, ...current.filter((item) => item.id !== task.id)]);
      queryClient.setQueryData(["tasks"], (current = []) => [task, ...current.filter((item) => item.id !== task.id)]);
      setHomeTaskIds((current) => new Set([...current, task.id]));
      setActiveChatSessionId(task.sessionId || activeChatSessionId);
      setObjective("");
      setGlobalStatus(subagentCount ? `Agent run started with ${subagentCount} sub-agent${subagentCount === 1 ? "" : "s"}.` : "Task started.");
    } catch (error) {
      setComposerStatus(error.message);
    }
  }

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

  async function saveSafety(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const keys = [
      "privacyLock", "allowFileRead", "allowFileWrite", "allowFileReorganize", "allowShellExecution",
      "allowWebSearch", "allowDockerControl", "allowModelTests", "allowModelRegistryEdit", "allowRemoteModels",
      "approvalRequiredFileWrite", "approvalRequiredFileMove", "approvalRequiredWebSearch", "auditEnabled",
    ];
    const payload = Object.fromEntries(keys.map((key) => [key, form.get(key) === "on"]));
    payload.webSearchMaxChars = Number(form.get("webSearchMaxChars") || 180);
    setSecurity(await postJson("/api/security", payload));
    setGlobalStatus("Safety settings saved.");
  }

  async function loadRuntimeData() {
    const [nextSessions, nextApprovals, nextMemoryReview, nextSkills, nextTelegram, nextSchedules] = await Promise.all([
      api("/api/sessions"),
      api("/api/approvals"),
      api("/api/memory/review"),
      api("/api/skills"),
      api("/api/integrations/telegram"),
      api("/api/schedules"),
    ]);
    setSessions(nextSessions);
    setApprovals(nextApprovals);
    setMemoryReview(nextMemoryReview);
    setSkillRegistry(nextSkills);
    setTelegramConfig(nextTelegram);
    setSchedulesList(nextSchedules);
  }

  async function loadSession(sessionId) {
    try {
      setSelectedSession(await api(`/api/sessions/${sessionId}`));
    } catch (error) {
      setGlobalStatus(error.message);
    }
  }

  async function refreshApprovals() {
    setApprovals(await api("/api/approvals"));
  }

  async function approveApproval(id) {
    await postJson(`/api/approvals/${id}/approve`, {});
    await refreshApprovals();
    if (selectedTaskIdRef.current) await loadTaskDetails(selectedTaskIdRef.current, { silent: true });
    setGlobalStatus("Approval accepted.");
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
    const nextWarsat = await api("/api/warsat/protocols");
    setWarsat(nextWarsat);
    return nextWarsat;
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
        hostPort: Number(form.get("hostPort") || 0) || undefined,
        role: form.get("role") || undefined,
        containerName: form.get("containerName") || undefined,
      });
      setWarsatPlan(plan);
      setGlobalStatus("Warsat launch plan created.");
      return plan;
    } catch (error) {
      setWarsatError(error.message);
      setWarsatPlan(null);
      return null;
    }
  }

  if (loginVisible) {
    return <LoginShell onSubmit={login} status={loginStatus} />;
  }

  return (
    <AppShell
      globalStatus={globalStatus}
      clearGlobalStatus={() => setGlobalStatus("")}
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
        newTask: () => {
          setHomeTaskIds(new Set());
          setActiveChatSessionId(null);
          setObjective("");
          setMobileSidebarOpen(false);
          go("home");
        },
      }}
    >
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
        setTaskMode={setTaskMode}
        subagentCount={subagentCount}
        setSubagentCount={setSubagentCount}
        runningTasks={runningTasks}
        openTaskDetails={openTaskDetails}
        setPrompt={(prompt, mode) => {
          setObjective(prompt);
          setTaskMode(mode === "analyze files" ? "analyze" : mode || "chat");
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
        approvePath={approvePath}
        selectWorkspace={selectWorkspace}
        loadWorkspaceRoots={() => loadWorkspaceRoots(workspace.activePath)}
        previewMount={previewMount}
        mountPlan={mountPlan}
      />
      <AgentsView view={view} tasks={tasks} models={models} />
      <SessionsView
        view={view}
        sessions={sessions}
        selectedSession={selectedSession}
        loadSession={loadSession}
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
        plan={warsatPlan}
        error={warsatError}
        createPlan={createWarsatPlan}
        clearPlan={() => {
          setWarsatPlan(null);
          setWarsatError("");
          setGlobalStatus("");
        }}
        refresh={loadWarsat}
      />
      <ActivityView
        view={view}
        tasks={tasks}
        models={models}
        refresh={loadTasks}
        approvals={approvals}
        sessions={sessions}
        auditEvents={auditEvents}
        go={go}
        cancelTask={cancelTask}
        pauseTask={pauseTask}
        resumeTask={resumeTask}
        openTaskDetails={openTaskDetails}
      />
      <SettingsView
        view={view}
        section={settingsSection}
        setSection={setSettingsSection}
        models={models}
        selectedModelObject={selectedModelObject}
        selectedModel={selectedModel}
        testingMode={testingMode}
        setTestingMode={setTestingMode}
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
        output={output}
        theme={theme}
        setTheme={setTheme}
        logout={logout}
        loadModels={loadModels}
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

function updateThemeChrome(theme) {
  const dark = theme === "rasputin-dark";
  const accent = theme === "contrast" ? "#005fcc" : dark ? "#d85b32" : "#bd4a28";
  const bg = theme === "contrast" ? "#ffffff" : dark ? "#090b0f" : "#d9d3c8";
  let meta = document.querySelector("meta[name='theme-color']");
  if (!meta) {
    meta = document.createElement("meta");
    meta.setAttribute("name", "theme-color");
    document.head.appendChild(meta);
  }
  meta.setAttribute("content", bg);

  let icon = document.querySelector("link[rel='icon']");
  if (!icon) {
    icon = document.createElement("link");
    icon.setAttribute("rel", "icon");
    document.head.appendChild(icon);
  }
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" fill="${bg}"/><path d="M14 32h36M32 14v36M20 20l24 24M44 20 20 44" stroke="${accent}" stroke-width="3" stroke-linecap="round" opacity=".72"/><circle cx="32" cy="32" r="11" fill="none" stroke="${accent}" stroke-width="4"/><text x="32" y="37" text-anchor="middle" font-family="Arial,sans-serif" font-size="15" font-weight="700" fill="${accent}">R</text></svg>`;
  icon.setAttribute("href", `data:image/svg+xml,${encodeURIComponent(svg)}`);
}
