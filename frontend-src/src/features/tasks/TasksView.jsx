import React, { useMemo, useState, useEffect } from "react";
import {
  Pause, Play, RefreshCw, Square, Users, Search, 
  Activity, AlertTriangle, CheckCircle, Clock, History as HistoryIcon, ListFilter,
  Server, Database, HardDrive, Download, Eye, FileText, Archive, ChevronUp, ChevronDown
} from "lucide-react";
import { displayModelName, displayWorkspaceName } from "../../lib/display.js";
import { actionRegistry, useReliableAction } from "../../lib/actionRegistry.js";
import { Button as UIButton } from "@/components/ui/button.jsx";
import { Badge } from "@/components/ui/badge.jsx";
import { cn } from "@/lib/utils.js";
import "../../styles/history-workspace-v3.css";

const activityIcons = { History: HistoryIcon, "All Runs": ListFilter, Active: Activity, Queue: Clock, Completed: CheckCircle, Failed: AlertTriangle, Scheduled: Clock, "System Events": Server, "Audit Log": FileText };

const activityGroups = [
  { label: "Timeline", items: ["History"] },
  { label: "Runs", items: ["All Runs", "Active", "Queue", "Completed", "Failed", "Scheduled"] },
  { label: "System", items: ["System Events", "Audit Log"] },
];

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
  retryTask,
  setTaskPriority,
  openTaskDetails,
  inbox = [],
  markInboxRead,
  archiveInbox,
  markAllInboxRead,
}) {
  const [tab, setTab] = useState("History");
  const [searchQuery, setSearchQuery] = useState("");
  const [localAudit, setLocalAudit] = useState(actionRegistry.logs);
  
  // Phase 10: Button Reliability Framework State
  const [uiState, setUiState] = useState({ status: 'idle', message: '' });
  const executeAction = useReliableAction("ActivityView");

  useEffect(() => {
    const handleAudit = () => setLocalAudit([...actionRegistry.logs]);
    window.addEventListener("rasputin:audit", handleAudit);
    return () => window.removeEventListener("rasputin:audit", handleAudit);
  }, []);

  const pendingApprovals = approvals?.approvals || [];
  const rootTasks = tasks.filter((task) => !task.parentId);
  
  // Helpers
  const activeTasks = tasks.filter((task) => ["queued", "running", "paused"].includes(task.status));
  const completedTasks = tasks.filter((task) => ["completed", "done", "success"].includes(task.status));
  const failedTasks = tasks.filter((task) => ["failed", "error", "cancelled"].includes(task.status));
  const queuedTasks = tasks
    .filter((task) => task.status === "queued")
    .sort((a, b) => Number(b.priority || 0) - Number(a.priority || 0) || Number(a.queueOrder || a.createdAt || 0) - Number(b.queueOrder || b.createdAt || 0));
  const scheduledTasks = queuedTasks.filter((task) => Number(task.scheduledFor || 0) > Date.now() / 1000);
  const unreadInbox = inbox.filter((event) => event.status === "unread");
  const historyEntries = useMemo(() => {
    const taskEntries = rootTasks.map((task) => ({
      kind: "task",
      id: "task-" + task.id,
      timestamp: historyTimestamp(task.updatedAt || task.updated_at || task.completedAt || task.completed_at || task.createdAt || task.created_at),
      task,
    }));
    const notificationEntries = inbox.map((event) => ({
      kind: "notification",
      id: "notification-" + event.id,
      timestamp: historyTimestamp(event.created_at || event.createdAt || event.updated_at || event.updatedAt),
      event,
    }));
    return [...taskEntries, ...notificationEntries].sort((a, b) => b.timestamp - a.timestamp);
  }, [rootTasks, inbox]);
  const tabCounts = { History: historyEntries.length, "All Runs": tasks.length, Active: activeTasks.length, Queue: queuedTasks.length, Completed: completedTasks.length, Failed: failedTasks.length, Scheduled: scheduledTasks.length, "System Events": auditEvents?.length || 0, "Audit Log": localAudit.length };

  // Search Filter
  const filteredTasks = useMemo(() => {
    let source = [];
    if (tab === "All Runs") source = tasks;
    if (tab === "Active") source = activeTasks;
    if (tab === "Completed") source = completedTasks;
    if (tab === "Failed") source = failedTasks;
    
    if (!searchQuery.trim()) return source;
    const q = searchQuery.toLowerCase();
    return source.filter(t => 
      t.id?.toLowerCase().includes(q) || 
      t.objective?.toLowerCase().includes(q) ||
      t.status?.toLowerCase().includes(q)
    );
  }, [tasks, tab, searchQuery, activeTasks, completedTasks, failedTasks]);

  // Reliable wrappers for actions
  const handleRefresh = () => executeAction("RefreshActivities", "system", async () => refresh?.(), setUiState);
  const handleCancel = (id) => executeAction("CancelTask", id, async () => cancelTask?.(id), setUiState);
  const handlePause = (id) => executeAction("PauseTask", id, async () => pauseTask?.(id), setUiState);
  const handleResume = (id) => executeAction("ResumeTask", id, async () => resumeTask?.(id), setUiState);
  const handleRetry = (id) => executeAction("RetryTask", id, async () => retryTask?.(id), setUiState);
  const handlePriority = (id, priority) => executeAction("SetTaskPriority", id, async () => setTaskPriority?.(id, priority), setUiState);

  return (
    <section className={`w2-layout app-view activity-view tw ${view === "activity" ? "active" : ""}`} id="activityView" data-app-view="activity">
      <div className="history-page-shell fx-rise mx-auto flex w-full min-w-0 max-w-[1500px] flex-col gap-5 p-7">

      {/* Header */}
      <div className="history-page-header history-v3-header flex flex-wrap items-start justify-between gap-5">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">History</h1>
          <p className="mt-1.5 text-sm text-muted-foreground">Recent chats, runs, notifications, and outcomes in one quiet timeline.</p>
        </div>
        <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
          <span>{historyEntries.length} recent items</span>
          {unreadInbox.length > 0 && <Badge variant="muted">{unreadInbox.length} unread</Badge>}
        </div>
      </div>

      <div className="history-toolbar history-v3-toolbar">
        <div className="activity-tabs-scroll" role="tablist" aria-label="History views" data-testid="history-view-tabs">
          {activityGroups.map((group) => (
            <div className="history-nav-group" role="presentation" key={group.label}>
              <span className="history-nav-label">{group.label}</span>
              {group.items.map((item) => (
                <button
                  key={item}
                  type="button"
                  role="tab"
                  aria-selected={tab === item}
                  className={cn("history-view-tab", tab === item && "is-active")}
                  onClick={() => setTab(item)}
                >
                  {React.createElement(activityIcons[item] || Activity, { size: 14, "aria-hidden": true })}
                  <span>{item}</span><small>{tabCounts[item] || 0}</small>
                </button>
              ))}
            </div>
          ))}
        </div>
        <div className="flex-1" />
        {uiState.status !== 'idle' && (
          <Badge variant={uiState.status === 'failed' ? "down" : uiState.status === 'success' ? "up" : "muted"}>
            {uiState.message}
          </Badge>
        )}
        <UIButton className="history-refresh-button" variant="outline" size="sm" onClick={handleRefresh} aria-label="Refresh history">
          <RefreshCw size={15} /> Refresh
        </UIButton>
      </div>

      <div className="w2-main-grid history-main-grid">
        
        {/* MAIN COLUMN */}
        <div className="w2-column">

          {tab === "History" && (
            <div className="history-v3-content flex flex-1 flex-col gap-3">
              <div className="history-stream-command rounded-xl border border-border bg-card">
                <div className="history-stream-title">
                  <span className="rounded-lg bg-primary/10 p-2 text-primary"><Clock size={18} /></span>
                  <div>
                    <h2 className="font-semibold">Recent history</h2>
                    <p className="text-xs text-muted-foreground">Notifications and task outcomes, newest first.</p>
                  </div>
                </div>
                <div className="history-search-field flex items-center gap-2">
                  <Search size={16} className="text-muted-foreground" />
                  <input
                    className="w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground"
                    placeholder="Search history..."
                    aria-label="Search history"
                    value={searchQuery}
                    onChange={(event) => setSearchQuery(event.target.value)}
                  />
                </div>
              </div>
              <div className="history-stream-list flex flex-col gap-2 overflow-y-auto">
                {historyEntries
                  .filter((entry) => {
                    if (!searchQuery.trim()) return true;
                    const query = searchQuery.toLowerCase();
                    const searchText = entry.kind === "task"
                      ? [entry.task.objective, entry.task.status, entry.task.model, entry.task.workspace].join(" ")
                      : [entry.event.title, entry.event.body, entry.event.kind, entry.event.severity].join(" ");
                    return searchText.toLowerCase().includes(query);
                  })
                  .map((entry) => entry.kind === "task" ? (
                    <article key={entry.id} className="history-timeline-row history-timeline-task rounded-xl border border-border bg-card p-4">
                      <span className={cn("history-status-signal", entry.task.status)} aria-hidden="true" />
                      <div className="flex items-start justify-between gap-4">
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <Badge variant={["failed", "error", "cancelled"].includes(entry.task.status) ? "down" : ["queued", "running", "paused"].includes(entry.task.status) ? "muted" : "up"} className="capitalize">{entry.task.status}</Badge>
                            <strong className="truncate">{entry.task.objective || "Untitled run"}</strong>
                          </div>
                          <p className="mt-1 text-xs text-muted-foreground">
                            {displayModelName(entry.task.model, models)} - {displayWorkspaceName(entry.task.workspace)}
                          </p>
                        </div>
                        <time className="shrink-0 text-xs text-muted-foreground">{new Date(entry.timestamp).toLocaleString()}</time>
                      </div>
                      <UIButton className="history-row-action" variant="outline" size="sm" onClick={() => openTaskDetails?.(entry.task.id)}>Open details</UIButton>
                    </article>
                  ) : (
                    <article key={entry.id} className={cn("history-timeline-row history-timeline-notification rounded-xl border bg-card p-4", entry.event.status === "unread" && "is-unread")}>
                      <span className={cn("history-status-signal", entry.event.severity || "info")} aria-hidden="true" />
                      <div className="flex items-start justify-between gap-4">
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            {entry.event.status === "unread" && <span className="h-2 w-2 rounded-full bg-primary" aria-label="Unread" />}
                            <strong>{entry.event.title}</strong>
                            <Badge variant={entry.event.severity === "error" ? "down" : entry.event.severity === "success" ? "up" : "muted"}>{entry.event.kind.replaceAll("_", " ")}</Badge>
                          </div>
                          <p className="mt-1 text-sm text-muted-foreground">{entry.event.body}</p>
                        </div>
                        <time className="shrink-0 text-xs text-muted-foreground">{new Date(entry.timestamp).toLocaleString()}</time>
                      </div>
                      <div className="history-row-actions">
                        {entry.event.task_id && <UIButton size="sm" onClick={() => { markInboxRead?.(entry.event.id); openTaskDetails?.(entry.event.task_id); }}>Open details</UIButton>}
                        {entry.event.status === "unread" && <UIButton variant="outline" size="sm" onClick={() => markInboxRead?.(entry.event.id)}>Mark read</UIButton>}
                        <UIButton variant="ghost" size="icon" title="Archive notification" aria-label="Archive notification" onClick={() => archiveInbox?.(entry.event.id)}><Archive size={15} /></UIButton>
                      </div>
                    </article>
                  ))}
                {!historyEntries.length && <div className="rounded-xl border border-dashed border-border bg-card/50 p-10 text-center text-sm text-muted-foreground">No history yet. Task outcomes and notifications will appear here.</div>}
              </div>
            </div>
          )}

          {tab === "Queue" && (
            <div className="flex flex-1 flex-col gap-3">
              <div className="rounded-xl border border-border bg-card p-4">
                <h2 className="font-semibold">Persistent task queue</h2>
                <p className="mt-1 text-sm text-muted-foreground">Higher priority work runs first. Queued tasks survive refreshes and server restarts.</p>
              </div>
              {queuedTasks.map((task) => (
                <RunCard
                  key={task.id}
                  task={task}
                  models={models}
                  onCancel={() => handleCancel(task.id)}
                  onPause={() => handlePause(task.id)}
                  onResume={() => handleResume(task.id)}
                  onDetails={() => openTaskDetails?.(task.id)}
                  onRetry={() => handleRetry(task.id)}
                  onPriority={(priority) => handlePriority(task.id, priority)}
                  onDownloadLogs={() => downloadTaskLogs(task)}
                />
              ))}
              {queuedTasks.length === 0 && <div className="rounded-xl border border-dashed border-border bg-card/50 p-10 text-center text-sm text-muted-foreground">The queue is empty. Send another message while a run is active to add work here.</div>}
            </div>
          )}
          
          {/* PHASE 6: Activity Search */}
          {["All Runs", "Active", "Completed", "Failed"].includes(tab) && (
            <div className="flex flex-1 flex-col gap-4">
              <div className="flex items-center gap-2 rounded-xl border border-border bg-card px-3.5 py-2.5">
                <Search size={16} className="text-muted-foreground" />
                <input
                  className="w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground"
                  placeholder="Search by ID, agent, status, or error text…"
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                />
              </div>

              {/* Run List */}
              <div className="flex flex-1 flex-col gap-2 overflow-y-auto">
                {filteredTasks.map(task => (
                  <RunCard
                    key={task.id}
                    task={task}
                    models={models}
                    onCancel={() => handleCancel(task.id)}
                    onPause={() => handlePause(task.id)}
                    onResume={() => handleResume(task.id)}
                    onRetry={() => handleRetry(task.id)}
                    onPriority={(priority) => handlePriority(task.id, priority)}
                    onDetails={() => openTaskDetails?.(task.id)}
                    onDownloadLogs={() => downloadTaskLogs(task)}
                  />
                ))}
                {filteredTasks.length === 0 && (
                  <div className="rounded-xl border border-border bg-card p-8 text-center text-sm text-muted-foreground">
                    No matching runs found.
                  </div>
                )}
              </div>
            </div>
          )}

          {/* PHASE 7: Audit Log */}
          {tab === "Audit Log" && (
            <div className="w2-section" style={{ flex: 1 }}>
              <h2 className="w2-section-title">Action Registry & Audit Log</h2>
              <div className="w2-card" style={{ flex: 1, overflowY: 'auto', gap: '8px' }}>
                {localAudit.length === 0 && <p style={{ color: 'var(--cc-muted)' }}>No actions recorded yet.</p>}
                {localAudit.map(log => (
                  <div key={log.id} style={{ padding: '12px', border: '1px solid var(--cc-border)', borderRadius: '6px', fontSize: '0.875rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                      <strong>{log.name}</strong>
                      <span style={{ color: 'var(--cc-muted)' }}>{new Date(log.timestamp).toLocaleTimeString()}</span>
                    </div>
                    <div>Target: {log.target}</div>
                    <div style={{ 
                      color: log.status === 'failed' ? 'var(--ras-danger)' : 
                             log.status === 'success' ? 'var(--ras-safe)' : 'var(--cc-muted)' 
                    }}>
                      Status: {log.status} {log.details && `- ${log.details}`}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* PHASE 12: System Events & Health */}
          {tab === "System Events" && (
            <div className="w2-section" style={{ flex: 1 }}>
              <h2 className="w2-section-title">System Health Panel</h2>
              <div className="w2-card" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <Server size={24} color="var(--cc-muted)" />
                  <div>
                    <strong>API Status</strong>
                    <div style={{ fontSize: '0.875rem', color: 'var(--cc-muted)' }}>Unknown - refresh to check</div>
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <Database size={24} color="var(--cc-muted)" />
                  <div>
                    <strong>Database Status</strong>
                    <div style={{ fontSize: '0.875rem', color: 'var(--cc-muted)' }}>Unknown - refresh to check</div>
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <HardDrive size={24} color="var(--cc-muted)" />
                  <div>
                    <strong>Vector Store Status</strong>
                    <div style={{ fontSize: '0.875rem', color: 'var(--cc-muted)' }}>Unknown - refresh to check</div>
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <Activity size={24} color="var(--ras-warn)" />
                  <div>
                    <strong>Worker Queue</strong>
                    <div style={{ fontSize: '0.875rem', color: 'var(--cc-muted)' }}>{activeTasks.length} jobs running</div>
                  </div>
                </div>
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <UIButton className="history-refresh-button" variant="outline" size="sm" onClick={handleRefresh} aria-label="Refresh history">Refresh activity</UIButton>
                <span className="text-xs text-muted-foreground">Health data is not included in the current activity payload.</span>
              </div>

              <h2 className="w2-section-title" style={{ marginTop: '16px' }}>Raw Backend Events</h2>
              <pre className="w2-preview-block" style={{ flex: 1 }}>
                {JSON.stringify(auditEvents || [], null, 2)}
              </pre>
            </div>
          )}
          
          {/* Scheduled */}
          {tab === "Scheduled" && (
             <div className="w2-section">
                <h2 className="w2-section-title">Scheduled Jobs</h2>
                <div className="w2-card">
                  {scheduledTasks.map((task) => (
                    <button key={task.id} type="button" className="flex w-full items-center justify-between rounded-lg border border-border p-3 text-left" onClick={() => openTaskDetails?.(task.id)}>
                      <span><strong className="block">{task.objective}</strong><span className="text-xs text-muted-foreground">Priority {task.priority || 0}</span></span>
                      <time className="text-sm text-muted-foreground">{new Date(Number(task.scheduledFor) * 1000).toLocaleString()}</time>
                    </button>
                  ))}
                  {scheduledTasks.length === 0 && <p style={{ color: 'var(--cc-muted)' }}>No scheduled tasks available.</p>}
                </div>
             </div>
          )}

        </div>

        {/* RIGHT COLUMN: Inspector / Monitor */}
        <aside className="w2-column history-inspector history-v3-inspector" aria-label="Execution summary">
          <header className="history-inspector-heading">
            <span>Execution summary</span>
            <Badge variant={activeTasks.length ? "muted" : "up"}>{activeTasks.length ? activeTasks.length + " active" : "Idle"}</Badge>
          </header>
          <div className="flex flex-col gap-4">
          
          {/* PHASE 3: Active Execution Monitor */}
          <div className="w2-section">
            <h2 className="w2-section-title">Live Execution Monitor</h2>
            <div className="w2-card">
              {activeTasks.length === 0 ? (
                <p style={{ fontSize: '0.875rem', color: 'var(--cc-muted)' }}>No runs currently active.</p>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {activeTasks.slice(0, 3).map(t => (
                    <div key={t.id} style={{ padding: '12px', border: '1px solid var(--cc-border)', borderRadius: '6px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                        <span style={{ fontSize: '0.875rem', fontWeight: 600 }} className="truncate">{t.objective}</span>
                        <span className={`status-pill status-${t.status}`}>{t.status}</span>
                      </div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--cc-muted)', marginBottom: '8px' }}>
                        Workspace: {displayWorkspaceName(t.workspace)}
                      </div>
                      <div className="w2-action-panel-grid">
                        {t.status === 'paused' ? (
                          <button className="w2-button" style={{ padding: '4px' }} onClick={() => handleResume(t.id)}><Play size={14}/></button>
                        ) : (
                          <button className="w2-button" style={{ padding: '4px' }} onClick={() => handlePause(t.id)}><Pause size={14}/></button>
                        )}
                        <button className="w2-button" style={{ padding: '4px', color: 'var(--ras-danger)' }} onClick={() => handleCancel(t.id)}><Square size={14}/></button>
                        <button className="w2-button" style={{ padding: '4px', gridColumn: 'span 2' }} onClick={() => openTaskDetails?.(t.id)}>Open Details</button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* PHASE 9: Analytics Dashboard Snapshot */}
          <div className="w2-section">
            <h2 className="w2-section-title">Analytics</h2>
            <div className="w2-card" style={{ fontSize: '0.875rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--cc-border)' }}>
                <span>Success Rate</span>
                <strong>{tasks.length ? Math.round((completedTasks.length / tasks.length) * 100) : 0}%</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--cc-border)' }}>
                <span>Failure Rate</span>
                <strong>{tasks.length ? Math.round((failedTasks.length / tasks.length) * 100) : 0}%</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0' }}>
                <span>Approvals Pending</span>
                <strong>{pendingApprovals.length}</strong>
              </div>
            </div>
          </div>
          </div>
        </aside>

      </div>
      </div>
    </section>
  );
}

// --- Helpers ---

function historyTimestamp(value) {
  const number = Number(value || 0);
  if (!Number.isFinite(number) || number <= 0) return 0;
  return number > 100000000000 ? number : number * 1000;
}

// PHASE 4 & 5 & 8: Embedded in RunCard
function RunCard({ task, models, onCancel, onPause, onResume, onDetails, onRetry, onPriority, onDownloadLogs }) {
  const isFailed = ["failed", "error", "cancelled"].includes(task.status);
  const isActive = ["queued", "running", "paused"].includes(task.status);
  const [expanded, setExpanded] = useState(false);

  const statusVariant = isFailed ? "down" : isActive ? "muted" : "up";
  return (
    <div className={cn(
      "ras-list-item history-run-ledger-row glow-card rounded-2xl border bg-card p-4",
      isFailed ? "border-rose-500/40" : "border-border",
    )}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 flex-col gap-1">
          <div className="flex items-center gap-2.5">
            <Badge variant={statusVariant} className="capitalize">{task.status}</Badge>
            <strong className="truncate text-[0.95rem]">{task.objective || "Untitled Run"}</strong>
          </div>
          <div className="text-xs text-muted-foreground">
            {displayModelName(task.model, models)} • {displayWorkspaceName(task.workspace)} • ID: {task.id.slice(0, 8)}
          </div>
        </div>
        <div className="flex shrink-0 gap-2">
          <UIButton variant="outline" size="sm" onClick={() => setExpanded(!expanded)}>
            {expanded ? "Collapse" : "Inspect"}
          </UIButton>
          {isActive && (
            <div className="flex gap-1.5">
              {task.status === "queued" && (
                <>
                  <UIButton variant="outline" size="icon" onClick={() => onPriority?.(Number(task.priority || 0) + 1)} title="Raise priority" aria-label="Raise priority"><ChevronUp size={14} /></UIButton>
                  <UIButton variant="outline" size="icon" onClick={() => onPriority?.(Number(task.priority || 0) - 1)} title="Lower priority" aria-label="Lower priority"><ChevronDown size={14} /></UIButton>
                </>
              )}
              {task.status === 'paused' ? (
                <UIButton variant="outline" size="icon" onClick={onResume} title="Resume"><Play size={14} /></UIButton>
              ) : (
                <UIButton variant="outline" size="icon" onClick={onPause} title="Pause"><Pause size={14} /></UIButton>
              )}
              <UIButton variant="outline" size="icon" className="text-rose-400 hover:text-rose-300" onClick={onCancel} title="Cancel"><Square size={14} /></UIButton>
            </div>
          )}
        </div>
      </div>

      {expanded && (
        <div style={{ marginTop: '12px', paddingTop: '12px', borderTop: '1px solid var(--cc-border)', display: 'flex', flexDirection: 'column', gap: '12px' }}>
          
          {/* PHASE 4: Timeline / Logs */}
          <div>
            <strong style={{ fontSize: '0.875rem' }}>Execution Logs</strong>
            <pre className="w2-preview-block" style={{ maxHeight: '150px', marginTop: '8px', fontSize: '0.75rem' }}>
              {task.logs?.join('\n') || task.result || "No logs available for this run."}
            </pre>
          </div>

          {/* PHASE 5: Failed Run Management */}
          {isFailed && (
            <div style={{ padding: '12px', backgroundColor: 'color-mix(in srgb, var(--ras-danger) 10%, var(--cc-surface))', border: '1px solid var(--ras-danger)', borderRadius: '6px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--ras-danger)', marginBottom: '8px' }}>
                <AlertTriangle size={16} /> <strong>Run Failed</strong>
              </div>
              <p style={{ fontSize: '0.875rem', margin: '0 0 8px 0' }}>The agent encountered an error and could not complete the objective.</p>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button className="w2-button" style={{ borderColor: 'var(--ras-danger)', color: 'var(--ras-danger)' }} onClick={onRetry}>Retry Run</button>
                <button className="w2-button" onClick={onDetails} disabled={!onDetails}>Debug Stack Trace</button>
              </div>
            </div>
          )}

          {/* PHASE 8: Artifact Management */}
          <div>
            <strong style={{ fontSize: '0.875rem' }}>Artifacts & Evidence</strong>
            <div style={{ display: 'flex', gap: '8px', marginTop: '8px' }}>
              <button className="w2-button" style={{ fontSize: '0.75rem', padding: '6px 12px' }} onClick={onDetails} disabled={!onDetails}><FileText size={14}/> Execution Report</button>
              <button className="w2-button" style={{ fontSize: '0.75rem', padding: '6px 12px' }} onClick={onDownloadLogs} disabled={!task.logs?.length && !task.trace?.length} title={!task.logs?.length && !task.trace?.length ? "No task logs or trace are available to download." : "Download recorded task logs and trace"}><Download size={14}/> Download Logs</button>
            </div>
          </div>
          
          <UIButton className="self-start" onClick={onDetails}>
            Open Full Details View
          </UIButton>
        </div>
      )}
    </div>
  );
}

function downloadTaskLogs(task) {
  const logs = Array.isArray(task?.logs) ? task.logs : [];
  const trace = Array.isArray(task?.trace) ? task.trace : [];
  if (!logs.length && !trace.length) return;
  const content = [
    `Task: ${task.id}`,
    `Objective: ${task.objective || "Untitled Run"}`,
    `Status: ${task.status || "Unknown"}`,
    "", "Logs:",
    ...logs.map((entry) => typeof entry === "string" ? entry : JSON.stringify(entry)),
    ...(trace.length ? ["", "Trace:", ...trace.map((entry) => typeof entry === "string" ? entry : JSON.stringify(entry))] : []),
  ].join("\n");
  const url = URL.createObjectURL(new Blob([content], { type: "text/plain;charset=utf-8" }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `rasputin-task-${String(task.id).slice(0, 8)}-logs.txt`;
  anchor.click();
  URL.revokeObjectURL(url);
}
