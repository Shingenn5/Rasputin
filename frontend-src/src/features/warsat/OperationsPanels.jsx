import { Database, RefreshCw } from "lucide-react";

import { displayWorkspaceName, labelize } from "../../lib/display.js";

import { taskStatusIcon, statusColor } from "./warsatPresentation.jsx";

export function TimelineTab({ tasks }) {
  const latestTasks = (tasks || []).slice(0, 10);
  return (
    <div className="w2-section" style={{ flex: 1 }}>
      <h2 style={{ margin: 0, fontSize: "1rem", marginBottom: "8px" }}>Execution Timeline</h2>
      {!latestTasks.length && <div style={{ padding: "32px", textAlign: "center", color: "var(--cc-muted)", backgroundColor: "var(--cc-surface)", borderRadius: "8px" }}>No activity recorded yet.</div>}
      <div style={{ display: "flex", flexDirection: "column", gap: "0" }}>
        {latestTasks.map((task, i) => (
          <div key={task.id} style={{ display: "flex", gap: "12px", padding: "12px 0", borderBottom: i < latestTasks.length - 1 ? "1px solid var(--cc-border)" : "none" }}>
            <div style={{ paddingTop: "2px" }}>{taskStatusIcon(task.status)}</div>
            <div>
              <div style={{ fontSize: "0.875rem", fontWeight: 500, color: "var(--cc-text)" }}>{task.objective || "Unnamed mission"}</div>
              <div style={{ fontSize: "0.75rem", color: "var(--cc-muted)", marginTop: "4px" }}>
                {labelize(task.status)} · {new Date(task.createdAt * 1000).toLocaleTimeString()} · {task.model}
              </div>
              {task.logs?.length > 0 && (
                <div style={{ fontSize: "0.6875rem", fontFamily: "monospace", color: "var(--cc-muted)", marginTop: "6px", background: "var(--cc-surface)", padding: "6px", borderRadius: "4px" }}>
                  {task.logs[task.logs.length - 1]}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function AgentsTab({ agentState }) {
  const agents = agentState?.tasks || [];
  return (
    <div className="w2-section" style={{ flex: 1 }}>
      <h2 style={{ margin: 0, fontSize: "1rem", marginBottom: "8px" }}>Active Agents ({agentState?.active_agents || 0})</h2>
      {!agents.length && <div style={{ padding: "32px", textAlign: "center", color: "var(--cc-muted)", backgroundColor: "var(--cc-surface)", borderRadius: "8px" }}>No agents currently active.</div>}
      {agents.map(agent => (
        <div key={agent.id} className="w2-card" style={{ gap: "8px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
              <Database size={16} color="var(--cc-accent)" />
              <div>
                <strong style={{ fontSize: "0.875rem" }}>{labelize(agent.skill || "general")} Agent</strong>
                <div style={{ fontSize: "0.6875rem", color: "var(--cc-muted)" }}>Workspace: {displayWorkspaceName(agent.workspace)}</div>
              </div>
            </div>
            <span style={{ fontSize: "0.6875rem", padding: "2px 10px", borderRadius: "999px", background: `color-mix(in srgb, ${statusColor(agent.status)} 15%, var(--cc-surface))`, color: statusColor(agent.status), fontWeight: 600 }}>
              {labelize(agent.status)}
            </span>
          </div>
          <div style={{ fontSize: "0.75rem", color: "var(--cc-text)" }}>Mission: {agent.objective}</div>
          <div style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>Model: {agent.model}</div>
        </div>
      ))}
    </div>
  );
}

export function TelemetryTab({ telemetry }) {
  if (!telemetry) return <div className="w2-section" style={{ flex: 1, padding: "32px", textAlign: "center", color: "var(--cc-muted)" }}>Connecting to telemetry...</div>;
  const { cpu, ram, disk, gpus } = telemetry;
  // API responses are camelized; accept legacy snake_case too.
  const gb = (o, key, alt) => o?.[key] ?? o?.[alt];

  return (
    <div className="w2-section" style={{ flex: 1 }}>
      <h2 style={{ margin: 0, fontSize: "1rem", marginBottom: "8px" }}>System Telemetry</h2>

      <div className="w2-card" style={{ gap: "12px" }}>
        <h3 style={{ margin: 0, fontSize: "0.875rem" }}>Host Resources</h3>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem", marginBottom: "4px" }}>
              <span>CPU Utilization</span>
              <strong>{cpu.percent}%</strong>
            </div>
            <div style={{ height: "6px", background: "var(--cc-border)", borderRadius: "3px", overflow: "hidden" }}>
              <div style={{ height: "100%", width: `${cpu.percent}%`, background: "var(--cc-accent)", transition: "width 0.5s ease" }} />
            </div>
          </div>

          <div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem", marginBottom: "4px" }}>
              <span>RAM ({gb(ram, "usedGb", "used_gb")} / {gb(ram, "totalGb", "total_gb")} GB)</span>
              <strong>{ram.percent}%</strong>
            </div>
            <div style={{ height: "6px", background: "var(--cc-border)", borderRadius: "3px", overflow: "hidden" }}>
              <div style={{ height: "100%", width: `${ram.percent}%`, background: "var(--ras-warn)", transition: "width 0.5s ease" }} />
            </div>
          </div>

          <div style={{ gridColumn: "1 / -1" }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem", marginBottom: "4px" }}>
              <span>Disk ({gb(disk, "usedGb", "used_gb")} / {gb(disk, "totalGb", "total_gb")} GB)</span>
              <strong>{disk.percent}%</strong>
            </div>
            <div style={{ height: "6px", background: "var(--cc-border)", borderRadius: "3px", overflow: "hidden" }}>
              <div style={{ height: "100%", width: `${disk.percent}%`, background: "var(--cc-muted)", transition: "width 0.5s ease" }} />
            </div>
          </div>
        </div>
      </div>

      {gpus && gpus.length > 0 && (
        <div className="w2-card" style={{ gap: "12px", marginTop: "16px" }}>
          <h3 style={{ margin: 0, fontSize: "0.875rem" }}>GPU Clusters</h3>
          {gpus.map(gpu => {
            const usedMb = gb(gpu, "memoryUsedMb", "memory_used_mb") || 0;
            const totalMb = gb(gpu, "memoryTotalMb", "memory_total_mb") || 0;
            const vramPct = totalMb ? Math.round((usedMb / totalMb) * 100) : 0;
            return (
            <div key={gpu.index} style={{ border: "1px solid var(--cc-border)", padding: "12px", borderRadius: "6px", display: "flex", flexDirection: "column", gap: "8px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <strong style={{ fontSize: "0.875rem" }}>GPU {gpu.index}: {gpu.name}</strong>
                <span style={{ fontSize: "0.75rem", color: "var(--cc-muted)", background: "var(--cc-surface)", padding: "2px 6px", borderRadius: "4px" }}>{gpu.temperature}°C</span>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", marginTop: "8px" }}>
                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem", marginBottom: "4px" }}>
                    <span>Compute</span>
                    <strong>{gpu.utilization}%</strong>
                  </div>
                  <div style={{ height: "6px", background: "var(--cc-border)", borderRadius: "3px", overflow: "hidden" }}>
                    <div style={{ height: "100%", width: `${gpu.utilization}%`, background: "var(--ras-danger)", transition: "width 0.5s ease" }} />
                  </div>
                </div>

                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem", marginBottom: "4px" }}>
                    <span>VRAM ({Math.round(usedMb / 1024 * 10)/10} / {Math.round(totalMb / 1024 * 10)/10} GB)</span>
                    <strong>{vramPct}%</strong>
                  </div>
                  <div style={{ height: "6px", background: "var(--cc-border)", borderRadius: "3px", overflow: "hidden" }}>
                    <div style={{ height: "100%", width: `${vramPct}%`, background: "var(--ras-safe)", transition: "width 0.5s ease" }} />
                  </div>
                </div>
              </div>
            </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export function QuickActionsPanel({ activeTab, handleRefresh, clearPlan, plan }) {
  return (
    <div className="w2-section">
      <h3 className="w2-section-title">Quick Actions</h3>
      <div className="w2-card" style={{ gap: "8px" }}>
        <button className="w2-button" type="button" onClick={handleRefresh} style={{ width: "100%" }}>
          <RefreshCw size={14} /> Refresh All
        </button>
        {plan && (
          <button className="w2-button" type="button" onClick={clearPlan} style={{ width: "100%" }}>
            Clear Plan
          </button>
        )}
      </div>
    </div>
  );
}
