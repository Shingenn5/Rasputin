import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  Bot,
  ChevronDown,
  Cpu,
  Folder,
  Pause,
  PanelLeftOpen,
  Play,
  Send,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  Square,
  Users,
  X,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import rehypeSanitize from "rehype-sanitize";
import {
  displayModelName,
  displayModelSecondary,
  displayWorkspaceName,
  labelize,
  modelHealthLine,
  runtimeStatus,
} from "../../lib/display.js";
import { actionRegistry, useReliableAction } from "../../lib/actionRegistry.js";

const modeOptions = [
  {
    value: "chat",
    label: "Chat",
    role: "main",
    description: "General conversation and local problem solving.",
    permission: "Uses the active workspace only when a task needs it.",
  },
  {
    value: "analyze",
    label: "Analyze",
    role: "executor",
    description: "Inspect mounted files, summarize structure, and compare evidence.",
    permission: "Read-only unless you approve a later mutation.",
  },
  {
    value: "research",
    label: "Research",
    role: "researcher",
    description: "Brokered research workflows with approval-gated web tools.",
    permission: "Models stay offline; only approved tools can reach out.",
  },
  {
    value: "code",
    label: "Code",
    role: "coder",
    description: "Repo analysis, patch planning, test guidance, and coding tasks.",
    permission: "Writes and shell execution remain approval-gated.",
  },
  {
    value: "write",
    label: "Write",
    role: "summarizer",
    description: "Draft Markdown, notes, summaries, and document outlines.",
    permission: "Exports only go to approved output folders.",
  },
  {
    value: "organize",
    label: "Organize",
    role: "executor",
    description: "Plan folder cleanup and file organization from mounted roots.",
    permission: "Folder changes require preview and approval.",
  },
  {
    value: "review",
    label: "Review",
    role: "summarizer",
    description: "Check prior output, summarize risk, and prepare follow-up edits.",
    permission: "Review uses local task history and approved workspace evidence.",
  },
];

export function HomeView(props) {
  const {
    activeWorkspaceName,
    view,
    selectedModel,
    selectedModelObject,
    models,
    visibleModels,
    setSelectedModel,
    security,
    go,
    toggleSidebar,
    homeTasks,
    objective,
    setObjective,
    sendTask,
    healthy,
    composerStatus,
    cancelTask,
    pauseTask,
    resumeTask,
    approvalCount,
    taskMode,
    setTaskMode,
    modeModelOverrides,
    setModeModelOverride,
    modelKeyForMode,
    subagentCount,
    setSubagentCount,
    runningTasks,
    openTaskDetails,
    setPrompt,
  } = props;

  const threadScrollRef = useRef(null);
  const modeButtonRef = useRef(null);
  const modePanelRef = useRef(null);
  const modelButtonRef = useRef(null);
  const modelPanelRef = useRef(null);
  const previousThreadVersionRef = useRef("");
  const [autoScroll, setAutoScroll] = useState(true);
  const [hasNewActivity, setHasNewActivity] = useState(false);
  const [modePanelOpen, setModePanelOpen] = useState(false);
  const [modelPanelOpen, setModelPanelOpen] = useState(false);
  const [activeCommandWorkspace, setActiveCommandWorkspace] = useState("General");

  // Phase 10: Button Reliability Framework State
  const [uiState, setUiState] = useState({ status: 'idle', message: '' });
  const executeAction = useReliableAction("HomeView");

  const handleSendTask = async (e) => {
    e.preventDefault();
    if (!objective.trim()) return;
    try {
      await executeAction("SendTask", taskMode, async () => {
        await sendTask(e);
      }, setUiState);
    } catch (error) {
      console.error(error);
    }
  };

  const handleCancelTask = (id) => executeAction("CancelTask", id, async () => cancelTask(id), setUiState);
  const handlePauseTask = (id) => executeAction("PauseTask", id, async () => pauseTask(id), setUiState);
  const handleResumeTask = (id) => executeAction("ResumeTask", id, async () => resumeTask(id), setUiState);

  function selectCommandWorkspace(ws) {
    setActiveCommandWorkspace(ws);
    if (ws === "Research") setTaskMode("research");
    if (ws === "Documents") setTaskMode("analyze");
    if (ws === "Coding") setTaskMode("code");
    if (ws === "General") setTaskMode("chat");
  }

  let objectivePlaceholder = "Message Rasputin...";
  if (activeCommandWorkspace === "Research") objectivePlaceholder = "What are we researching?";
  if (activeCommandWorkspace === "Documents") objectivePlaceholder = "Ask about your documents or draft new ones...";
  if (activeCommandWorkspace === "Coding") objectivePlaceholder = "Describe the coding task...";
  const orderedHomeTasks = useMemo(
    () => [...homeTasks].sort((a, b) => Number(a.createdAt || 0) - Number(b.createdAt || 0)),
    [homeTasks],
  );
  const threadVersion = useMemo(
    () => orderedHomeTasks.map((task) => `${task.id}:${task.status}:${task.progress}:${String(task.result || "").length}`).join("|"),
    [orderedHomeTasks],
  );
  const activeHomeTasks = orderedHomeTasks.filter((task) => ["queued", "running", "paused"].includes(task.status));
  const latestActiveTask = activeHomeTasks[activeHomeTasks.length - 1] || runningTasks?.[0];
  const privacyTitle = security.privacyLock ? "Local-only" : "Review mode";
  const privacyDetail = security.privacyLock ? "Models offline" : "Safety relaxed";
  const selectedModelHealthLine = modelHealthLine(selectedModelObject, models);
  const disabledReason = healthy ? "" : `${selectedModelHealthLine} Use Models to test or repair the local runtime, or enable Testing Mode.`;
  const activeMode = modeOptions.find((mode) => mode.value === taskMode) || modeOptions[0];
  const laneSummaries = useMemo(() => {
    const taskMap = new Map();
    [...orderedHomeTasks, ...(runningTasks || [])].forEach((task) => {
      if (task?.id && !taskMap.has(task.id)) taskMap.set(task.id, task);
    });
    const allTasks = [...taskMap.values()];
    return modeOptions.map((mode) => {
      const routedKey = modelKeyForMode?.(mode.value, modeModelOverrides) || selectedModel;
      const routed = models.find((model) => model.key === routedKey) || models.find((model) => model.role === mode.role) || selectedModelObject;
      const modeTasks = allTasks
        .filter((task) => (task.mode || "chat") === mode.value)
        .sort((left, right) => Number(right.createdAt || 0) - Number(left.createdAt || 0));
      const activeRun = modeTasks.find((task) => ["queued", "running", "paused"].includes(task.status));
      const recent = modeTasks[0];
      return {
        ...mode,
        modelName: routed ? displayModelName(routed, models) : "No routed model",
        workspaceName: activeWorkspaceName || "No workspace selected",
        statusLabel: activeRun ? labelize(activeRun.status || "running") : "Ready",
        recentTitle: recent?.objective || "",
        isRunning: Boolean(activeRun),
      };
    });
  }, [activeWorkspaceName, modelKeyForMode, modeModelOverrides, models, orderedHomeTasks, runningTasks, selectedModel, selectedModelObject]);

  useEffect(() => {
    if (view !== "home" || !threadScrollRef.current) return;
    const target = threadScrollRef.current;
    if (autoScroll) {
      window.requestAnimationFrame(() => {
        target.scrollTop = target.scrollHeight;
      });
    } else if (previousThreadVersionRef.current && previousThreadVersionRef.current !== threadVersion) {
      setHasNewActivity(true);
    }
    previousThreadVersionRef.current = threadVersion;
  }, [threadVersion, view, autoScroll]);

  useEffect(() => {
    if (!modePanelOpen) return undefined;
    const firstControl = modePanelRef.current?.querySelector("button, select, input");
    firstControl?.focus();
    function closeOnEscape(event) {
      if (event.key === "Escape") {
        setModePanelOpen(false);
        window.requestAnimationFrame(() => modeButtonRef.current?.focus());
      }
    }
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [modePanelOpen]);

  useEffect(() => {
    if (!modelPanelOpen) return undefined;
    const firstControl = modelPanelRef.current?.querySelector("button, select, input");
    firstControl?.focus();
    function closeOnEscape(event) {
      if (event.key === "Escape") {
        setModelPanelOpen(false);
        window.requestAnimationFrame(() => modelButtonRef.current?.focus());
      }
    }
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [modelPanelOpen]);

  function handleThreadScroll(event) {
    const target = event.currentTarget;
    const distanceFromBottom = target.scrollHeight - target.scrollTop - target.clientHeight;
    const atBottom = distanceFromBottom < 84;
    setAutoScroll(atBottom);
    if (atBottom) setHasNewActivity(false);
  }

function jumpToLatest() {
    const target = threadScrollRef.current;
    if (!target) return;
    target.scrollTo({ top: target.scrollHeight, behavior: "smooth" });
    setAutoScroll(true);
    setHasNewActivity(false);
  }

  return (
    <section className={`cc-layout app-view home-view ${view === "home" ? "active" : ""}`} id="homeView" data-app-view="home" tabIndex="-1">
      {/* Header */}
      <header className="cc-header">
        <div className="cc-header-left">
          <button className="icon-button" type="button" aria-label="Open navigation" onClick={toggleSidebar}>
            <PanelLeftOpen size={19} />
          </button>
          <div className="cc-logo">
            <span className="brand-mark" aria-hidden="true">R</span>
            Rasputin
          </div>
        </div>
        <div className="cc-status-area">
          <div className="cc-status-item">
            <Cpu size={14} /> <span>{displayModelName(selectedModelObject, models)}</span>
          </div>
          <div className="cc-status-item" title={`${privacyTitle}: ${privacyDetail}`}>
            <ShieldCheck size={14} /> <span>{privacyTitle}</span>
          </div>
          <button className="icon-button" type="button" aria-label="Open settings" onClick={() => go("settings", "general")}>
            <Settings size={18} />
          </button>
        </div>
      </header>

      <div className="cc-main-container">
        {/* Content Area */}
        <div className="cc-content-area">
          {/* Workspace Selector */}
          <div className="cc-workspace-selector">
            <div className={`cc-workspace-card ${activeCommandWorkspace === "Research" ? "is-active" : ""}`} onClick={() => selectCommandWorkspace("Research")}>Research</div>
            <div className={`cc-workspace-card ${activeCommandWorkspace === "Documents" ? "is-active" : ""}`} onClick={() => selectCommandWorkspace("Documents")}>Documents</div>
            <div className={`cc-workspace-card ${activeCommandWorkspace === "Coding" ? "is-active" : ""}`} onClick={() => selectCommandWorkspace("Coding")}>Coding</div>
            <div className={`cc-workspace-card ${activeCommandWorkspace === "General" ? "is-active" : ""}`} onClick={() => selectCommandWorkspace("General")}>General</div>
          </div>

          {/* Quick Action Center */}
          <div className="cc-quick-action-center">
            <h1 className="cc-objective-title">What is our objective?</h1>
            
            <form id="taskForm" className="cc-input-container" onSubmit={handleSendTask}>
              <label className="visually-hidden" htmlFor="objective">Message Rasputin</label>
              <textarea
                id="objective"
                className="cc-input"
                rows={3}
                placeholder={objectivePlaceholder}
                value={objective}
                onChange={(event) => setObjective(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    event.currentTarget.form.requestSubmit();
                  }
                }}
              />
              <div className="cc-input-actions">
                <div className="cc-quick-actions">
                  {activeCommandWorkspace === "Research" && (
                    <>
                      <button type="button" className="w2-button w2-button-outline" onClick={() => setPrompt?.("Deep dive a topic", "research")}>Deep dive a topic</button>
                      <button type="button" className="w2-button w2-button-outline" onClick={() => setPrompt?.("Find latest references", "research")}>Find latest references</button>
                    </>
                  )}
                  {activeCommandWorkspace === "Documents" && (
                    <>
                      <button type="button" className="w2-button w2-button-outline" onClick={() => setPrompt?.("Summarize active workspace", "analyze")}>Summarize active workspace</button>
                      <button type="button" className="w2-button w2-button-outline" onClick={() => setPrompt?.("Organize files", "organize")}>Organize files</button>
                    </>
                  )}
                  {activeCommandWorkspace === "Coding" && (
                    <>
                      <button type="button" className="w2-button w2-button-outline" onClick={() => setPrompt?.("Review code", "code")}>Review code</button>
                      <button type="button" className="w2-button w2-button-outline" onClick={() => setPrompt?.("Plan next feature", "code")}>Plan next feature</button>
                      <button type="button" className="w2-button w2-button-outline" onClick={() => setPrompt?.("Find bugs", "code")}>Find bugs</button>
                    </>
                  )}
                  {activeCommandWorkspace === "General" && (
                    <>
                      <button type="button" className="w2-button w2-button-outline" onClick={() => setPrompt?.("General chat", "chat")}>General chat</button>
                      <button type="button" className="w2-button w2-button-outline" onClick={() => setPrompt?.("Brainstorm ideas", "chat")}>Brainstorm ideas</button>
                    </>
                  )}
                </div>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                  {/* Button Reliability Status Readout */}
                  {uiState.status !== 'idle' && (
                    <div style={{ 
                      padding: '4px 8px', borderRadius: '4px', fontSize: '0.75rem',
                      backgroundColor: uiState.status === 'failed' ? 'var(--ras-danger)' : 
                                      uiState.status === 'success' ? 'var(--ras-safe)' : 'var(--cc-surface)',
                      color: '#fff', display: 'flex', alignItems: 'center'
                    }}>
                      {uiState.message}
                    </div>
                  )}
                  {latestActiveTask && (
                    <button className="cc-quick-action-chip" style={{ borderColor: 'var(--ras-danger)', color: 'var(--ras-danger)' }} type="button" onClick={() => handleCancelTask(latestActiveTask.id)}>
                      <Square size={14} style={{ marginRight: '4px', verticalAlign: 'middle' }} />
                      Stop latest
                    </button>
                  )}
                  <button
                    id="sendBtn"
                    className="w2-button w2-button-primary"
                    style={{ padding: '6px 16px' }}
                    type="submit"
                    disabled={!healthy}
                    aria-disabled={!healthy}
                    aria-label="Send message"
                    title={disabledReason || "Send message"}
                  >
                    <Send size={14} style={{ marginRight: '4px', verticalAlign: 'middle' }} /> Send
                  </button>
                </div>
              </div>

              {/* Render panels if open */}
              {modePanelOpen && (
                <ModeSidePanel
                  panelRef={modePanelRef}
                  modes={modeOptions}
                  activeMode={taskMode}
                  models={models}
                  visibleModels={visibleModels}
                  modeModelOverrides={modeModelOverrides || {}}
                  setModeModelOverride={setModeModelOverride}
                  modelKeyForMode={modelKeyForMode}
                  setTaskMode={(nextMode) => {
                    setTaskMode(nextMode);
                    setModePanelOpen(false);
                    window.requestAnimationFrame(() => modeButtonRef.current?.focus());
                  }}
                  subagentCount={subagentCount}
                  setSubagentCount={setSubagentCount}
                  close={() => {
                    setModePanelOpen(false);
                    window.requestAnimationFrame(() => modeButtonRef.current?.focus());
                  }}
                />
              )}
              {modelPanelOpen && (
                <ModelSidePanel
                  panelRef={modelPanelRef}
                  models={models}
                  visibleModels={visibleModels}
                  selectedModel={selectedModel}
                  setSelectedModel={(key) => {
                    setSelectedModel(key);
                    setModelPanelOpen(false);
                    window.requestAnimationFrame(() => modelButtonRef.current?.focus());
                  }}
                  close={() => {
                    setModelPanelOpen(false);
                    window.requestAnimationFrame(() => modelButtonRef.current?.focus());
                  }}
                />
              )}
            </form>

            <div style={{ display: 'none' }}>
              <button ref={modeButtonRef} onClick={() => setModePanelOpen(true)}>Mode</button>
              <button ref={modelButtonRef} onClick={() => setModelPanelOpen(true)}>Model</button>
            </div>
          </div>
        </div>

        {/* Context Sidebar */}
        <aside className="cc-sidebar">
          <div className="cc-sidebar-section">
            <h3 className="cc-sidebar-section-title">Recent Activity</h3>
            <div className="thread-list" aria-live="polite" style={{ padding: 0 }} ref={threadScrollRef}>
              {orderedHomeTasks.length === 0 && (
                <div className="cc-sidebar-item">
                  <p>No recent activity in this chat.</p>
                </div>
              )}
              {orderedHomeTasks.map((task) => (
                <TaskThread
                  key={task.id}
                  task={task}
                  models={models}
                  cancelTask={handleCancelTask}
                  pauseTask={handlePauseTask}
                  resumeTask={handleResumeTask}
                  openTaskDetails={openTaskDetails}
                />
              ))}
            </div>
          </div>

          <div className="cc-sidebar-section">
            <h3 className="cc-sidebar-section-title">Active Knowledge</h3>
            {activeCommandWorkspace === "Research" ? (
              <>
                <div className="cc-sidebar-item">
                  <h4>Graph Status</h4>
                  <p>Knowledge graph active and indexing...</p>
                </div>
                <div className="cc-sidebar-item">
                  <h4>Web Access</h4>
                  <p>Enabled for deep research tasks.</p>
                </div>
              </>
            ) : activeCommandWorkspace === "Documents" ? (
              <>
                <div className="cc-sidebar-item">
                  <h4>Mounted Workspace</h4>
                  <p>{activeWorkspaceName || "No workspace selected"}</p>
                </div>
                <div className="cc-sidebar-item">
                  <h4>Document Index</h4>
                  <p>Ready for summarization.</p>
                </div>
              </>
            ) : activeCommandWorkspace === "Coding" ? (
              <>
                <div className="cc-sidebar-item">
                  <h4>Target Repository</h4>
                  <p>{activeWorkspaceName || "None"}</p>
                </div>
                <div className="cc-sidebar-item">
                  <h4>Code Tools</h4>
                  <p>Read/Write enabled.</p>
                </div>
              </>
            ) : (
              <>
                <div className="cc-sidebar-item">
                  <h4>Current Mode</h4>
                  <p>General Chat</p>
                </div>
                <div className="cc-sidebar-item">
                  <h4>Local Context</h4>
                  <p>{activeWorkspaceName || "None"}</p>
                </div>
              </>
            )}
          </div>
        </aside>
      </div>
    </section>
  );
}

function AgentLaneStrip({ lanes, activeMode, setTaskMode }) {
  const activeLane = lanes.find((lane) => lane.value === activeMode) || lanes[0];

  function handleKeyDown(event) {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const currentIndex = lanes.findIndex((lane) => lane.value === activeMode);
    let nextIndex = currentIndex;
    if (event.key === "Home") nextIndex = 0;
    if (event.key === "End") nextIndex = lanes.length - 1;
    if (event.key === "ArrowRight") nextIndex = (currentIndex + 1 + lanes.length) % lanes.length;
    if (event.key === "ArrowLeft") nextIndex = (currentIndex - 1 + lanes.length) % lanes.length;
    const nextLane = lanes[nextIndex];
    if (!nextLane) return;
    setTaskMode(nextLane.value);
    window.requestAnimationFrame(() => {
      document.getElementById(`agent-lane-tab-${nextLane.value}`)?.focus();
    });
  }

  if (!lanes.length) return null;

  return (
    <section className="agent-lane-shell" data-testid="agent-lanes" aria-label="Agent lanes">
      <div className="agent-lane-head">
        <span className="eyebrow">Agent lanes</span>
        <span>{activeLane.label} lane selected</span>
      </div>
      <div className="agent-lane-tabs" role="tablist" aria-label="Choose active AI lane" onKeyDown={handleKeyDown}>
        {lanes.map((lane) => {
          const selected = lane.value === activeMode;
          return (
            <button
              key={lane.value}
              id={`agent-lane-tab-${lane.value}`}
              className={selected ? "agent-lane-tab is-active" : "agent-lane-tab"}
              data-testid="agent-lane"
              title={`${lane.label} lane`}
              type="button"
              role="tab"
              aria-selected={selected}
              aria-controls="agent-lane-current"
              tabIndex={selected ? 0 : -1}
              aria-label={`${lane.label}. ${lane.statusLabel}. Model ${lane.modelName}. Workspace ${lane.workspaceName}. ${lane.recentTitle ? `Recent task ${lane.recentTitle}.` : "No recent task."}`}
              onClick={() => setTaskMode(lane.value)}
            >
              <strong>{lane.label}</strong>
              <span>{lane.modelName}</span>
              <em className={lane.isRunning ? "is-running" : ""}>{lane.statusLabel}</em>
            </button>
          );
        })}
      </div>
      <div
        id="agent-lane-current"
        className="agent-lane-current"
        role="tabpanel"
        aria-labelledby={`agent-lane-tab-${activeLane.value}`}
        data-testid="active-agent-lane"
      >
        <dl>
          <div>
            <dt>Mode</dt>
            <dd>{activeLane.label}</dd>
          </div>
          <div>
            <dt>Model</dt>
            <dd>{activeLane.modelName}</dd>
          </div>
          <div>
            <dt>Workspace</dt>
            <dd>{activeLane.workspaceName}</dd>
          </div>
          <div>
            <dt>Recent</dt>
            <dd>{activeLane.recentTitle || "No recent task"}</dd>
          </div>
        </dl>
      </div>
    </section>
  );
}

function ModelSidePanel({ panelRef, models, visibleModels, selectedModel, setSelectedModel, close }) {
  const items = visibleModels.length ? visibleModels : models;
  return (
    <aside
      ref={panelRef}
      className="model-side-panel"
      data-testid="model-side-panel"
      role="dialog"
      aria-modal="false"
      aria-labelledby="modelPanelTitle"
    >
      <header className="mode-panel-head">
        <div>
          <span className="eyebrow">Runtime routing</span>
          <h2 id="modelPanelTitle">Choose model</h2>
        </div>
        <button className="icon-button" type="button" aria-label="Close model panel" onClick={close}>
          <X size={18} />
        </button>
      </header>
      <div className="model-panel-list">
        {items.map((model) => {
          const selected = model.key === selectedModel;
          const status = runtimeStatus(model);
          return (
            <button
              key={model.key}
              type="button"
              className={selected ? "model-choice is-active" : "model-choice"}
              data-testid="model-option"
              aria-pressed={selected}
              onClick={() => setSelectedModel(model.key)}
            >
              <span className={`model-choice-status status-${status}`} aria-hidden="true" />
              <span>
                <strong>{displayModelName(model, models)}</strong>
                <small>{displayModelSecondary(model, models) || model.key}</small>
              </span>
              <em>{status}</em>
            </button>
          );
        })}
      </div>
      <footer className="model-panel-footer">
        <p>Only user-facing chat models appear here. Embeddings and raw registry entries stay in Models settings.</p>
      </footer>
    </aside>
  );
}

function ModeSidePanel({
  panelRef,
  modes,
  activeMode,
  models,
  visibleModels,
  modeModelOverrides,
  setModeModelOverride,
  modelKeyForMode,
  setTaskMode,
  subagentCount,
  setSubagentCount,
  close,
}) {
  function modelForMode(mode) {
    const key = modelKeyForMode?.(mode.value, modeModelOverrides);
    return models.find((model) => model.key === key) || models.find((model) => model.role === mode.role) || null;
  }

  return (
    <aside
      ref={panelRef}
      className="mode-side-panel"
      data-testid="mode-side-panel"
      role="dialog"
      aria-modal="false"
      aria-labelledby="modePanelTitle"
    >
      <header className="mode-panel-head">
        <div>
          <span className="eyebrow">Task routing</span>
          <h2 id="modePanelTitle">Choose mode</h2>
        </div>
        <button className="icon-button" type="button" aria-label="Close mode panel" onClick={close}>
          <X size={18} />
        </button>
      </header>

      <div className="mode-panel-list">
        {modes.map((mode) => {
          const routed = modelForMode(mode);
          const override = modeModelOverrides?.[mode.value] || "";
          return (
            <article className={activeMode === mode.value ? "mode-card is-active" : "mode-card"} key={mode.value} data-testid="mode-option">
              <button type="button" className="mode-card-main" aria-pressed={activeMode === mode.value} onClick={() => setTaskMode(mode.value)}>
                <Bot size={18} aria-hidden="true" />
                <span>
                  <strong>{mode.label}</strong>
                  <small>{mode.description}</small>
                </span>
              </button>
              <dl className="mode-route-grid">
                <dt>Role</dt>
                <dd>{labelize(mode.role)}</dd>
                <dt>Model</dt>
                <dd>{routed ? displayModelName(routed, models) : "No routed model"}</dd>
                {routed && displayModelSecondary(routed, models) && (
                  <>
                    <dt>Registry</dt>
                    <dd>{displayModelSecondary(routed, models)}</dd>
                  </>
                )}
              </dl>
              <label className="mode-model-override">
                <span>Override model</span>
                <select
                  value={override}
                  aria-label={`${mode.label} model override`}
                  onChange={(event) => setModeModelOverride(mode.value, event.target.value)}
                >
                  <option value="">Use {labelize(mode.role)} route</option>
                  {visibleModels.map((model) => (
                    <option key={model.key} value={model.key}>{displayModelName(model, models)}</option>
                  ))}
                </select>
              </label>
              <p>{mode.permission}</p>
            </article>
          );
        })}
      </div>

      <section className="mode-subagent-panel" aria-label="Parallel sub-agent controls">
        <div>
          <h3>Parallel sub-agents</h3>
          <p>Use these for larger non-chat jobs. Normal chat messages can already run at the same time.</p>
        </div>
        <label>
          <span>Count</span>
          <input
            type="number"
            min="0"
            max="4"
            value={subagentCount}
            onChange={(event) => setSubagentCount(Math.max(0, Math.min(Number(event.target.value || 0), 4)))}
          />
        </label>
      </section>
    </aside>
  );
}

function TaskThread({ task, models, cancelTask, pauseTask, resumeTask, openTaskDetails }) {
  const response = task.result || task.logs?.slice(-4).join("\n") || "Working...";
  const status = task.status || "queued";
  const active = ["queued", "running", "paused"].includes(status);
  return (
    <article className="thread-item">
      <div className="message user-message">
        <div className="message-label">You</div>
        <div className="message-body user-bubble">{task.objective}</div>
      </div>
      <div className="message assistant-message">
        <div className="message-label assistant-label">
          <span>Rasputin</span>
          <span className={`status-pill status-${status}`}>{status}</span>
          {active && (
            <span className="status-pill status-running">{Number(task.progress || 0)}%</span>
          )}
        </div>
        <div className="markdown-body">
          <ReactMarkdown rehypePlugins={[rehypeSanitize]}>{response}</ReactMarkdown>
        </div>
        <details className="runtime-details" data-testid="runtime-details-toggle">
          <summary>Details</summary>
          <dl className="detail-grid">
            <dt>Model</dt><dd>{displayModelName(task.model, models)}</dd>
            <dt>Mode</dt><dd>{task.mode || "chat"}</dd>
            <dt>Workspace</dt><dd>{displayWorkspaceName(task.workspace)}</dd>
            <dt>Status</dt><dd>{status}</dd>
          </dl>
          <div className="task-inline-actions" aria-label="Task details">
            <button type="button" className="tiny-action" data-testid="activity-task-details" onClick={() => openTaskDetails(task.id)}>
              Open details
            </button>
          </div>
          {active && (
            <div className="task-inline-actions" aria-label="Task controls">
              {status === "paused" ? (
                <button type="button" className="tiny-action" onClick={() => resumeTask(task.id)}>
                  <Play size={13} />
                  Resume
                </button>
              ) : (
                <button type="button" className="tiny-action" onClick={() => pauseTask(task.id)}>
                  <Pause size={13} />
                  Pause
                </button>
              )}
              <button type="button" className="tiny-action danger" onClick={() => cancelTask(task.id)}>
                <Square size={13} />
                Stop
              </button>
            </div>
          )}
        </details>
      </div>
    </article>
  );
}
