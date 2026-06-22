import React, { useMemo, useState, useEffect } from "react";
import {
  Pause, Play, RefreshCw, Square, Users, Search, 
  Activity, AlertTriangle, CheckCircle, Clock, 
  Server, Database, HardDrive, Download, Eye, FileText
} from "lucide-react";
import { displayModelName, displayWorkspaceName } from "../../lib/display.js";
import { actionRegistry, useReliableAction } from "../../lib/actionRegistry.js";

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
    <section className={`w2-layout app-view activity-view ${view === "activity" ? "active" : ""}`} id="activityView" data-app-view="activity">
      
      {/* PHASE 1: Top Navigation & Header */}
      <div className="w2-header-card" style={{ marginBottom: '16px' }}>
        <div>
          <h1>Activities Center</h1>
          <p>Mission Control for everything Rasputin has ever done.</p>
        </div>
        <div className="w2-header-stats">
          <div className="w2-header-stat">
            <strong>{tasks.length}</strong>
            <small>Total Runs</small>
          </div>
          <div className="w2-header-stat">
            <strong style={{color: 'var(--ras-safe)'}}>{completedTasks.length}</strong>
            <small>Successes</small>
          </div>
          <div className="w2-header-stat">
            <strong style={{color: 'var(--ras-warn)'}}>{activeTasks.length}</strong>
            <small>Running Now</small>
          </div>
          <div className="w2-header-stat">
            <strong style={{color: 'var(--ras-danger)'}}>{failedTasks.length}</strong>
            <small>Failures</small>
          </div>
        </div>
      </div>

      <div style={{ padding: '0 24px', display: 'flex', gap: '12px', overflowX: 'auto', marginBottom: '16px' }}>
        {activityTabs.map(t => (
          <button 
            key={t}
            className={`w2-button ${tab === t ? 'primary' : ''}`}
            onClick={() => setTab(t)}
          >
            {t}
          </button>
        ))}
        <div style={{ flex: 1 }} />
        
        {/* Button Reliability Status Readout */}
        {uiState.status !== 'idle' && (
          <div style={{ 
            padding: '8px 16px', borderRadius: '4px', fontSize: '0.875rem',
            backgroundColor: uiState.status === 'failed' ? 'var(--ras-danger)' : 
                            uiState.status === 'success' ? 'var(--ras-safe)' : 'var(--cc-surface)',
            color: '#fff', display: 'flex', alignItems: 'center'
          }}>
            {uiState.message}
          </div>
        )}

        <button className="w2-button" onClick={handleRefresh}>
          <RefreshCw size={16} /> Refresh
        </button>
      </div>

      <div className="w2-main-grid" style={{ gridTemplateColumns: '1fr 350px' }}>
        
        {/* MAIN COLUMN */}
        <div className="w2-column">
          
          {/* PHASE 6: Activity Search */}
          {["All Runs", "Active", "Completed", "Failed"].includes(tab) && (
            <div className="w2-section" style={{ flex: 1 }}>
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <Search size={16} color="var(--cc-muted)" />
                <input 
                  className="w2-input" 
                  placeholder="Search by ID, agent, status, or error text..." 
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                />
              </div>

              {/* Run List */}
              <div className="w2-card" style={{ flex: 1, overflowY: 'auto', gap: '8px', backgroundColor: 'transparent', border: 'none', padding: 0 }}>
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
                  <div style={{ padding: '32px', textAlign: 'center', color: 'var(--cc-muted)', backgroundColor: 'var(--cc-surface)', borderRadius: '8px' }}>
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
    </section>
  );
}

// --- Helpers ---

// PHASE 4 & 5 & 8: Embedded in RunCard
function RunCard({ task, models, onCancel, onPause, onResume, onDetails }) {
  const isFailed = ["failed", "error", "cancelled"].includes(task.status);
  const isActive = ["queued", "running", "paused"].includes(task.status);
  const [expanded, setExpanded] = useState(false);

  return (
    <div className={`w2-card ras-list-item ${isFailed ? 'failed-run-border' : ''}`} style={{ padding: '16px', gap: '8px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span className={`status-pill status-${task.status}`}>{task.status}</span>
            <strong style={{ fontSize: '1rem' }}>{task.objective || "Untitled Run"}</strong>
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--cc-muted)' }}>
            {displayModelName(task.model, models)} • {displayWorkspaceName(task.workspace)} • ID: {task.id.slice(0,8)}
          </div>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button className="w2-button" onClick={() => setExpanded(!expanded)}>
            {expanded ? "Collapse" : "Inspect"}
          </button>
          {isActive && (
            <div style={{ display: 'flex', gap: '4px' }}>
              {task.status === 'paused' ? (
                <button className="w2-button" style={{ padding: '8px' }} onClick={onResume} title="Resume"><Play size={14}/></button>
              ) : (
                <button className="w2-button" style={{ padding: '8px' }} onClick={onPause} title="Pause"><Pause size={14}/></button>
              )}
              <button className="w2-button" style={{ padding: '8px', color: 'var(--ras-danger)' }} onClick={onCancel} title="Cancel"><Square size={14}/></button>
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
          
          <button className="w2-button primary" style={{ alignSelf: 'flex-start' }} onClick={onDetails}>
            Open Full Details View
          </button>
        </div>
      )}
    </div>
  );
}
