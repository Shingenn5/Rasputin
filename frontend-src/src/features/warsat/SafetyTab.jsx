import { AlertTriangle, Cloud, Gauge, Lock, RefreshCw, Server, ShieldCheck, Unlock, Zap } from "lucide-react";

import { displayWorkspaceName } from "../../lib/display.js";

import { statusColor } from "./warsatPresentation.jsx";

export function SafetyTab({ security, warsat, hardware, pendingApprovals, approveApproval, denyApproval, handleRefresh }) {
  const checks = hardware?.checks || [];
  const detected = hardware?.detectedHardware || {};

  return (
    <div className="w2-section" style={{ flex: 1 }}>
      {/* Offline status */}
      <div className="w2-card">
        <h3 style={{ margin: 0, fontSize: "0.875rem" }}><ShieldCheck size={14} style={{ verticalAlign: "-2px" }} /> Local-Only Safety Lock</h3>
        <div className="w2-health-grid">
          <div className={`w2-health-item ${security?.privacyLock ? "is-good" : "is-warn"}`}>
            {security?.privacyLock ? <Lock size={14} /> : <Unlock size={14} />}
            Privacy: {security?.privacyLock ? "Locked" : "Unlocked"}
          </div>
          <div className={`w2-health-item ${!security?.allowRemoteModels ? "is-good" : "is-warn"}`}>
            <Cloud size={14} />
            Remote models: {security?.allowRemoteModels ? "Allowed" : "Blocked"}
          </div>
          <div className={`w2-health-item ${warsat?.dockerControlEnabled ? "is-good" : ""}`}>
            <Server size={14} />
            Docker: {warsat?.dockerControlEnabled ? "Enabled" : "Off"}
          </div>
          <div className={`w2-health-item ${warsat?.executionEnabled ? "is-good" : ""}`}>
            <Zap size={14} />
            Execution: {warsat?.executionEnabled ? "Enabled" : "Plan only"}
          </div>
        </div>
      </div>

      {/* System readiness */}
      {hardware && (
        <div className="w2-card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <h3 style={{ margin: 0, fontSize: "0.875rem" }}><Gauge size={14} style={{ verticalAlign: "-2px" }} /> System Readiness</h3>
            <button className="w2-button" type="button" onClick={handleRefresh} style={{ fontSize: "0.75rem", padding: "4px 10px" }}>
              <RefreshCw size={12} /> Refresh
            </button>
          </div>
          {checks.map(check => (
            <div key={check.id} style={{ display: "flex", gap: "8px", alignItems: "flex-start", fontSize: "0.75rem" }}>
              <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: statusColor(check.status), flexShrink: 0, marginTop: "5px" }} />
              <div>
                <strong>{check.label}</strong>
                <div style={{ color: "var(--cc-muted)" }}>{check.message}</div>
                {check.nextStep && <div style={{ color: "var(--ras-warn)", fontSize: "0.6875rem" }}>{check.nextStep}</div>}
              </div>
            </div>
          ))}
          <div style={{ display: "flex", gap: "16px", fontSize: "0.75rem", color: "var(--cc-muted)" }}>
            <span>Docker: {detected.dockerServerVersion || "not detected"}</span>
            <span>GPUs: {(detected.gpus || []).length}</span>
            <span>Runtimes: {(detected.dockerRuntimes || []).join(", ") || "none"}</span>
          </div>
        </div>
      )}

      {/* Pending approvals */}
      {pendingApprovals.length > 0 && (
        <div className="w2-card">
          <h3 style={{ margin: 0, fontSize: "0.875rem" }}><AlertTriangle size={14} style={{ verticalAlign: "-2px", color: "var(--ras-warn)" }} /> Pending Approvals ({pendingApprovals.length})</h3>
          {pendingApprovals.map(approval => (
            <div key={approval.id} className="w2-list-item" style={{ cursor: "default" }}>
              <div>
                <strong style={{ fontSize: "0.8125rem" }}>{approval.summary}</strong>
                <div style={{ fontSize: "0.6875rem", color: "var(--cc-muted)" }}>
                  Code {approval.code} · {approval.actionType || approval.action_type} · {displayWorkspaceName(approval.workspace)}
                </div>
              </div>
              <div style={{ display: "flex", gap: "6px" }}>
                <button className="w2-button primary" type="button" onClick={() => approveApproval(approval.id)} style={{ fontSize: "0.75rem", padding: "4px 10px" }}>
                  Approve
                </button>
                <button className="w2-button" type="button" onClick={() => denyApproval(approval.id)} style={{ fontSize: "0.75rem", padding: "4px 10px", color: "var(--ras-danger)" }}>
                  Deny
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function SafetyLockPanel({ security, warsat, hardware }) {
  const gpus = hardware?.detectedHardware?.gpus || [];
  return (
    <div className="w2-section">
      <h3 className="w2-section-title">Safety Status</h3>
      <div className="w2-card">
        <div style={{ display: "flex", flexDirection: "column", gap: "8px", fontSize: "0.75rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span>Privacy Lock</span>
            <strong style={{ color: security?.privacyLock ? "var(--ras-safe)" : "var(--ras-warn)" }}>
              {security?.privacyLock ? "LOCKED" : "OPEN"}
            </strong>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span>Remote Models</span>
            <strong style={{ color: !security?.allowRemoteModels ? "var(--ras-safe)" : "var(--ras-warn)" }}>
              {security?.allowRemoteModels ? "ALLOWED" : "BLOCKED"}
            </strong>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span>Docker Control</span>
            <strong>{warsat?.dockerControlEnabled ? "ON" : "OFF"}</strong>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span>Execution</span>
            <strong>{warsat?.executionEnabled ? "ENABLED" : "PLAN ONLY"}</strong>
          </div>
        </div>
      </div>

      {gpus.length > 0 && (
        <>
          <h3 className="w2-section-title">GPU Hardware</h3>
          <div className="w2-card">
            {gpus.map((gpu, i) => {
              const vramMb = gpu.memoryTotalMb || gpu.memory_total_mb;
              return (
                <div key={i} style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>
                  <strong style={{ color: "var(--cc-text)" }}>{gpu.name}</strong>
                  <div>{vramMb ? `${(vramMb / 1024).toFixed(1)} GB VRAM` : "Unknown VRAM"}</div>
                </div>
              );
            })}
          </div>
        </>
      )}

      <h3 className="w2-section-title">Offline Assurance</h3>
      <div className="w2-card">
        <div style={{ fontSize: "0.75rem", color: "var(--cc-muted)", display: "flex", flexDirection: "column", gap: "4px" }}>
          <span>• All data stays on this machine</span>
          <span>• Model inference runs locally</span>
          <span>• No telemetry, no cloud sync</span>
          <span>• Approval gates all risky actions</span>
          <span>• Privacy lock blocks remote endpoints</span>
        </div>
      </div>
    </div>
  );
}
