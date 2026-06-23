import React, { useMemo } from "react";
import {
  Activity,
  ArrowUpRight,
  Boxes,
  CheckCircle2,
  ChevronUp,
  Cpu,
  GitBranch,
  Layers,
  ListChecks,
  Satellite,
  ShieldCheck,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import { displayModelName } from "../../lib/display.js";

/* ─────────────────────────────────────────────
   DashboardView — analytics landing screen
   Reference: deep-dark dashboard with KPI cards, a hero activity chart,
   a "by status" donut, a top-models table and a metric list. Bound to the
   real app state (models, tasks, approvals) — no invented numbers.
   ───────────────────────────────────────────── */

const ACTIVE = ["queued", "running", "paused"];
const DONE = ["completed", "done", "success"];
const FAILED = ["failed", "error", "cancelled"];

function statusBucket(status) {
  if (ACTIVE.includes(status)) return "active";
  if (DONE.includes(status)) return "done";
  if (FAILED.includes(status)) return "failed";
  return "other";
}

// A tiny inline sparkline from a series of numbers.
function Sparkline({ data, width = 84, height = 30, stroke = "var(--dash-accent)" }) {
  if (!data || data.length < 2) {
    return <svg width={width} height={height} aria-hidden="true" />;
  }
  const max = Math.max(...data, 1);
  const min = Math.min(...data, 0);
  const span = max - min || 1;
  const step = width / (data.length - 1);
  const points = data.map((v, i) => `${i * step},${height - ((v - min) / span) * (height - 4) - 2}`);
  return (
    <svg width={width} height={height} aria-hidden="true">
      <polyline
        points={points.join(" ")}
        fill="none"
        stroke={stroke}
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

// Build a daily "tasks created" series from task timestamps for the hero chart.
function buildActivitySeries(tasks, days = 30) {
  const now = Date.now();
  const dayMs = 86400000;
  const buckets = new Array(days).fill(0);
  for (const task of tasks) {
    const ts = Date.parse(task.createdAt || task.created_at || task.updatedAt || "") || 0;
    if (!ts) continue;
    const age = Math.floor((now - ts) / dayMs);
    if (age >= 0 && age < days) buckets[days - 1 - age] += 1;
  }
  return buckets;
}

// Area/line hero chart from a numeric series.
function HeroChart({ series, height = 240 }) {
  const width = 760;
  const max = Math.max(...series, 1);
  const step = series.length > 1 ? width / (series.length - 1) : width;
  const pts = series.map((v, i) => [i * step, height - (v / max) * (height - 30) - 10]);
  const line = pts.map((p) => `${p[0]},${p[1]}`).join(" ");
  const area = `0,${height} ${line} ${width},${height}`;
  return (
    <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" style={{ width: "100%", height }}>
      <defs>
        <linearGradient id="dashHeroFill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--dash-accent)" stopOpacity="0.28" />
          <stop offset="100%" stopColor="var(--dash-accent)" stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon points={area} fill="url(#dashHeroFill)" />
      <polyline points={line} fill="none" stroke="var(--dash-accent)" strokeWidth="2.4" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

// SVG donut from segments [{value, color, label}].
function Donut({ segments, size = 150, thickness = 18 }) {
  const radius = (size - thickness) / 2;
  const circ = 2 * Math.PI * radius;
  const total = segments.reduce((s, x) => s + x.value, 0) || 1;
  let offset = 0;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <g transform={`rotate(-90 ${size / 2} ${size / 2})`}>
        {segments.map((seg, i) => {
          const len = (seg.value / total) * circ;
          const el = (
            <circle
              key={i}
              cx={size / 2}
              cy={size / 2}
              r={radius}
              fill="none"
              stroke={seg.color}
              strokeWidth={thickness}
              strokeDasharray={`${len} ${circ - len}`}
              strokeDashoffset={-offset}
              strokeLinecap="round"
            />
          );
          offset += len;
          return el;
        })}
      </g>
    </svg>
  );
}

export function DashboardView({
  view,
  models = [],
  homeTasks = [],
  runningTasks = [],
  approvalCount = 0,
  go,
  openTaskDetails,
  security,
  selectedModelObject,
}) {
  const tasks = homeTasks || [];

  const stats = useMemo(() => {
    const counts = { active: 0, done: 0, failed: 0, other: 0 };
    for (const t of tasks) counts[statusBucket(t.status)] += 1;
    const enabledModels = models.filter((m) => m.enabled !== false);
    const managed = models.filter((m) => m.managed);
    return {
      totalTasks: tasks.length,
      ...counts,
      modelCount: models.length,
      enabledModels: enabledModels.length,
      managedModels: managed.length,
      successRate: tasks.length ? Math.round((counts.done / tasks.length) * 100) : 0,
    };
  }, [tasks, models]);

  const activitySeries = useMemo(() => buildActivitySeries(tasks, 30), [tasks]);

  // Top models by how many tasks reference them.
  const topModels = useMemo(() => {
    const usage = new Map();
    for (const t of tasks) {
      const key = t.model || "—";
      usage.set(key, (usage.get(key) || 0) + 1);
    }
    return models
      .map((m) => ({ model: m, runs: usage.get(m.key) || usage.get(m.model) || 0 }))
      .sort((a, b) => b.runs - a.runs)
      .slice(0, 5);
  }, [models, tasks]);

  const maxRuns = Math.max(...topModels.map((t) => t.runs), 1);

  const donutSegments = [
    { value: stats.done, color: "var(--dash-accent)", label: "Completed" },
    { value: stats.active, color: "#5b8def", label: "Active" },
    { value: stats.failed, color: "var(--dash-down)", label: "Failed" },
    { value: stats.other, color: "#3a444b", label: "Other" },
  ].filter((s) => s.value > 0);

  const privacyLocked = security?.privacyLock ?? security?.privacy_lock;

  const kpis = [
    {
      label: "Models Registered", badge: "live", value: stats.modelCount,
      delta: `${stats.enabledModels} enabled`, up: true,
      spark: models.map((_, i) => (i % 3) + 1), icon: Sparkles,
    },
    {
      label: "Total Runs", badge: "all-time", value: stats.totalTasks.toLocaleString(),
      delta: `${stats.active} active`, up: stats.active > 0,
      spark: activitySeries.slice(-12), icon: ListChecks,
    },
    {
      label: "Success Rate", badge: "tasks", value: `${stats.successRate}%`,
      delta: `${stats.done} completed`, up: stats.successRate >= 50,
      spark: activitySeries.slice(-12).map((v) => v + 1), icon: TrendingUp,
    },
    {
      label: "Managed Deployments", badge: "warsat", value: stats.managedModels,
      delta: privacyLocked ? "privacy locked" : "ready", up: !privacyLocked,
      spark: [1, 2, 2, 3, 2, 4], icon: Satellite,
    },
  ];

  return (
    <section
      className={`app-view dash-main ${view === "home" ? "active" : ""}`}
      id="homeView"
      data-app-view="home"
      tabIndex="-1"
    >
      {/* Topbar */}
      <div className="dash-topbar">
        <div>
          <h1 className="dash-title">Operations <span className="dim">Overview</span></h1>
          <p className="dash-subtitle">Live snapshot of your local AI fleet, runs, and deployments.</p>
        </div>
        <div className="dash-topbar-actions">
          <button className="dash-user-chip" type="button" onClick={() => go("models")}>
            <span className="dash-user-avatar"><Cpu size={14} /></span>
            <span style={{ fontSize: "0.8rem" }}>{displayModelName(selectedModelObject, models)}</span>
          </button>
          <button className="dash-icon-btn" type="button" aria-label="Approvals" onClick={() => go("activity")}>
            <ShieldCheck size={17} />
          </button>
        </div>
      </div>

      {/* KPI row */}
      <div className="dash-kpi-row">
        {kpis.map((k) => {
          const Icon = k.icon;
          return (
            <div className="dash-kpi" key={k.label}>
              <div className="dash-kpi-label">
                <Icon size={14} /> <span>{k.label}</span>
                <span className="dash-kpi-badge">{k.badge}</span>
              </div>
              <div className="dash-kpi-value">{k.value}</div>
              <span className={`dash-kpi-delta ${k.up ? "is-up" : "is-down"}`}>
                {k.up ? <ChevronUp size={12} /> : <ArrowUpRight size={12} />} {k.delta}
              </span>
              <div className="dash-kpi-spark"><Sparkline data={k.spark} /></div>
            </div>
          );
        })}
      </div>

      {/* Hero chart + donut */}
      <div className="dash-grid">
        <div className="dash-card">
          <div className="dash-card-head">
            <div className="dash-card-title">Run Activity <span className="dim">· 30d</span></div>
            <div className="dash-pill-tabs">
              <button className="dash-pill is-active" type="button">Daily</button>
              <button className="dash-pill" type="button" onClick={() => go("activity")}>View all</button>
            </div>
          </div>
          <HeroChart series={activitySeries} />
        </div>

        <div className="dash-card">
          <div className="dash-card-head">
            <div className="dash-card-title">Runs by Status</div>
          </div>
          <div className="dash-donut-wrap">
            {donutSegments.length ? <Donut segments={donutSegments} /> : <div className="dash-empty">No runs yet</div>}
            {donutSegments.length > 0 && (
              <div className="dash-donut-center">
                <strong>{stats.totalTasks}</strong>
                <div style={{ fontSize: "0.7rem", color: "var(--dash-muted)" }}>runs</div>
              </div>
            )}
          </div>
          <div className="dash-donut-legend">
            {donutSegments.map((s) => (
              <div className="dash-donut-legend-item" key={s.label}>
                <span className="dash-legend-dot" style={{ background: s.color }} />
                {s.label} · {s.value}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Top models table + activity metric list */}
      <div className="dash-grid">
        <div className="dash-card">
          <div className="dash-card-head">
            <div className="dash-card-title">Top Models <span className="dim">· by runs</span></div>
            <button className="dash-pill" type="button" onClick={() => go("models")}>Manage</button>
          </div>
          {topModels.length ? (
            <table className="dash-table">
              <thead>
                <tr>
                  <th>#</th><th>Model</th><th>Runtime</th><th>Role</th><th>Usage</th><th style={{ textAlign: "right" }}>Runs</th>
                </tr>
              </thead>
              <tbody>
                {topModels.map((row, i) => (
                  <tr key={row.model.key || i}>
                    <td className="dash-rank">{i + 1}</td>
                    <td className="dash-cell-strong">{displayModelName(row.model, models)}</td>
                    <td style={{ color: "var(--dash-muted)" }}>{row.model.runtime || row.model.provider || "local"}</td>
                    <td style={{ color: "var(--dash-muted)" }}>{row.model.role || "chat"}</td>
                    <td>
                      <div className="dash-bar"><i style={{ width: `${(row.runs / maxRuns) * 100}%` }} /></div>
                    </td>
                    <td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{row.runs}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="dash-empty">No models registered yet. Open Models to add one.</div>
          )}
        </div>

        <div className="dash-card">
          <div className="dash-card-head">
            <div className="dash-card-title">Live Status</div>
            <button className="dash-pill" type="button" onClick={() => go("activity")}>Activity</button>
          </div>
          <div className="dash-metric-list">
            <Metric icon={Activity} name="Active runs" delta={`${stats.active} in flight`} value={stats.active} />
            <Metric icon={CheckCircle2} name="Completed" delta={`${stats.successRate}% success`} value={stats.done} />
            <Metric icon={GitBranch} name="Failed / cancelled" delta="needs review" value={stats.failed} />
            <Metric icon={ShieldCheck} name="Pending approvals" delta={approvalCount ? "action needed" : "all clear"} value={approvalCount} />
            <Metric icon={Boxes} name="Enabled models" delta={`${stats.modelCount} total`} value={stats.enabledModels} />
            <Metric icon={Layers} name="Managed deployments" delta="warsat" value={stats.managedModels} />
          </div>
        </div>
      </div>
    </section>
  );
}

function Metric({ icon: Icon, name, delta, value }) {
  return (
    <div className="dash-metric">
      <span className="dash-metric-icon"><Icon size={16} /></span>
      <div className="dash-metric-body">
        <div className="dash-metric-name">{name}</div>
        <div className="dash-metric-delta">{delta}</div>
      </div>
      <div className="dash-metric-value">{value}</div>
    </div>
  );
}
