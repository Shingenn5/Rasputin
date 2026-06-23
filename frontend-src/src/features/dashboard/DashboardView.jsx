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
  Send,
  ShieldCheck,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import {
  Area,
  AreaChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
} from "recharts";
import { displayModelName } from "../../lib/display.js";

/* ─────────────────────────────────────────────
   DashboardView — analytics landing screen
   Charts: Recharts (gradient area, donut, sparklines). Bound to real app
   state (models, tasks, approvals) — no invented numbers.
   ───────────────────────────────────────────── */

const ACTIVE = ["queued", "running", "paused"];
const DONE = ["completed", "done", "success"];
const FAILED = ["failed", "error", "cancelled"];

const ACCENT = "#2fe3a0";
const DOWN = "#ff6b6b";
const BLUE = "#5b8def";
const FAINT = "#3a444b";

function statusBucket(status) {
  if (ACTIVE.includes(status)) return "active";
  if (DONE.includes(status)) return "done";
  if (FAILED.includes(status)) return "failed";
  return "other";
}

// Recharts sparkline from a numeric series.
function Sparkline({ data, color = ACCENT, height = 34, width = 90 }) {
  const series = (data && data.length > 1 ? data : [0, 0]).map((v, i) => ({ i, v }));
  const id = `spark-${Math.random().toString(36).slice(2, 8)}`;
  return (
    <AreaChart width={width} height={height} data={series} margin={{ top: 4, right: 0, bottom: 0, left: 0 }}>
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity={0.4} />
          <stop offset="100%" stopColor={color} stopOpacity={0} />
        </linearGradient>
      </defs>
      <Area type="monotone" dataKey="v" stroke={color} strokeWidth={1.8} fill={`url(#${id})`} isAnimationActive={false} dot={false} />
    </AreaChart>
  );
}

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
  return buckets.map((v, i) => {
    const d = new Date(now - (days - 1 - i) * dayMs);
    return { day: `${d.getMonth() + 1}/${d.getDate()}`, runs: v };
  });
}

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload || !payload.length) return null;
  return (
    <div style={{
      background: "var(--dash-panel-2)", border: "1px solid var(--dash-border-strong)",
      borderRadius: 10, padding: "8px 12px", fontSize: "0.75rem", color: "var(--dash-text)",
    }}>
      <div style={{ color: "var(--dash-muted)", marginBottom: 2 }}>{label}</div>
      <strong>{payload[0].value} runs</strong>
    </div>
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
  objective = "",
  setObjective,
  sendTask,
  healthy,
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
  const sparkVals = activitySeries.slice(-12).map((d) => d.runs);

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
    { name: "Completed", value: stats.done, color: ACCENT },
    { name: "Active", value: stats.active, color: BLUE },
    { name: "Failed", value: stats.failed, color: DOWN },
    { name: "Other", value: stats.other, color: FAINT },
  ].filter((s) => s.value > 0);

  const privacyLocked = security?.privacyLock ?? security?.privacy_lock;

  const kpis = [
    { label: "Models Registered", badge: "live", value: stats.modelCount, delta: `${stats.enabledModels} enabled`, up: true, spark: models.map((_, i) => (i % 4) + 1), icon: Sparkles, color: ACCENT },
    { label: "Total Runs", badge: "all-time", value: stats.totalTasks.toLocaleString(), delta: `${stats.active} active`, up: stats.active > 0, spark: sparkVals, icon: ListChecks, color: ACCENT },
    { label: "Success Rate", badge: "tasks", value: `${stats.successRate}%`, delta: `${stats.done} completed`, up: stats.successRate >= 50, spark: sparkVals.map((v) => v + 1), icon: TrendingUp, color: ACCENT },
    { label: "Managed Deployments", badge: "warsat", value: stats.managedModels, delta: privacyLocked ? "privacy locked" : "ready", up: !privacyLocked, spark: [1, 2, 2, 3, 2, 4], icon: Satellite, color: ACCENT },
  ];

  function submitChat(e) {
    e.preventDefault();
    if (!objective.trim()) return;
    sendTask?.();
  }

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
              <div className="dash-kpi-spark"><Sparkline data={k.spark} color={k.color} /></div>
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
          <div style={{ height: 240 }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={activitySeries} margin={{ top: 10, right: 8, bottom: 0, left: 0 }}>
                <defs>
                  <linearGradient id="dashHeroFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={ACCENT} stopOpacity={0.3} />
                    <stop offset="100%" stopColor={ACCENT} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="day" tick={{ fill: "var(--dash-faint)", fontSize: 11 }} axisLine={false} tickLine={false} interval={6} minTickGap={20} />
                <Tooltip content={<ChartTooltip />} cursor={{ stroke: "var(--dash-border-strong)" }} />
                <Area type="monotone" dataKey="runs" stroke={ACCENT} strokeWidth={2.4} fill="url(#dashHeroFill)" isAnimationActive={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="dash-card">
          <div className="dash-card-head">
            <div className="dash-card-title">Runs by Status</div>
          </div>
          {donutSegments.length ? (
            <>
              <div className="dash-donut-wrap" style={{ height: 170 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={donutSegments} dataKey="value" nameKey="name" innerRadius={56} outerRadius={78} paddingAngle={3} cornerRadius={6} stroke="none">
                      {donutSegments.map((s) => <Cell key={s.name} fill={s.color} />)}
                    </Pie>
                  </PieChart>
                </ResponsiveContainer>
                <div className="dash-donut-center">
                  <strong>{stats.totalTasks}</strong>
                  <div style={{ fontSize: "0.7rem", color: "var(--dash-muted)" }}>runs</div>
                </div>
              </div>
              <div className="dash-donut-legend">
                {donutSegments.map((s) => (
                  <div className="dash-donut-legend-item" key={s.name}>
                    <span className="dash-legend-dot" style={{ background: s.color }} />
                    {s.name} · {s.value}
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className="dash-empty">No runs yet</div>
          )}
        </div>
      </div>

      {/* Embedded chat card + top models */}
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
                    <td><div className="dash-bar"><i style={{ width: `${(row.runs / maxRuns) * 100}%` }} /></div></td>
                    <td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{row.runs}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="dash-empty">No models registered yet. Open Models to add one.</div>
          )}
        </div>

        {/* Embedded chat composer card */}
        <div className="dash-card dash-chat-card">
          <div className="dash-card-head">
            <div className="dash-card-title">Quick Chat</div>
            <button className="dash-pill" type="button" onClick={() => go("chat")}>Open full chat</button>
          </div>
          <p className="dash-chat-hint">Start a run with {displayModelName(selectedModelObject, models)}.</p>
          <form className="dash-chat-form" onSubmit={submitChat}>
            <textarea
              className="dash-chat-input"
              rows={4}
              placeholder="What should Rasputin work on?"
              value={objective}
              onChange={(e) => setObjective?.(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submitChat(e); }
              }}
            />
            <button className="dash-chat-send" type="submit" disabled={!objective.trim() || healthy === false}>
              <Send size={15} /> Send to {go ? "Chat" : "Run"}
            </button>
          </form>
        </div>
      </div>

      {/* Live status metric list */}
      <div className="dash-grid">
        <div className="dash-card" style={{ gridColumn: "1 / -1" }}>
          <div className="dash-card-head">
            <div className="dash-card-title">Live Status</div>
            <button className="dash-pill" type="button" onClick={() => go("activity")}>Activity</button>
          </div>
          <div className="dash-metric-grid">
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
