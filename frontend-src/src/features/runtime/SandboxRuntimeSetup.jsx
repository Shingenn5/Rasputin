import React, { useCallback, useEffect, useState } from "react";
import { api, postJson } from "../../api/client.js";
import { Button } from "../../components/ui/button.jsx";
import "./sandbox-review.css";

export function SandboxRuntimeSetup({ visible = true }) {
  const [runtime, setRuntime] = useState(null);
  const [capability, setCapability] = useState(null);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const refresh = useCallback(async () => {
    try {
      const [state, configuration] = await Promise.all([api("/api/execution/runtime"), api("/api/execution")]);
      setRuntime(state); setCapability(configuration); setError("");
    } catch (failure) { setError(failure.message); }
  }, []);
  useEffect(() => { if (visible) refresh(); }, [refresh, visible]);
  const active = runtime?.state === "installing" || runtime?.state === "stopping";
  useEffect(() => {
    if (!active || !visible) return;
    const timer = setInterval(refresh, 750);
    return () => clearInterval(timer);
  }, [active, refresh, visible]);

  async function install() {
    setSubmitting(true); setError("");
    try { setRuntime(await postJson("/api/execution/runtime/install", {})); }
    catch (failure) { setError(failure.message); }
    finally { setSubmitting(false); await refresh(); }
  }

  async function cancel() {
    try { setRuntime(await postJson("/api/execution/runtime/cancel", {})); }
    catch (failure) { setError(failure.message); }
  }

  const managed = runtime?.installed && capability?.available && capability?.toolchain?.managed;
  const needsRepair = capability?.toolchain?.managed && !runtime?.installed;
  const percent = runtime?.totalBytes ? Math.min(100, Math.floor((runtime.downloadedBytes || 0) * 100 / runtime.totalBytes)) : 0;
  return (
    <section className="sandbox-runtime-setup" aria-label="Sandbox runtime setup" data-testid="sandbox-runtime-setup">
      <div className="sandbox-review-heading">
        <h2>Sandbox runtime</h2>
        <Button type="button" variant="ghost" size="sm" onClick={refresh}>Refresh runtime</Button>
      </div>
      <p>A private runtime lets agents run approved snapshots. Rasputin sets it up for you; no separate developer installation is needed.</p>
      {error && <p role="alert" className="sandbox-review-error">{error}</p>}
      {runtime?.state === "error" && <p role="alert" className="sandbox-review-error">{runtime.message}</p>}
      {runtime && !runtime.supported && <p>{runtime.message}</p>}
      {runtime?.supported && <>
        <p role="status">{active ? runtime.state === "stopping" ? "Stopping runtime setup…" : "Downloading and verifying runtime…"
          : managed ? "Managed sandbox runtime ready."
            : needsRepair ? "Managed runtime files need repair."
              : capability?.available ? "A custom runtime is selected." : "Sandbox runtime is not set up yet."}</p>
        {runtime.state === "cancelled" && <p>{runtime.message}</p>}
        {active && <div className="sandbox-runtime-progress">
          <progress max="100" value={percent} aria-label="Runtime download progress" />
          <span>{percent}% · {((runtime.downloadedBytes || 0) / 1048576).toFixed(1)} MiB</span>
        </div>}
        <div className="sandbox-review-actions">
          {!active && <Button type="button" variant={managed ? "outline" : "default"} onClick={install}
            disabled={submitting || (runtime.offline && !runtime.installed)}>
            {submitting ? "Starting setup…" : managed ? "Verify runtime" : needsRepair ? "Repair sandbox runtime" : capability?.available ? "Use managed runtime" : "Set up sandbox runtime"}
          </Button>}
          {active && <Button type="button" variant="outline" onClick={cancel} disabled={runtime.state === "stopping"}>Cancel runtime setup</Button>}
        </div>
        {runtime.offline && !runtime.installed && <p>Offline mode blocks this download. Turn it off in <a href="#settings/security">Security settings</a>, then retry.</p>}
        {managed && !runtime.executionEnabled && <p>Execution is off. Enable Shell Execution in <a href="#settings/security">Security settings</a> to allow approved sandbox tasks.</p>}
        <details className="sandbox-review-identities">
          <summary>Runtime details</summary>
          <dl className="sandbox-review-facts">
            <dt>Runtime</dt><dd>Node.js {runtime.version} · {runtime.architecture}</dd>
            <dt>Download</dt><dd>{(runtime.totalBytes / 1048576).toFixed(1)} MiB from nodejs.org</dd>
            <dt>License</dt><dd>{runtime.license}</dd>
          </dl>
          <p>Files are verified before use and stay inside Rasputin. Pending snapshots made with a different runtime must be prepared again.</p>
        </details>
      </>}
    </section>
  );
}
