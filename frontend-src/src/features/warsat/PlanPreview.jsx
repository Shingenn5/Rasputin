import { useState } from "react";
import { AlertTriangle, CheckCircle2, Play, RefreshCw, Server, ShieldCheck } from "lucide-react";

import { labelize } from "../../lib/display.js";

import { blockerGuidanceForReasons } from "../shared/blockerGuidance.js";
import { getWarsatGuidance } from "./warsatGuidance.js";
import { DownloadProgressPanel } from "./warsatPresentation.jsx";

export function EnableDockerButton({ enableDockerControl }) {
  const [busy, setBusy] = useState(false);
  if (!enableDockerControl) return null;

  async function handleClick() {
    const ok = window.confirm(
      "Enable Docker control?\n\nWarSat will be allowed to manage Docker containers on this machine (same as the toggle in Settings > Security)."
    );
    if (!ok) return;
    setBusy(true);
    try {
      await enableDockerControl();
    } finally {
      setBusy(false);
    }
  }

  return (
    <button
      className="w2-button primary"
      type="button"
      disabled={busy}
      onClick={handleClick}
      style={{ fontSize: "0.75rem", padding: "4px 10px", flexShrink: 0, marginLeft: "auto" }}
    >
      {busy ? <RefreshCw size={12} className="ws-spin" /> : <Server size={12} />}
      {busy ? "Enabling..." : "Enable Docker Control"}
    </button>
  );
}

export function PlanPreview({ plan, deployment, deploying, deployLabel, deployDisabled, canDeployPlan, deployPlan, approvalPending, approvalClosed, approvalStatus, currentApproval, approveApproval, denyApproval, lifecycle, enableDockerControl, downloadProgress, resourceAdmission, resourceAdmissionStatus, go }) {
  // Keep this component safe when a plan comes from an older backend response
  // or an embedded preview that does not include the derived admission props.
  // The plan is the source of truth; the props remain available for callers
  // that already derive the values in the parent.
  const admittedResource = resourceAdmission || plan?.resourceAdmission || null;
  const admittedResourceStatus = resourceAdmissionStatus || admittedResource?.status || "unmeasured";
  const isLocalhost = plan.securityChecks?.localhostOnly;
  const deployFailed = deployment?.status === "failed";
  const deployDone = deployment?.status === "registered";
  // The docker banners below supersede the backend's plain-text warnings
  // about the same conditions.
  const dockerReady = plan.dockerControlEnabled && plan.dockerCliAvailable;
  const planWarnings = (plan.warnings || []).filter(
    (w) => dockerReady || !w.startsWith("Docker control is")
  );
  const guidance = getWarsatGuidance({
    resource: admittedResource,
    plan,
    deployment,
    lifecycle,
    approvalPending,
    downloadProgress,
  });
  const deploymentBlockerReasons = [
    ...(["blocked", "queued"].includes(admittedResourceStatus) ? (admittedResource?.reasons || []) : []),
    deployment?.lastError,
    !plan.dockerControlEnabled ? "Docker control is disabled." : null,
    !plan.dockerCliAvailable ? "Docker CLI access is unavailable." : null,
    approvalClosed ? "Approval expired or closed." : null,
    approvalPending ? "Approval required." : null,
  ].filter(Boolean);
  const deploymentBlockers = blockerGuidanceForReasons(deploymentBlockerReasons);
  const deploymentBlockersId = "warsat-deployment-blockers";

  return (
    <div className="ws-mission-brief">
      {/* Brief Header */}
      <div className="ws-brief-header">
        <div>
          <div className="ws-brief-label">Mission Brief</div>
          <h3 className="ws-brief-title">{plan.protocolName}</h3>
          <div className="ws-brief-subtitle">
            {plan.runtime} · port {plan.hostPort} · {plan.executionEnabled ? "Execution enabled" : "Plan only"}
          {plan.assistantRequestId && (
            <div className="ws-brief-subtitle" data-testid="warsat-assistant-request">
              Requested by Personal Assistant
            </div>
          )}
          </div>
        </div>
        <span className={`ws-binding-badge ${isLocalhost ? "is-safe" : "is-warn"}`}>
          {isLocalhost ? <ShieldCheck size={11} /> : <AlertTriangle size={11} />}
          {isLocalhost ? "localhost only" : "review binding"}
        </span>
      </div>

      {/* Spec Grid */}
      <div className="ws-brief-specs">
        <div className="ws-brief-spec">
          <span>Model</span>
          <strong>{plan.modelRef || plan.modelPath || "Not set"}</strong>
        </div>
        <div className="ws-brief-spec">
          <span>Container</span>
          <strong>{plan.containerName}</strong>
        </div>
        <div className="ws-brief-spec">
          <span>Endpoint</span>
          <strong>{plan.expectedModelRegistryEntry?.baseUrl || plan.endpoint}</strong>
        </div>
        <div className="ws-brief-spec">
          <span>Profile</span>
          <strong>{plan.resourceProfile?.label || plan.strengthProfile}</strong>
        </div>
        <div className="ws-brief-spec">
          <span>Context</span>
          <strong>
            {plan.tuning?.contextAuto
              ? "Auto-detect after load"
              : `${plan.tuning?.contextWindow || plan.tuning?.maxModelLen || "Provider default"} tokens`}
          </strong>
        </div>
      </div>

      {admittedResource && (
        <div
          className="ws-exec-warning"
          data-testid="warsat-resource-admission"
          style={{ flexWrap: "wrap" }}
        >
          {admittedResourceStatus === "ready"
            ? <ShieldCheck size={13} />
            : <AlertTriangle size={13} />}
          <span>
            Resource admission: <strong>{labelize(admittedResourceStatus)}</strong>
            {admittedResourceStatus === "unmeasured"
              ? " — supply a current hardware profile before treating this as a capacity-certified launch."
              : admittedResourceStatus === "ready"
                ? " — " + (admittedResource.placements?.map(item => item.deviceId + " " + item.vramMb + " MB").join(", ") || "placement selected") + "."
                : " — deployment remains locked until the admission decision is ready."}
          </span>
          {(admittedResource.reasons || []).length > 0 && (
            <small style={{ width: "100%", opacity: 0.82 }}>
              Reasons: {admittedResource.reasons.join(", ")}
            </small>
          )}
        </div>
      )}

      {guidance && (
        <div className="ws-next-action" data-testid="warsat-next-action" role="status">
          <div className="ws-next-action-heading"><ShieldCheck size={14} /> Plain-language next step</div>
          <div><strong>What happened:</strong> {guidance.happened}</div>
          <div><strong>What to do next:</strong> {guidance.next}</div>
          {guidance.settings && go && (
            <button type="button" className="ws-next-action-link" onClick={() => go("settings", "models")}>
              Open Model Settings
            </button>
          )}
        </div>
      )}

      {/* Lifecycle progress rail */}
      {lifecycle.length > 0 && (
        <div className="ws-lifecycle-rail">
          {lifecycle.map(phase => {
            const st = phase.status || "pending";
            return (
              <div key={phase.id} className={`ws-lifecycle-step is-${st}`}>
                <div className="ws-lifecycle-dot" />
                <div className="ws-lifecycle-body">
                  <strong>{phase.label || labelize(phase.id)}</strong>
                  {phase.message && <span>{phase.message}</span>}
                </div>
              </div>
            );
          })}
        </div>
      )}

      <DownloadProgressPanel progress={downloadProgress} />

      {/* Docker command preview */}
      {plan.dockerRun && (
        <div className="ws-docker-cmd">
          <div className="ws-docker-cmd-label"><Server size={11} /> docker run command</div>
          <pre>{plan.dockerRun}</pre>
        </div>
      )}

      {/* Docker control gate — offer the fix inline instead of sending the
          user to Settings > Security */}
      {!plan.dockerControlEnabled && (
        <div className="ws-exec-warning">
          <AlertTriangle size={13} />
          <span>Docker control is off, so this plan cannot launch a container yet.</span>
          <EnableDockerButton enableDockerControl={enableDockerControl} />
        </div>
      )}
      {plan.dockerControlEnabled && !plan.dockerCliAvailable && (
        <div className="ws-exec-warning" style={{ flexWrap: "wrap" }}>
          <AlertTriangle size={13} />
          <span>
            Docker control is on, but this Rasputin container was started without Docker CLI
            access, so deploys will fail. Restart the stack with the docker-control overlay:
          </span>
          <pre style={{ width: "100%", margin: 0, padding: "8px 10px", borderRadius: "6px", background: "var(--cc-surface)", fontSize: "0.6875rem", overflowX: "auto" }}>
            docker compose -f docker-compose.yml -f docker-compose.docker-control.yml up --build -d
          </pre>
        </div>
      )}

      {/* Warnings */}
      {planWarnings.length > 0 && (
        <div className="ws-brief-warnings">
          {planWarnings.map((w, i) => (
            <div key={i} className="ws-brief-warning">
              <AlertTriangle size={12} /> {w}
            </div>
          ))}
        </div>
      )}

      {/* Action zone */}
      {deployDisabled && deploymentBlockers.length > 0 && (
        <div id={deploymentBlockersId} data-testid="warsat-deployment-blockers" role="alert" className="ws-brief-warnings">
          <strong>Deployment blocked — how to fix it</strong>
          {deploymentBlockers.map((entry) => (
            <div key={entry.raw} className="ws-brief-warning">
              <AlertTriangle size={12} />
              <span><strong>Reason:</strong> {entry.raw}<br /><strong>What this means:</strong> {entry.happened}<br /><strong>Next step:</strong> {entry.next}</span>
            </div>
          ))}
        </div>
      )}
      <div className="ws-brief-actions">
        {approvalPending && currentApproval?.id && (
          <>
            <button className="ws-brief-btn is-approve" type="button" onClick={() => approveApproval?.(currentApproval.id)}>
              <CheckCircle2 size={14} /> Approve
            </button>
            <button className="ws-brief-btn is-deny" type="button" onClick={() => denyApproval?.(currentApproval.id)}>
              Deny
            </button>
          </>
        )}
        <button
          className={`ws-brief-btn ${canDeployPlan ? "is-deploy" : ""} ${deploying ? "is-loading" : ""}`}
          type="button"
          disabled={deployDisabled}
          aria-describedby={deployDisabled && deploymentBlockers.length > 0 ? deploymentBlockersId : undefined}
          onClick={deployPlan}
        >
          {deploying ? <RefreshCw size={14} className="ws-spin" /> : <Play size={14} />}
          {deployLabel}
        </button>
      </div>

      {/* Result banner */}
      {deployment && (
        <div className={`ws-deploy-result ${deployFailed ? "is-fail" : deployDone ? "is-done" : "is-info"}`}>
          {deployFailed ? <AlertTriangle size={14} /> : <CheckCircle2 size={14} />}
          <div>
            <strong>{deployFailed ? "Deployment failed" : deployDone ? "Model registered" : "Deploy updated"}</strong>
            {deployment.lastError && <div className="ws-result-detail">{deployment.lastError}</div>}
            {deployment.endpoint && <div className="ws-result-detail">Endpoint: {deployment.endpoint}</div>}
          </div>
        </div>
      )}
    </div>
  );
}
