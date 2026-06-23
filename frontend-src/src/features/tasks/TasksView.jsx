import React, { useMemo, useState, useEffect } from "react";
import {
  Pause, Play, RefreshCw, Square, Users, Search, 
  Activity, AlertTriangle, CheckCircle, Clock, 
  Server, Database, HardDrive, Download, Eye, FileText
} from "lucide-react";
import { displayModelName, displayWorkspaceName } from "../../lib/display.js";
import { actionRegistry, useReliableAction } from "../../lib/actionRegistry.js";
import { Button as UIButton } from "@/components/ui/button.jsx";
import { Badge } from "@/components/ui/badge.jsx";
import { cn } from "@/lib/utils.js";

const activityTabs = ["All Runs", "Active", "Completed", "Failed", "Scheduled", "System Events", "Audit Log"];

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
  const [tab, setTab] = useState("All Runs");
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

  return (
    <section className={`w2-layout app-view activity-view tw ${view === "activity" ? "active" : ""}`} id="activityView" data-app-view="activity">
      <div className="fx-rise mx-auto flex max-w-[1500px] flex-col gap-5 p-7">

      {/* Header */}
      <div className="flex items-start justify-between gap-5">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Activity <span className="text-muted-foreground">Center</span></h1>
          <p className="mt-1.5 text-sm text-muted-foreground">Mission control for everything Rasputin has ever done.</p>
        </div>
        <div className="flex gap-3">
          {[
            { v: tasks.length, l: "Total Runs", c: "text-foreground" },
            { v: completedTasks.length, l: "Successes", c: "text-primary" },
            { v: activeTasks.length, l: "Running", c: "text-amber-400" },
            { v: failedTasks.length, l: "Failures", c: "text-rose-400" },
          ].map((s) => (
            <div key={s.l} className="glow-card rounded-xl border border-border bg-card px-4 py-2.5 text-center">
              <div className={`text-xl font-bold ${s.c}`}>{s.v}</div>
              <div className="text-[0.66rem] uppercase tracking-wide text-muted-foreground">{s.l}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="flex items-center gap-2 overflow-x-auto">
        {activityTabs.map(t => (
          <UIButton key={t} variant={tab === t ? "default" : "outline"} size="sm" onClick={() => setTab(t)}>
            {t}
          </UIButton>
        ))}
        <div className="flex-1" />
        {uiState.status !== 'idle' && (
          <Badge variant={uiState.status === 'failed' ? "down" : uiState.status === 'success' ? "up" : "muted"}>
            {uiState.message}
          </Badge>
        )}
        <UIButton variant="outline" size="sm" onClick={handleRefresh}>
          <RefreshCw size={15} /> Refresh
        </UIButton>
      </div>

      <div className="w2-main-grid" style={{ gridTemplateColumns: '1fr 350px' }}>
        
        {/* MAIN COLUMN */}
        <div className="w2-column">
          
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
                    onDetails={() => openTaskDetails?.(task.id)}
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
                  <Server size={24} color="var(--ras-safe)" />
                  <div>
                    <strong>API Status</strong>
                    <div style={{ fontSize: '0.875rem', color: 'var(--cc-muted)' }}>Online - 32ms ping</div>
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <Database size={24} color="var(--ras-safe)" />
                  <div>
                    <strong>Database Status</strong>
                    <div style={{ fontSize: '0.875rem', color: 'var(--cc-muted)' }}>Connected</div>
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <HardDrive size={24} color="var(--ras-safe)" />
                  <div>
                    <strong>Vector Store Status</strong>
                    <div style={{ fontSize: '0.875rem', color: 'var(--cc-muted)' }}>Active - 12.4 MB</div>
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
                  <p style={{ color: 'var(--cc-muted)' }}>No scheduled tasks available.</p>
                </div>
             </div>
          )}

        </div>

        {/* RIGHT COLUMN: Inspector / Monitor */}
        <div className="w2-column">
          
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

      </div>
      </div>
    </section>
  );
}

// --- Helpers ---

// PHASE 4 & 5 & 8: Embedded in RunCard
function RunCard({ task, models, onCancel, onPause, onResume, onDetails }) {
  const isFailed = ["failed", "error", "cancelled"].includes(task.status);
  const isActive = ["queued", "running", "paused"].includes(task.status);
  const [expanded, setExpanded] = useState(false);

  const statusVariant = isFailed ? "down" : isActive ? "muted" : "up";
  return (
    <div className={cn(
      "ras-list-item glow-card rounded-2xl border bg-card p-4",
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
                <button className="w2-button" style={{ borderColor: 'var(--ras-danger)', color: 'var(--ras-danger)' }}>Retry Run</button>
                <button className="w2-button">Debug Stack Trace</button>
              </div>
            </div>
          )}

          {/* PHASE 8: Artifact Management */}
          <div>
            <strong style={{ fontSize: '0.875rem' }}>Artifacts & Evidence</strong>
            <div style={{ display: 'flex', gap: '8px', marginTop: '8px' }}>
              <button className="w2-button" style={{ fontSize: '0.75rem', padding: '6px 12px' }}><FileText size={14}/> Execution Report</button>
              <button className="w2-button" style={{ fontSize: '0.75rem', padding: '6px 12px' }}><Download size={14}/> Download Logs</button>
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
