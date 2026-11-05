import React from "react";
import { Cpu, Gauge, MemoryStick, X, Move, Maximize2, Minimize2, RotateCcw } from "lucide-react";
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
  const [expanded, setExpanded] = React.useState(false);
  const dragRef = React.useRef(null);
  const [position, setPosition] = React.useState(() => {
    try {
      const saved = JSON.parse(localStorage.getItem("rasputin-system-status-position") || "null");
      return Number.isFinite(saved?.x) && Number.isFinite(saved?.y) ? saved : null;
    } catch { return null; }
  });
  const moveHelpId = React.useId();
  const clampPosition = (x, y) => {
    const rect = popupRef.current.getBoundingClientRect();
    return {
      x: Math.max(8, Math.min(x, window.innerWidth - rect.width - 8)),
      y: Math.max(8, Math.min(y, window.innerHeight - rect.height - 8)),
    };
  };
  React.useEffect(() => {
    try {
      if (position) localStorage.setItem("rasputin-system-status-position", JSON.stringify(position));
      else localStorage.removeItem("rasputin-system-status-position");
    } catch { /* Position persistence is optional. */ }
  }, [position]);
  React.useLayoutEffect(() => {
    if (!open || expanded) return undefined;
    const constrain = () => {
      const rect = popupRef.current.getBoundingClientRect();
      const next = clampPosition(rect.left, rect.top);
      if (next.x !== rect.left || next.y !== rect.top) setPosition(next);
    };
    constrain();
    window.addEventListener("resize", constrain);
    return () => window.removeEventListener("resize", constrain);
  }, [open, expanded]);

  function startMove(event) {
    if (event.button !== 0 || expanded) return;
    const rect = popupRef.current.getBoundingClientRect();
    dragRef.current = { x: rect.left, y: rect.top, pointerX: event.clientX, pointerY: event.clientY };
    event.currentTarget.setPointerCapture(event.pointerId);
    event.currentTarget.focus();
    event.preventDefault();
  }
  function move(event) {
    const drag = dragRef.current;
    if (drag) setPosition(clampPosition(drag.x + event.clientX - drag.pointerX, drag.y + event.clientY - drag.pointerY));
  }
  function moveWithKeyboard(event) {
    if (event.key === "Home") { event.preventDefault(); setPosition(null); return; }
    const delta = { ArrowLeft: [-24, 0], ArrowRight: [24, 0], ArrowUp: [0, -24], ArrowDown: [0, 24] }[event.key];
    if (!delta) return;
    event.preventDefault();
    const rect = popupRef.current.getBoundingClientRect();
    setPosition(clampPosition(rect.left + delta[0], rect.top + delta[1]));
  }

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
    && (isManagedModelRunning(model) || ["reachable", "starting"].includes(runtimeStatus(model)) || model.lastLoadFailure || model.last_load_failure));

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
        className={`system-status-popup${expanded ? " is-expanded" : ""}`}
        style={!expanded && position ? { inset: `${position.y}px auto auto ${position.x}px` } : undefined}
        data-testid="hardware-monitor"
        role="dialog"
        aria-label="System status"
      >
        <header className="system-status-heading">
          <strong>System status</strong>
          <span id={moveHelpId} className="sr-only">Drag to move, or use arrow keys while this handle is focused. Home resets the position.</span>
          <button type="button" className="system-status-move" aria-label="Move system status" aria-describedby={moveHelpId}
            title="Drag to move, or use arrow keys" disabled={expanded} onPointerDown={startMove} onPointerMove={move}
            onPointerUp={() => { dragRef.current = null; }} onPointerCancel={() => { dragRef.current = null; }} onKeyDown={moveWithKeyboard}><Move size={16} aria-hidden="true" /></button>
          <button type="button" aria-label={expanded ? "Restore system status size" : "Expand system status"} aria-expanded={expanded}
            onClick={() => setExpanded((value) => !value)}>{expanded ? <Minimize2 size={16} aria-hidden="true" /> : <Maximize2 size={16} aria-hidden="true" />}</button>
          <button type="button" aria-label="Reset system status position" onClick={() => { setPosition(null); setExpanded(false); }}><RotateCcw size={16} aria-hidden="true" /></button>
          <button type="button" popovertarget={popupId} popovertargetaction="hide" aria-label="Close system status" autoFocus><X size={16} aria-hidden="true" /></button>
        </header>
        <section className="system-status-models" aria-label="Local models" aria-live="polite">
          <span className="system-status-label">Local model{loadedModels.length > 1 ? "s" : ""}</span>
          {loadedModels.length ? loadedModels.map((model) => (
            <div key={model.key} className="system-status-model" data-testid="system-status-model">
              <strong>{displayModelName(model)}</strong>
              <small>{runtimeStatus(model) === "starting" ? "Loading" : runtimeStatus(model) === "reachable" ? "Ready"
                : model.lastLoadFailure || model.last_load_failure ? "Couldn't load" : "Running · health check pending"}</small>
              {runtimeStatus(model) !== "starting" && (model.lastLoadFailure || model.last_load_failure) && <small role="alert">{(model.lastLoadFailure || model.last_load_failure).message}</small>}
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
