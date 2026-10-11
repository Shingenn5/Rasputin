import { useState, useEffect } from "react";
import { AlertTriangle, CheckCircle2, Cpu, Eye, MonitorSpeaker, Package, Play, Power, RefreshCw, Search, Server } from "lucide-react";

import { labelize } from "../../lib/display.js";

import { api, postJson } from "../../api/client.js";

import { EnableDockerButton } from "./PlanPreview.jsx";
import { DownloadProgressPanel } from "./warsatPresentation.jsx";

export function ContainersTab({ containers, runtimes, logs, handleLoadLogs, handleRuntimeAction, operation, approvals, handleRefresh, enableDockerControl, loadModels, go }) {
  const [activeLogContainer, setActiveLogContainer] = useState(null);
  const [discovering, setDiscovering] = useState(false);
  const [discovered, setDiscovered] = useState(null);
  const [importingKey, setImportingKey] = useState(null);
  const [importedKeys, setImportedKeys] = useState(new Set());
  const [downloadProgress, setDownloadProgress] = useState({});
  const operationApproval = (approvals?.approvals || []).find(a => a.id === (operation?.approval?.id || operation?.approvalId)) || operation?.approval;

  // status is raw docker text ("Up 50 seconds"); state is the normalized flag.
  const isUp = (c) => ["running", "healthy", "reachable"].includes(c.state || "") || (c.status || "").toLowerCase().startsWith("up");
  const running = containers.filter(isUp);
  const stopped = containers.filter(c => !isUp(c));
  const runningNamesKey = running.map(container => container.name).filter(Boolean).sort().join("|");

  useEffect(() => {
    const names = runningNamesKey ? runningNamesKey.split("|") : [];
    if (!names.length) {
      setDownloadProgress({});
      return undefined;
    }
    let isSubscribed = true;
    let timer = null;
    async function poll() {
      const entries = await Promise.all(names.map(async name => {
        try {
          return [name, await api(`/api/warsat/download-progress?containerName=${encodeURIComponent(name)}`)];
        } catch (err) {
          return [name, null];
        }
      }));
      if (isSubscribed) {
        setDownloadProgress(Object.fromEntries(entries.filter(([, progress]) => progress)));
      }
      if (isSubscribed) timer = setTimeout(poll, 5000);
    }
    poll();
    return () => {
      isSubscribed = false;
      if (timer) clearTimeout(timer);
    };
  }, [runningNamesKey]);

  function toggleLogs(name) {
    if (activeLogContainer === name) {
      setActiveLogContainer(null);
    } else {
      setActiveLogContainer(name);
      handleLoadLogs(name);
    }
  }

  async function runDiscover() {
    setDiscovering(true);
    setDiscovered(null);
    try {
      const res = await api("/api/warsat/discover");
      setDiscovered(res);
    } catch (err) {
      setDiscovered({ error: err.message || "Discovery failed", discovered: [] });
    } finally {
      setDiscovering(false);
    }
  }

  async function importModel(item) {
    const k = `${item.containerName}::${item.modelId}`;
    setImportingKey(k);
    try {
      await postJson("/api/warsat/import-discovered", {
        modelId: item.modelId,
        baseUrl: item.baseUrl,
        containerName: item.containerName,
        protocolHint: item.protocolHint,
      });
      setImportedKeys(prev => new Set([...prev, k]));
      await loadModels?.();
      // Navigate to chat — give the user 400ms to see the success state
      setTimeout(() => go?.("home"), 400);
    } catch (err) {
      alert(`Import failed: ${err.message}`);
    } finally {
      setImportingKey(null);
    }
  }

  return (
    <div className="w2-section" style={{ flex: 1 }}>

      {/* Discover panel */}
      <div className="ws-discover-panel">
        <div className="ws-discover-header">
          <div className="ws-discover-title">
            <Search size={14} />
            <span>Model Discovery</span>
            <span className="ws-discover-hint">Find AI models running in Docker on this machine</span>
          </div>
          <button
            className={`w2-button primary ${discovering ? "is-loading" : ""}`}
            type="button"
            onClick={runDiscover}
            disabled={discovering}
          >
            {discovering ? <RefreshCw size={13} className="ws-spin" /> : <Search size={13} />}
            {discovering ? "Scanning..." : "Scan for Models"}
          </button>
        </div>

        {discovered && (
          <div className="ws-discover-results">
            {discovered.error && (
              <div className="ws-exec-warning"><AlertTriangle size={13} /> {discovered.error}</div>
            )}
            {!discovered.error && (discovered.discovered || []).length === 0 && (
              <div className="ws-discover-empty">
                No unregistered AI model endpoints found. If a model is running,
                make sure Docker control is enabled and its port is exposed.
              </div>
            )}
            {(discovered.discovered || []).map(item => {
              const k = `${item.containerName}::${item.modelId}`;
              const imported = importedKeys.has(k);
              const loading = importingKey === k;
              return (
                <div key={k} className="ws-discover-card">
                  <div className="ws-discover-card-left">
                    <span className="ws-status-pulse is-running" />
                    <div>
                      <div className="ws-discover-model-id">{item.modelId}</div>
                      <div className="ws-discover-meta">
                        <span><Server size={10} /> {item.containerName}</span>
                        <span><MonitorSpeaker size={10} /> {item.baseUrl}</span>
                        <span className="ws-protocol-badge">{item.protocolHint}</span>
                      </div>
                    </div>
                  </div>
                  <button
                    className={`ws-brief-btn ${imported ? "" : "is-deploy"}`}
                    type="button"
                    disabled={imported || loading}
                    onClick={() => importModel(item)}
                    style={{ fontSize: "0.8125rem", padding: "7px 14px" }}
                  >
                    {loading ? <RefreshCw size={12} className="ws-spin" /> : imported ? <CheckCircle2 size={12} /> : <Play size={12} />}
                    {loading ? "Importing..." : imported ? "Added — Starting chat…" : "Add to Chat"}
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Summary banner */}
      <div className="ws-runtime-banner">
        <div className="ws-runtime-banner-stat">
          <span className="ws-status-pulse is-running" />
          <strong style={{ color: "var(--ras-safe)" }}>{running.length}</strong>
          <span>Running</span>
        </div>
        <div className="ws-runtime-banner-stat">
          <span className="ws-status-pulse is-stopped" />
          <strong>{stopped.length}</strong>
          <span>Stopped</span>
        </div>
        <div className="ws-runtime-banner-stat">
          <Server size={13} color="var(--cc-muted)" />
          <strong>{containers.length}</strong>
          <span>Total</span>
        </div>
        <div style={{ flex: 1 }} />
        <button className="w2-button" type="button" onClick={handleRefresh} style={{ fontSize: "0.75rem", padding: "4px 10px" }}>
          <RefreshCw size={12} /> Refresh
        </button>
      </div>

      {/* Execution disabled warning — runtimes reports `enabled`, and when it
          is true the message is informational, not a warning */}
      {runtimes && runtimes.enabled === false && (
        <div className="ws-exec-warning">
          <AlertTriangle size={13} />
          <span>{runtimes?.message || "Docker control is off, so WarSat cannot manage containers."}</span>
          {!runtimes?.dockerControlEnabled && (
            <EnableDockerButton enableDockerControl={enableDockerControl} />
          )}
        </div>
      )}

      {/* Container cards */}
      {containers.map(container => {
        const st = container.status || container.state || "unknown";
        const isRunning = isUp(container);
        const isLogOpen = activeLogContainer === container.name;
        const logsForThis = logs?.containerName === container.name ? logs : null;

        /* Parse port string into clickable links */
        const portMatches = (container.ports || "").match(/(\d+\.\d+\.\d+\.\d+):(\d+)/g) || [];
        const localPort = portMatches.map(p => p.split(":")[1]).find(Boolean);

        return (
          <div key={container.name || container.id} className={`ws-runtime-card ${isRunning ? "is-running" : "is-stopped"}`}>
            {/* Card header */}
            <div className="ws-runtime-card-head">
              <div className="ws-runtime-status-wrap">
                <span className={`ws-status-pulse ${isRunning ? "is-running" : "is-stopped"}`} />
                <div>
                  <div className="ws-runtime-name">{container.name || "Unnamed container"}</div>
                  <div className="ws-runtime-image">{container.image || "Unknown image"}</div>
                </div>
              </div>
              <div className="ws-runtime-badges">
                {container.protocolId && (
                  <span className="ws-protocol-badge">{container.protocolId}</span>
                )}
                <span className={`ws-status-badge is-${st}`}>{labelize(st)}</span>
              </div>
            </div>

            {/* Meta row */}
            <div className="ws-runtime-meta">
              {container.runtime && <span><Cpu size={11} /> {container.runtime}</span>}
              {localPort && (
                <a
                  href={`http://127.0.0.1:${localPort}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="ws-runtime-endpoint"
                >
                  <MonitorSpeaker size={11} /> 127.0.0.1:{localPort}
                </a>
              )}
              {!localPort && container.ports && (
                <span><Package size={11} /> {container.ports}</span>
              )}
            </div>

            <DownloadProgressPanel progress={downloadProgress[container.name]} compact />

            {/* Actions */}
            <div className="ws-runtime-actions">
              <button
                className={`ws-runtime-btn ${isLogOpen ? "is-active" : ""}`}
                type="button"
                onClick={() => toggleLogs(container.name)}
              >
                <Eye size={12} /> Logs
              </button>
              <button
                className="ws-runtime-btn"
                type="button"
                onClick={() => handleRuntimeAction("restart", container.name)}
              >
                {isRunning ? <RefreshCw size={12} /> : <Play size={12} />}
                {isRunning ? "Restart" : "Start"}
              </button>
              {isRunning && (
                <button
                  className="ws-runtime-btn is-danger"
                  type="button"
                  onClick={() => handleRuntimeAction("stop", container.name)}
                >
                  <Power size={12} /> Stop
                </button>
              )}
            </div>

            {/* Inline log panel */}
            {isLogOpen && (
              <div className="ws-log-panel">
                <div className="ws-log-header">
                  <span><Eye size={11} /> {container.name} — stdout / stderr</span>
                  <button type="button" className="ws-log-close" onClick={() => setActiveLogContainer(null)}>✕</button>
                </div>
                <pre className="ws-log-body">
                  {logsForThis ? (logsForThis.logs || "No log output.") : "Loading..."}
                </pre>
              </div>
            )}
          </div>
        );
      })}

      {/* Empty state */}
      {!containers.length && (
        <div className="ws-empty-state">
          <Server size={32} color="var(--cc-border)" />
          <strong>No managed containers</strong>
          <span>Deploy a model from the Deploy tab to spin up a container here.</span>
        </div>
      )}
    </div>
  );
}
