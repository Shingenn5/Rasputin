import React, { useEffect, useMemo, useRef } from "react";
import { Cpu, Folder, Pause, PanelLeftOpen, Play, Send, Settings, ShieldCheck, SlidersHorizontal, Square, Users } from "lucide-react";
import ReactMarkdown from "react-markdown";
import rehypeSanitize from "rehype-sanitize";
import {
  displayModelName,
  displayWorkspaceName,
  modelHealthLine,
  runtimeStatus,
} from "../../lib/display.js";

const modeOptions = [
  ["chat", "Chat"],
  ["analyze", "Analyze"],
  ["research", "Research"],
  ["code", "Code"],
  ["write", "Write"],
  ["organize", "Organize"],
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
    subagentCount,
    setSubagentCount,
    runningTasks,
    openTaskDetails,
  } = props;

  const threadScrollRef = useRef(null);
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
  const privacyLabel = security.privacyLock ? "Privacy lock" : "Review mode";
  const disabledReason = healthy ? "" : "A healthy local model or Testing Mode is required before sending.";

  useEffect(() => {
    if (view !== "home" || !threadScrollRef.current) return;
    const target = threadScrollRef.current;
    window.requestAnimationFrame(() => {
      target.scrollTop = target.scrollHeight;
    });
  }, [threadVersion, view]);

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
          <span className={`runtime-chip ${security.privacyLock ? "is-safe" : "is-warn"}`}>
            <ShieldCheck size={15} />
            <span>{privacyLabel}</span>
          </span>
          <button className="icon-button" type="button" aria-label="Open settings" onClick={() => go("settings", "general")}>
            <Settings size={18} />
          </button>
        </div>
      </header>

      <section className="chat-shell" aria-label="Conversation">
        <div className="thread-scroll" ref={threadScrollRef}>
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

        <form id="taskForm" className="chat-composer" data-testid="chat-composer" onSubmit={sendTask}>
          <div className="composer-chip-row">
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
            <div className="mode-segment" role="radiogroup" aria-label="Task mode">
              <span className="mode-segment-label">
                <SlidersHorizontal size={15} aria-hidden="true" />
                Mode
              </span>
              {modeOptions.map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  className={taskMode === value ? "mode-option is-active" : "mode-option"}
                  aria-pressed={taskMode === value}
                  onClick={() => setTaskMode(value)}
                >
                  {label}
                </button>
              ))}
            </div>

            <label className="model-inline-select" data-testid="active-model-chip">
              <Cpu size={15} />
              <span>Model</span>
              <select
                id="model"
                aria-label="Active model"
                data-testid="model-select"
                value={selectedModel}
                onChange={(event) => setSelectedModel(event.target.value)}
              >
                {visibleModels.map((model) => (
                  <option key={model.key} value={model.key}>{displayModelName(model, models)} - {runtimeStatus(model)}</option>
                ))}
              </select>
            </label>

            <details className="parallel-agent-options">
              <summary>
                <Users size={15} aria-hidden="true" />
                Parallel agents
              </summary>
              <div className="parallel-agent-body">
                <label>
                  <span>Sub-agent count</span>
                  <input
                    type="number"
                    min="0"
                    max="4"
                    value={subagentCount}
                    aria-label="Sub-agent count"
                    onChange={(event) => setSubagentCount(Math.max(0, Math.min(Number(event.target.value || 0), 4)))}
                  />
                </label>
                <p>Sub-agents are isolated parallel tasks for larger non-chat jobs. Separate chat messages already run concurrently.</p>
              </div>
            </details>
          </div>

          <div className="composer-meta">
            <p id="selectedModelHealth" className={`model-health ${healthy ? "is-healthy" : "is-unhealthy"}`}>
              {disabledReason || modelHealthLine(selectedModelObject, models)}
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
        </form>
      </section>
    </section>
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
