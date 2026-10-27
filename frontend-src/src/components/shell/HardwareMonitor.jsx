import React from "react";
import { Cpu, Gauge, MemoryStick, X } from "lucide-react";
import { api } from "../../api/client.js";
import { displayModelName, isManagedModelRunning, runtimeStatus } from "../../lib/display.js";
import "../../styles/system-status.css";

function numberOrNull(value) {
  if (value == null || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function formatGb(value) {
  const parsed = numberOrNull(value);
  return parsed == null ? "unknown" : `${parsed.toFixed(1)} GB`;
}

function formatPercent(value) {
  const parsed = numberOrNull(value);
  return parsed == null ? "--" : `${Math.round(parsed)}%`;
}

export function HardwareMonitor({ enabled = false, refreshIntervalMs = 2000, models = [] }) {
  const popupId = React.useId();
  const popupRef = React.useRef(null);
  const [open, setOpen] = React.useState(false);
  const [telemetry, setTelemetry] = React.useState(null);
  const [error, setError] = React.useState("");

  React.useEffect(() => {
    const popup = popupRef.current;
    const toggle = (event) => setOpen(event.newState === "open");
    popup.addEventListener("toggle", toggle);
    return () => popup.removeEventListener("toggle", toggle);
  }, []);

  React.useEffect(() => {
    if (!open) {
      setTelemetry(null);
      setError("");
      return undefined;
    }

    let active = true;
    const interval = Math.max(1000, Math.min(Number(refreshIntervalMs) || 2000, 10000));
    async function poll() {
      try {
        const next = await api("/api/warsat/system-metrics");
        if (!active) return;
        setTelemetry(next);
        setError("");
      } catch (requestError) {
        if (!active) return;
        setError(requestError?.message || "Hardware telemetry unavailable");
      }
    }

    poll();
    const timer = enabled ? window.setInterval(poll, interval) : null;
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [open, enabled, refreshIntervalMs]);

  const loadedModels = models.filter((model) => model.runtime !== "remote-api"
    && !["mock", "hash-vector"].includes(model.provider)
    && (isManagedModelRunning(model) || runtimeStatus(model) === "reachable"));

  const ram = telemetry?.ram || {};
  const gpus = Array.isArray(telemetry?.gpus) ? telemetry.gpus : [];
  const ramUsed = numberOrNull(ram.usedGb ?? ram.used_gb);
  const ramTotal = numberOrNull(ram.totalGb ?? ram.total_gb);

  return (
    <>
      <button type="button" className="system-status-trigger" popovertarget={popupId}
        aria-label="System status" aria-expanded={open} aria-controls={popupId} title="Hardware usage and loaded models" data-testid="system-status-trigger">
        <Gauge size={19} aria-hidden="true" />
      </button>
      <div ref={popupRef} id={popupId} popover="auto"
        className="system-status-popup"
        data-testid="hardware-monitor"
        role="dialog"
        aria-label="System status"
      >
        <header className="system-status-heading">
          <strong>System status</strong>
          <button type="button" popovertarget={popupId} popovertargetaction="hide" aria-label="Close system status" autoFocus><X size={16} aria-hidden="true" /></button>
        </header>
        <section className="system-status-models" aria-label="Loaded models">
          <span className="system-status-label">Loaded model{loadedModels.length > 1 ? "s" : ""}</span>
          {loadedModels.length ? loadedModels.map((model) => (
            <div key={model.key} className="system-status-model" data-testid="system-status-model">
              <strong>{displayModelName(model)}</strong>
              <small>{runtimeStatus(model) === "reachable" ? "Ready" : "Running · health check pending"}</small>
            </div>
          )) : <p>No model loaded</p>}
        </section>
        <section className="system-status-metrics" aria-label="Hardware usage">
          <span className="system-status-label">Hardware · {enabled ? "Live" : "Snapshot"}</span>
          <span className="inline-flex items-center gap-1" title="System RAM usage">
            <MemoryStick size={12} aria-hidden="true" />
            RAM {ramUsed == null || ramTotal == null ? "unknown" : `${formatGb(ramUsed)} / ${formatGb(ramTotal)}`}
          </span>
          <span className="inline-flex items-center gap-1" title="Host CPU usage">
            <Cpu size={12} aria-hidden="true" />
            CPU {formatPercent(telemetry?.cpu?.percent)}
          </span>
          {gpus.length > 0 ? gpus.map((gpu, index) => {
            const used = numberOrNull(gpu?.memoryUsedMb ?? gpu?.memory_used_mb);
            const total = numberOrNull(gpu?.memoryTotalMb ?? gpu?.memory_total_mb);
            const name = gpu?.name || `GPU ${gpu?.index ?? index}`;
            return (
              <span className="inline-flex items-center gap-1" key={`${gpu?.index ?? index}-${name}`} title={name}>
                <span aria-hidden="true">GPU</span>
                {gpu?.index ?? index} {used == null || total == null ? "VRAM unknown" : `${formatGb(used / 1024)} / ${formatGb(total / 1024)}`} {formatPercent(gpu?.utilization ?? gpu?.utilizationPct)}
              </span>
            );
          }) : (
            <span>GPU telemetry unavailable</span>
          )}
          {error && <span className="text-amber-600 dark:text-amber-300">{error}</span>}
        </section>
      </div>
    </>
  );
}
