import React, { useMemo, useState } from "react";
import { Pause, Play, RefreshCw, Route, Square, Users } from "lucide-react";
import { displayModelName, displayWorkspaceName } from "../../lib/display.js";

const activityTabs = ["Runs", "Approvals", "Sessions", "Pipeline", "Audit"];

export function ActivityView({
  view,
  tasks,
  models,
  refresh,
  approvals,
  sessions,
  auditEvents,
  go,
  cancelTask,
  pauseTask,
  resumeTask,
  openTaskDetails,
}) {
  const [tab, setTab] = useState("Runs");
  const pendingApprovals = approvals?.approvals || [];
  const recentSessions = sessions?.sessions || [];
  const activeTasks = tasks.filter((task) => ["queued", "running", "paused"].includes(task.status));
  const rootTasks = tasks.filter((task) => !task.parentId);
  const helpersByParent = useMemo(() => {
    const grouped = new Map();
    tasks.filter((task) => task.parentId).forEach((task) => {
      grouped.set(task.parentId, [...(grouped.get(task.parentId) || []), task]);
    });
    return grouped;
  }, [tasks]);

  function moveTab(direction) {
    const current = activityTabs.indexOf(tab);
    const next = (current + direction + activityTabs.length) % activityTabs.length;
    setTab(activityTabs[next]);
  }

  return (
    <section className={`app-view activity-view ${view === "activity" ? "active" : ""}`} id="activityView" data-app-view="activity" aria-labelledby="activityTitle">
      <header className="page-header activity-header">
        <div>
          <span className="eyebrow">Operations</span>
          <h1 id="activityTitle">Activity</h1>
          <p>Concurrent runs, sub-agents, approvals, sessions, and local audit signals.</p>
        </div>
        <button className="secondary-action" type="button" onClick={refresh}>
          <RefreshCw size={15} />
          Refresh
        </button>
      </header>

      <div className="task-dashboard">
        <div
          className="activity-tabs"
          role="tablist"
          aria-label="Activity sections"
          onKeyDown={(event) => {
            if (event.key === "ArrowRight") {
              event.preventDefault();
              moveTab(1);
            }
            if (event.key === "ArrowLeft") {
              event.preventDefault();
              moveTab(-1);
            }
          }}
        >
          {activityTabs.map((item) => (
            <button
              key={item}
              id={`activity-tab-${item.toLowerCase()}`}
              type="button"
              className={tab === item ? "activity-tab is-active" : "activity-tab"}
              role="tab"
              aria-selected={tab === item}
              aria-controls={`activity-panel-${item.toLowerCase()}`}
              tabIndex={tab === item ? 0 : -1}
              onClick={() => setTab(item)}
            >
              {item}
            </button>
          ))}
        </div>

        {tab === "Runs" && (
          <section id="activity-panel-runs" role="tabpanel" aria-labelledby="activity-tab-runs" className="activity-panel">
            <div className="run-summary-grid">
              <Stat id="taskCount" label="Total runs" value={tasks.length} />
              <Stat id="runningCount" label="Active now" value={activeTasks.length} />
              <Stat id="mainTaskCount" label="Main runs" value={rootTasks.length} />
              <Stat id="subTaskCount" label="Helper agents" value={tasks.filter((task) => task.parentId).length} />
            </div>

            {activeTasks.length > 0 && (
              <section className="active-run-panel" aria-label="Active concurrent runs">
                <div className="section-row">
                  <div>
                    <h2>Running now</h2>
                    <p>{activeTasks.length} run{activeTasks.length === 1 ? "" : "s"} active. Rasputin can keep these moving in parallel.</p>
                  </div>
                  <Users size={22} aria-hidden="true" />
                </div>
                <div className="run-lanes">
                  {activeTasks.map((task) => (
                    <TaskRunCard
                      key={task.id}
                      task={task}
                      models={models}
                      cancelTask={cancelTask}
                      pauseTask={pauseTask}
                      resumeTask={resumeTask}
                      openTaskDetails={openTaskDetails}
                      compact
                    />
                  ))}
                </div>
              </section>
            )}

            <div id="mainTaskList" className="activity-list">
              {rootTasks.map((task) => (
                <TaskRunCard
                  key={task.id}
                  task={task}
                  helpers={helpersByParent.get(task.id) || []}
                  models={models}
                  cancelTask={cancelTask}
                  pauseTask={pauseTask}
                  resumeTask={resumeTask}
                  openTaskDetails={openTaskDetails}
                />
              ))}
              {!tasks.length && <EmptyPanel title="No runs yet" text="Start a chat or agent task and it will appear here." />}
            </div>
          </section>
        )}

        {tab === "Approvals" && (
          <section id="activity-panel-approvals" role="tabpanel" aria-labelledby="activity-tab-approvals" className="activity-panel">
            <div className="activity-list">
              {pendingApprovals.map((approval) => (
                <article className="approval-card" key={approval.id} data-testid="approval-card">
                  <span className={`status-pill status-${approval.status}`}>{approval.status}</span>
                  <h2>{approval.summary}</h2>
                  <p>Code {approval.code} / {approval.actionType || approval.action_type} / {displayWorkspaceName(approval.workspace)}</p>
                  {approval.taskId && (
                    <button className="tiny-action" type="button" onClick={() => openTaskDetails(approval.taskId)}>
                      Open task
                    </button>
                  )}
                </article>
              ))}
              {!pendingApprovals.length && <EmptyPanel title="No approvals" text="Risky actions will wait here before execution." />}
            </div>
          </section>
        )}

        {tab === "Sessions" && (
          <section id="activity-panel-sessions" role="tabpanel" aria-labelledby="activity-tab-sessions" className="activity-panel">
            <div className="activity-list">
              {recentSessions.map((session) => (
                <button className="activity-row" key={session.id} type="button" onClick={() => go("sessions")}>
                  <strong>{session.title}</strong>
                  <span>{session.status} / {session.mode} / {displayWorkspaceName(session.workspace)}</span>
                </button>
              ))}
              {!recentSessions.length && <EmptyPanel title="No sessions yet" text="Conversation sessions will be stored locally." />}
            </div>
          </section>
        )}

        {tab === "Pipeline" && (
          <section id="activity-panel-pipeline" role="tabpanel" aria-labelledby="activity-tab-pipeline" className="activity-panel">
            <article className="pipeline-panel">
              <Route size={22} aria-hidden="true" />
              <div>
                <h2>Agent Runtime Pipeline</h2>
                <div className="runtime-steps">
                  {["Intake", "Context", "Plan", "Tool Plan", "Approval", "Execute", "Reflect", "Memory"].map((step) => (
                    <span className="pipeline-step" key={step}>{step}</span>
                  ))}
                </div>
                <p>Risky actions are approval-gated. Local memory, RAG, and Graphify stay inside approved workspaces.</p>
              </div>
            </article>
          </section>
        )}

        {tab === "Audit" && (
          <section id="activity-panel-audit" role="tabpanel" aria-labelledby="activity-tab-audit" className="activity-panel">
            <pre id="activityAuditLog" className="log-box">{JSON.stringify(auditEvents || [], null, 2)}</pre>
          </section>
        )}
      </div>
    </section>
  );
}

function Stat({ id, label, value }) {
  return (
    <article className="stat-card">
      <strong id={id}>{value}</strong>
      <span>{label}</span>
    </article>
  );
}

function TaskRunCard({ task, helpers = [], models, cancelTask, pauseTask, resumeTask, openTaskDetails, compact = false }) {
  const status = task.status || "queued";
  const active = ["queued", "running", "paused"].includes(status);
  return (
    <article className={`task-card ${active ? "is-active" : ""} ${compact ? "is-compact" : ""}`}>
      <div className="task-card-head">
        <div>
          <span className={`status-pill status-${status}`}>{status}</span>
          <h2>{task.objective}</h2>
        </div>
        {active && (
          <div className="task-card-actions" aria-label="Task controls">
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
      </div>
      <div className="meta-row">
        <span>{displayModelName(task.model, models)}</span>
        <span>{displayWorkspaceName(task.workspace)}</span>
        <span>{task.mode || "chat"}</span>
        <span>{Number(task.progress || 0)}%</span>
      </div>
      <div className="task-card-actions">
        <button type="button" className="tiny-action" data-testid="activity-task-details" onClick={() => openTaskDetails(task.id)}>
          Details
        </button>
      </div>
      {!compact && (
        <>
          <pre className="message-result">{task.result || task.logs?.slice(-6).join("\n") || "Queued."}</pre>
          {helpers.length > 0 && (
            <div className="helper-list" aria-label="Sub-agents">
              {helpers.map((helper) => (
                <button className="helper-row" type="button" key={helper.id} onClick={() => openTaskDetails(helper.id)}>
                  <Users size={14} />
                  <span>{helper.objective}</span>
                  <span className={`status-pill status-${helper.status}`}>{helper.status}</span>
                </button>
              ))}
            </div>
          )}
        </>
      )}
    </article>
  );
}

function EmptyPanel({ title, text }) {
  return (
    <div className="empty-panel">
      <h2>{title}</h2>
      <p>{text}</p>
    </div>
  );
}
