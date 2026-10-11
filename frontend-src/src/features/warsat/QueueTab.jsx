import { useState, useMemo } from "react";
import { Pause, Play, Square } from "lucide-react";

import { displayModelName, displayWorkspaceName, labelize } from "../../lib/display.js";

import { taskStatusIcon, statusColor } from "./warsatPresentation.jsx";

export function QueueTab({ tasks, activeTasks, failedTasks, models, handleCancel, handlePause, handleResume }) {
  const [filter, setFilter] = useState("active");
  const displayTasks = useMemo(() => {
    if (filter === "active") return activeTasks;
    if (filter === "failed") return failedTasks;
    return tasks;
  }, [filter, tasks, activeTasks, failedTasks]);

  return (
    <div className="w2-section" style={{ flex: 1 }}>
      <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
        <h2 style={{ margin: 0, fontSize: "1rem" }}>Mission Queue</h2>
        <div style={{ flex: 1 }} />
        <button className={`w2-button ${filter === "active" ? "primary" : ""}`} type="button" onClick={() => setFilter("active")} style={{ fontSize: "0.75rem", padding: "4px 10px" }}>
          Active ({activeTasks.length})
        </button>
        <button className={`w2-button ${filter === "failed" ? "primary" : ""}`} type="button" onClick={() => setFilter("failed")} style={{ fontSize: "0.75rem", padding: "4px 10px" }}>
          Failed ({failedTasks.length})
        </button>
        <button className={`w2-button ${filter === "all" ? "primary" : ""}`} type="button" onClick={() => setFilter("all")} style={{ fontSize: "0.75rem", padding: "4px 10px" }}>
          All ({tasks.length})
        </button>
      </div>

      {displayTasks.map(task => (
        <div key={task.id} className="w2-card" style={{ gap: "8px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
              {taskStatusIcon(task.status)}
              <div>
                <strong style={{ fontSize: "0.875rem" }}>{task.objective || task.id}</strong>
                <div style={{ fontSize: "0.6875rem", color: "var(--cc-muted)" }}>
                  {task.workspace ? displayWorkspaceName(task.workspace) : ""}{task.workspace && task.mode ? " · " : ""}{task.mode ? labelize(task.mode) : ""}
                </div>
              </div>
            </div>
            <span style={{ fontSize: "0.6875rem", padding: "2px 10px", borderRadius: "999px", background: `color-mix(in srgb, ${statusColor(task.status)} 15%, var(--cc-surface))`, color: statusColor(task.status), fontWeight: 600 }}>
              {labelize(task.status)}
            </span>
          </div>

          {task.model && (
            <div style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>
              Model: {displayModelName(task.model, models)}
            </div>
          )}

          <div style={{ display: "flex", gap: "8px" }}>
            {task.status === "running" && (
              <button className="w2-button" type="button" onClick={() => handlePause(task.id)} style={{ fontSize: "0.75rem", padding: "4px 10px" }}>
                <Pause size={12} /> Pause
              </button>
            )}
            {task.status === "paused" && (
              <button className="w2-button primary" type="button" onClick={() => handleResume(task.id)} style={{ fontSize: "0.75rem", padding: "4px 10px" }}>
                <Play size={12} /> Resume
              </button>
            )}
            {["running", "queued", "paused"].includes(task.status) && (
              <button className="w2-button" type="button" onClick={() => handleCancel(task.id)} style={{ fontSize: "0.75rem", padding: "4px 10px", color: "var(--ras-danger)" }}>
                <Square size={12} /> Cancel
              </button>
            )}
          </div>
        </div>
      ))}

      {!displayTasks.length && (
        <div style={{ padding: "32px", textAlign: "center", color: "var(--cc-muted)", backgroundColor: "var(--cc-surface)", borderRadius: "8px" }}>
          {filter === "active" ? "No active missions. Start a task from chat or the planner." : filter === "failed" ? "No failed missions." : "No missions recorded yet."}
        </div>
      )}
    </div>
  );
}
