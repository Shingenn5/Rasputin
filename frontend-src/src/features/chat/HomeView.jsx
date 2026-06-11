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
    <section className={`app-view home-view ${view === "home" ? "active" : ""}`} id="homeView" data-app-view="home" tabIndex="-1">
      <header className="home-commandbar">
        <button className="icon-button home-menu-button" type="button" aria-label="Open navigation" onClick={toggleSidebar}>
          <PanelLeftOpen size={19} />
        </button>
        <div className="home-title">
          <span className="system-label">Rasputin</span>
          <span className="system-subtitle">Local companion</span>
        </div>
        <div className="home-runtime-strip" aria-label="Runtime state">
          <button
            id="workspacePill"
            className="runtime-chip"
            data-testid="active-workspace-chip"
            type="button"
            onClick={() => go("workspaces")}
          >
            <Folder size={15} />
            <span>{activeWorkspaceName || "No workspace selected"}</span>
          </button>
          <button
            className={`runtime-chip privacy-chip ${security.privacyLock ? "is-safe" : "is-warn"}`}
            type="button"
            onClick={() => go("settings", "safety")}
            aria-label={`${privacyTitle}: ${privacyDetail}. Open safety settings.`}
            title={`${privacyTitle}: ${privacyDetail}`}
          >
            <ShieldCheck size={15} />
            <span>
              <strong>{privacyTitle}</strong>
              <small>{privacyDetail}</small>
            </span>
          </button>
          <button className="icon-button" type="button" aria-label="Open settings" onClick={() => go("settings", "general")}>
            <Settings size={18} />
          </button>
        </div>
      </header>

      <section className="chat-shell" aria-label="Conversation">
        <div className="thread-scroll" ref={threadScrollRef} onScroll={handleThreadScroll}>
          <section
            className={orderedHomeTasks.length ? "welcome-panel hidden" : "welcome-panel"}
            id="welcomePanel"
            aria-label="Start a task"
            data-testid="home-empty-state"
          >
            <div className="warmind-sigil" aria-hidden="true">
              <span />
            </div>
            <h1>What are we working on?</h1>
            <p>Ask a question, inspect an approved folder, or draft the next move.</p>
            <div className="prompt-strip" aria-label="Quick actions">
              <button type="button" className="prompt-chip" onClick={() => setPrompt?.("Inspect the active workspace and summarize the files you can see.", "analyze")}>
                Inspect workspace
              </button>
              <button type="button" className="prompt-chip" onClick={() => go("workspaces")}>
                Add folder
              </button>
              <button type="button" className="prompt-chip" onClick={() => setPrompt?.("Help me plan the next coding task for this project.", "code")}>
                Plan coding work
              </button>
              <button type="button" className="prompt-chip" onClick={() => setPrompt?.("Draft a clean markdown document I can export later.", "write")}>
                Draft document
              </button>
            </div>
          </section>

          <div id="tasks" className="thread-list" aria-live="polite">
            {activeHomeTasks.length > 1 && (
              <div className="parallel-run-strip" role="status" aria-live="polite">
                <Users size={16} />
                <span>{activeHomeTasks.length} active runs in this chat. They will continue in parallel.</span>
                <button type="button" onClick={() => go("activity")}>Open Activity</button>
              </div>
            )}
            {orderedHomeTasks.map((task) => (
              <TaskThread
                key={task.id}
                task={task}
                models={models}
                cancelTask={cancelTask}
                pauseTask={pauseTask}
                resumeTask={resumeTask}
                openTaskDetails={openTaskDetails}
              />
            ))}
          </div>
        </div>

        {hasNewActivity && (
          <button className="jump-latest-button" type="button" onClick={jumpToLatest}>
            Jump to latest
          </button>
        )}

        <form id="taskForm" className="chat-composer" data-testid="chat-composer" onSubmit={sendTask}>
          <div className="composer-chip-row">
            <div className="composer-context-actions" aria-label="Workspace actions">
              <button className="composer-link-button" type="button" onClick={() => go("workspaces")}>
                <Folder size={14} />
                Add folder
              </button>
              <button
                className="composer-link-button"
                type="button"
                onClick={() => setPrompt?.("Inspect the active workspace and summarize the files you can see.", "analyze")}
              >
                Inspect workspace
              </button>
            </div>
            {approvalCount > 0 && (
              <button className="runtime-chip is-warn" type="button" onClick={() => go("activity")}>
                {approvalCount} approval{approvalCount === 1 ? "" : "s"}
              </button>
            )}
            {(runningTasks?.length || 0) > 0 && (
              <button className="runtime-chip is-live" type="button" onClick={() => go("activity")}>
                <Users size={15} />
                {runningTasks.length} active run{runningTasks.length === 1 ? "" : "s"}
              </button>
            )}
          </div>

          {composerStatus && <p id="composerStatus" className="composer-status" role="alert">{composerStatus}</p>}

          <AgentLaneStrip lanes={laneSummaries} activeMode={activeMode.value} setTaskMode={setTaskMode} />

          <label className="visually-hidden" htmlFor="objective">Message Rasputin</label>
          <textarea
            id="objective"
            rows={3}
            placeholder="Message Rasputin"
            value={objective}
            aria-describedby="selectedModelHealth"
            onChange={(event) => setObjective(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                event.currentTarget.form.requestSubmit();
              }
            }}
          />

          <div className="composer-runbar" aria-label="Run settings">
            <button
              ref={modeButtonRef}
              type="button"
              className="mode-trigger"
              data-testid="chat-mode-chip"
              aria-haspopup="dialog"
              aria-expanded={modePanelOpen}
              onClick={() => setModePanelOpen(true)}
            >
              <SlidersHorizontal size={16} aria-hidden="true" />
              <span className="run-trigger-copy">
                <small>Mode</small>
                <strong>{activeMode.label}</strong>
                <em>{labelize(activeMode.role)} route</em>
              </span>
              <ChevronDown size={15} aria-hidden="true" />
            </button>

            <button
              ref={modelButtonRef}
              id="model"
              className="model-trigger"
              data-testid="active-model-chip"
              type="button"
              aria-haspopup="dialog"
              aria-expanded={modelPanelOpen}
              aria-label={`Active model: ${displayModelName(selectedModelObject, models)}. Open model selector.`}
              onClick={() => setModelPanelOpen(true)}
            >
              <Cpu size={16} aria-hidden="true" />
              <span className="run-trigger-copy">
                <small>Model</small>
                <strong>{displayModelName(selectedModelObject, models)}</strong>
                <em>{runtimeStatus(selectedModelObject)}</em>
              </span>
              <ChevronDown size={15} aria-hidden="true" />
            </button>
          </div>

          <div className="composer-meta">
            <p id="selectedModelHealth" className={`model-health ${healthy ? "is-healthy" : "is-unhealthy"}`}>
              {disabledReason || selectedModelHealthLine}
            </p>
            <div className="composer-actions">
              {latestActiveTask && (
                <button className="secondary-action" type="button" onClick={() => cancelTask(latestActiveTask.id)}>
                  <Square size={14} />
                  Stop latest
                </button>
              )}
              <button
                id="sendBtn"
                className="send-button"
                type="submit"
                disabled={!healthy}
                aria-disabled={!healthy}
                aria-label="Send message"
                title={disabledReason || "Send message"}
              >
                <Send size={18} />
              </button>
            </div>
          </div>
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
      </section>
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
