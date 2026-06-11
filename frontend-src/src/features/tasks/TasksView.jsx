import React, { useMemo, useState } from "react";
import { Pause, Play, RefreshCw, Route, Square, Users, Wrench } from "lucide-react";
import { displayModelName, displayWorkspaceName } from "../../lib/display.js";

const activityTabs = ["Runs", "Approvals", "Sessions", "Pipeline", "Tools", "Audit"];

export function ActivityView({
  view,
  tasks,
  models,
  refresh,
  approvals,
  sessions,
  auditEvents,
  tools,
  go,
  cancelTask,
  pauseTask,
  resumeTask,
  openTaskDetails,
}) {
  const [tab, setTab] = useState("Runs");
  const pendingApprovals = approvals?.approvals || [];
  const recentSessions = sessions?.sessions || [];
  const toolCount = tools?.tools?.length || 0;
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

      <div className="task-dashboard activity-workspace">
        <aside className="activity-nav-panel" aria-label="Activity sections">
          <div className="activity-status-card">
            <span className="eyebrow">Live State</span>
            <strong>{activeTasks.length ? `${activeTasks.length} active` : "Idle"}</strong>
            <span>{pendingApprovals.length ? `${pendingApprovals.length} approval${pendingApprovals.length === 1 ? "" : "s"} waiting` : "No approvals waiting"}</span>
          </div>
          <nav className="activity-tab-shell" aria-label="Activity navigation">
            <div
              className="activity-tabs"
              role="tablist"
              aria-label="Activity sections"
              onKeyDown={(event) => {
                if (["ArrowRight", "ArrowDown"].includes(event.key)) {
                  event.preventDefault();
                  moveTab(1);
                }
                if (["ArrowLeft", "ArrowUp"].includes(event.key)) {
                  event.preventDefault();
                  moveTab(-1);
                }
              }}
            >
              {activityTabs.map((item) => (
                <button
                  key={item}
                  id={`activity-tab-${item.toLowerCase()}`}
                  data-testid={`activity-tab-${item.toLowerCase()}`}
                  type="button"
                  className={tab === item ? "activity-tab is-active" : "activity-tab"}
                  role="tab"
                  aria-label={`Open ${item} activity`}
                  aria-selected={tab === item}
                  aria-controls={`activity-panel-${item.toLowerCase()}`}
                  tabIndex={tab === item ? 0 : -1}
                  onClick={() => setTab(item)}
                >
                  <span>{item}</span>
                  <small>{activityTabBadge(item, tasks.length, activeTasks.length, pendingApprovals.length, recentSessions.length, toolCount)}</small>
                </button>
              ))}
            </div>
            <p className="activity-tab-context" aria-live="polite">{activityContext(tab, activeTasks.length, pendingApprovals.length, toolCount)}</p>
          </nav>
        </aside>

        <div className="activity-main-panel">
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

          {tab === "Tools" && (
            <section id="activity-panel-tools" role="tabpanel" aria-labelledby="activity-tab-tools" className="activity-panel">
            <ToolRelayPanel tools={tools} />
            </section>
          )}

          {tab === "Audit" && (
            <section id="activity-panel-audit" role="tabpanel" aria-labelledby="activity-tab-audit" className="activity-panel">
            <pre id="activityAuditLog" className="log-box">{JSON.stringify(auditEvents || [], null, 2)}</pre>
            </section>
          )}
        </div>

        <aside className="activity-inspector-panel" aria-label="Activity inspector">
          <div className="activity-inspector-head">
            <span className="eyebrow">Inspector</span>
            <h2>Operations snapshot</h2>
          </div>
          <dl className="activity-inspector-stats">
            <div><dt>Runs</dt><dd>{tasks.length}</dd></div>
            <div><dt>Active</dt><dd>{activeTasks.length}</dd></div>
            <div><dt>Approvals</dt><dd>{pendingApprovals.length}</dd></div>
            <div><dt>Tools</dt><dd>{toolCount}</dd></div>
          </dl>
          <div className="activity-inspector-actions">
            <button type="button" className="tiny-action" onClick={() => setTab("Runs")}>View runs</button>
            <button type="button" className="tiny-action" onClick={() => setTab("Approvals")}>Review approvals</button>
            <button type="button" className="tiny-action" onClick={() => go("settings", "tool-relays")}>Tool relays</button>
          </div>
          <section className="activity-current-run" aria-label="Current run">
            <h3>Current run</h3>
            {activeTasks[0] ? (
              <button type="button" className="activity-current-run-card" onClick={() => openTaskDetails(activeTasks[0].id)}>
                <span className={`status-pill status-${activeTasks[0].status}`}>{activeTasks[0].status}</span>
                <strong>{activeTasks[0].objective}</strong>
                <small>{displayModelName(activeTasks[0].model, models)} / {displayWorkspaceName(activeTasks[0].workspace)}</small>
              </button>
            ) : (
              <p>No active run. New agent work will appear here as soon as it starts.</p>
            )}
          </section>
          <section className="activity-current-run" aria-label="Current section">
            <h3>{tab}</h3>
            <p>{activityContext(tab, activeTasks.length, pendingApprovals.length, toolCount)}</p>
          </section>
        </aside>
      </div>
    </section>
  );
}

function ToolRelayPanel({ tools }) {
  const groups = tools?.groups?.length ? tools.groups : groupTools(tools?.tools || []);
  if (!groups.length) return <EmptyPanel title="No tools registered" text="Tool Relay definitions will appear here once the backend is ready." />;
  return (
    <div className="tool-relay-panel" data-testid="tool-relay-panel">
      <div className="section-row">
        <div>
          <span className="eyebrow">Tool Relay</span>
          <h2>Available Local Tools</h2>
          <p>Read-only registry view for tool policy, risk, permissions, and trace behavior.</p>
        </div>
        <Wrench size={22} aria-hidden="true" />
      </div>
      {groups.map((group) => (
        <section className="tool-relay-group" key={group.category} aria-labelledby={`tool-relay-${slug(group.category)}`}>
          <h3 id={`tool-relay-${slug(group.category)}`}>{group.category}</h3>
          <div className="tool-relay-grid">
            {(group.tools || []).map((tool) => <ToolRelayCard key={tool.id} tool={tool} />)}
          </div>
        </section>
      ))}
    </div>
  );
}

function ToolRelayCard({ tool }) {
  const available = tool.available !== false;
  const permission = tool.permissionFlag || tool.permission_flag || "No extra permission";
  const disabledReason = tool.disabledReason || tool.disabled_reason || "";
  const approvalBehavior = tool.approvalBehavior || tool.approval_behavior || "not_required";
  return (
    <article className={`tool-relay-card ${available ? "is-available" : "is-blocked"}`} data-testid="tool-relay-card">
      <div className="tool-relay-card-head">
        <div>
          <span className={`status-pill risk-${tool.risk}`}>{labelize(tool.risk)}</span>
          <h4>{tool.displayName || tool.display_name || labelize(tool.id)}</h4>
        </div>
        <span className={`status-pill ${available ? "status-done" : "status-error"}`}>{available ? "Available" : "Blocked"}</span>
      </div>
      <p>{tool.description}</p>
      <dl className="detail-grid">
        <dt>Permission</dt><dd>{labelize(permission)}</dd>
        <dt>Approval</dt><dd>{labelize(approvalBehavior)}</dd>
        <dt>Timeout</dt><dd>{Number(tool.timeoutSeconds || tool.timeout_seconds || 0)}s</dd>
        <dt>Summary</dt><dd>{labelize(tool.outputSummaryPolicy || tool.output_summary_policy)}</dd>
      </dl>
      {disabledReason && <p className="tool-relay-reason">Blocked reason: {disabledReason}</p>}
    </article>
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
  const output = task.result || task.logs?.slice(-6).join("\n") || "Queued.";
  return (
    <article className={`task-card ${active ? "is-active" : ""} ${compact ? "is-compact" : ""}`}>
      <div className="task-card-head">
        <div className="task-card-title">
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

      <div className="task-run-info" aria-label="Run metadata">
        <dl>
          <div>
            <dt>Model</dt>
            <dd>{displayModelName(task.model, models)}</dd>
          </div>
          <div>
            <dt>Workspace</dt>
            <dd>{displayWorkspaceName(task.workspace)}</dd>
          </div>
          <div>
            <dt>Mode</dt>
            <dd>{task.mode || "chat"}</dd>
          </div>
          <div>
            <dt>Progress</dt>
            <dd>{Number(task.progress || 0)}%</dd>
          </div>
        </dl>
        <div className="task-card-actions">
          <button type="button" className="tiny-action" data-testid="activity-task-details" onClick={() => openTaskDetails(task.id)}>
            Details
          </button>
        </div>
      </div>

      {!compact && (
        <>
          <section className="task-message-block" aria-label="Latest task message">
            <span>Latest message</span>
            <pre className="message-result">{output}</pre>
          </section>
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

function activityContext(tab, runningCount, approvalCount, toolCount = 0) {
  if (tab === "Runs") return runningCount ? `${runningCount} run${runningCount === 1 ? "" : "s"} active now.` : "No active runs right now.";
  if (tab === "Approvals") return approvalCount ? `${approvalCount} approval${approvalCount === 1 ? "" : "s"} waiting.` : "No approvals waiting.";
  if (tab === "Sessions") return "Recent local sessions and resumable work.";
  if (tab === "Pipeline") return "How Rasputin routes planning, tools, approvals, execution, and memory.";
  if (tab === "Tools") return `${toolCount} registered Tool Relay definition${toolCount === 1 ? "" : "s"}.`;
  return "Local audit events for sensitive actions.";
}

function activityTabBadge(tab, taskCount, runningCount, approvalCount, sessionCount, toolCount) {
  if (tab === "Runs") return runningCount ? `${runningCount} active` : `${taskCount} total`;
  if (tab === "Approvals") return `${approvalCount} pending`;
  if (tab === "Sessions") return `${sessionCount} saved`;
  if (tab === "Tools") return `${toolCount} tools`;
  if (tab === "Pipeline") return "Runtime";
  return "Local log";
}

function groupTools(tools) {
  const grouped = new Map();
  tools.forEach((tool) => {
    const category = tool.category || "Other";
    grouped.set(category, [...(grouped.get(category) || []), tool]);
  });
  return [...grouped.entries()].map(([category, group]) => ({ category, tools: group }));
}

function labelize(value) {
  return String(value || "")
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase())
    || "Unknown";
}

function slug(value) {
  return String(value || "tools").replace(/[^a-z0-9]+/gi, "-").toLowerCase();
}

function EmptyPanel({ title, text }) {
  return (
    <div className="empty-panel">
      <h2>{title}</h2>
      <p>{text}</p>
    </div>
  );
}
