import React from "react";
import { Cpu, Gauge, MemoryStick } from "lucide-react";
import { api } from "../../api/client.js";

function numberOrNull(value) {
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

export function HardwareMonitor({ enabled = false, refreshIntervalMs = 2000 }) {
  const [telemetry, setTelemetry] = React.useState(null);
  const [error, setError] = React.useState("");

  React.useEffect(() => {
    if (!enabled) {
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
    const timer = window.setInterval(poll, interval);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [enabled, refreshIntervalMs]);

  if (!enabled) return null;

  const ram = telemetry?.ram || {};
  const gpus = Array.isArray(telemetry?.gpus) ? telemetry.gpus : [];
  const ramUsed = numberOrNull(ram.usedGb ?? ram.used_gb);
  const ramTotal = numberOrNull(ram.totalGb ?? ram.total_gb);

  return (
    <div
      className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-border bg-background/85 px-3 py-1.5 text-[0.68rem] text-muted-foreground backdrop-blur-sm"
      data-testid="hardware-monitor"
      role="status"
      aria-label="Live hardware usage"
    >
      <span className="inline-flex items-center gap-1 font-semibold text-foreground">
        <Gauge size={12} aria-hidden="true" />
        Hardware
      </span>
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
    </div>
  );
}
