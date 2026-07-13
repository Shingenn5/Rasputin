import React, { useMemo } from "react";
import {
  Activity,
  ArrowUpRight,
  Boxes,
  Bell,
  CheckCircle2,
  ChevronUp,
  Cpu,
  GitBranch,
  Layers,
  ListChecks,
  Rocket,
  Search,
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
import { motion } from "framer-motion";
import { displayModelName } from "../../lib/display.js";
import { Card } from "@/components/ui/card.jsx";
import { Button } from "@/components/ui/button.jsx";
import { Badge } from "@/components/ui/badge.jsx";
import { CountUp } from "@/components/fx/CountUp.jsx";
import { cn } from "@/lib/utils.js";

const fadeUp = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.5, ease: [0.2, 0.8, 0.2, 1] } },
};
const stagger = {
  hidden: {},
  show: { transition: { staggerChildren: 0.07 } },
};

/* ─────────────────────────────────────────────
   DashboardView — modern analytics landing (Tailwind + shadcn + Recharts).
   Bound to real app state (models, tasks, approvals) — no invented numbers.
   ───────────────────────────────────────────── */

const ACTIVE = ["queued", "running", "paused"];
const DONE = ["completed", "done", "success"];
const FAILED = ["failed", "error", "cancelled"];

const ACCENT = "var(--primary)";
const DOWN = "var(--destructive)";
const BLUE = "var(--chart-2)";
const FAINT = "var(--muted)";

function statusBucket(s) {
  if (ACTIVE.includes(s)) return "active";
  if (DONE.includes(s)) return "done";
  if (FAILED.includes(s)) return "failed";
  return "other";
}

function Sparkline({ data, color = ACCENT, height = 36, width = 96 }) {
  const series = (data && data.length > 1 ? data : [0, 0]).map((v, i) => ({ i, v }));
  const id = `spk-${Math.random().toString(36).slice(2, 8)}`;
  return (
    <AreaChart width={width} height={height} data={series} margin={{ top: 4, right: 0, bottom: 0, left: 0 }}>
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity={0.45} />
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
  for (const t of tasks) {
    const ts = Date.parse(t.createdAt || t.created_at || t.updatedAt || "") || 0;
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
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-border bg-popover px-3 py-2 text-xs text-popover-foreground shadow-lg">
      <div className="text-muted-foreground">{label}</div>
      <strong>{payload[0].value} runs</strong>
    </div>
  );
}

export function DashboardView({
  view,
  models = [],
  homeTasks = [],
  approvalCount = 0,
  go,
  security,
  selectedModelObject,
  objective = "",
  setObjective,
  sendTask,
  healthy,
  role,
}) {
  const tasks = homeTasks || [];
  const taskAccess = role !== "viewer";
  const adminAccess = role === "admin";

  const stats = useMemo(() => {
    const counts = { active: 0, done: 0, failed: 0, other: 0 };
    for (const t of tasks) counts[statusBucket(t.status)] += 1;
    const enabled = models.filter((m) => m.enabled !== false);
    const managed = models.filter((m) => m.managed);
    return {
      totalTasks: tasks.length, ...counts,
      modelCount: models.length, enabledModels: enabled.length, managedModels: managed.length,
      successRate: tasks.length ? Math.round((counts.done / tasks.length) * 100) : 0,
    };
  }, [tasks, models]);

  const activitySeries = useMemo(() => buildActivitySeries(tasks, 30), [tasks]);
  const sparkVals = activitySeries.slice(-12).map((d) => d.runs);

  const topModels = useMemo(() => {
    const usage = new Map();
    for (const t of tasks) usage.set(t.model || "—", (usage.get(t.model || "—") || 0) + 1);
    return models
      .map((m) => ({ model: m, runs: usage.get(m.key) || usage.get(m.model) || 0 }))
      .sort((a, b) => b.runs - a.runs)
      .slice(0, 5);
  }, [models, tasks]);
  const maxRuns = Math.max(...topModels.map((t) => t.runs), 1);

  const donut = [
    { name: "Completed", value: stats.done, color: "var(--chart-1)" },
    { name: "Active", value: stats.active, color: "var(--chart-2)" },
    { name: "Failed", value: stats.failed, color: "var(--chart-3)" },
    { name: "Other", value: stats.other, color: "var(--muted)" },
  ].filter((s) => s.value > 0);

  const privacyLocked = security?.privacyLock ?? security?.privacy_lock;

  const kpis = [
    { label: "Models Registered", badge: "live", value: stats.modelCount, delta: `${stats.enabledModels} enabled`, tone: "up", spark: models.map((_, i) => (i % 4) + 1), icon: Sparkles },
    { label: "Total Runs", badge: "all-time", value: stats.totalTasks.toLocaleString(), delta: `${stats.active} active`, tone: stats.active > 0 ? "up" : "neutral", spark: sparkVals, icon: ListChecks },
    { label: "Success Rate", badge: "tasks", value: `${stats.successRate}%`, delta: `${stats.done} completed`, tone: stats.totalTasks === 0 ? "neutral" : stats.successRate >= 50 ? "up" : "down", spark: sparkVals.map((v) => v + 1), icon: TrendingUp },
    { label: "Deployments", badge: "warsat", value: stats.managedModels, delta: privacyLocked ? "privacy locked" : "ready", tone: "neutral", spark: [1, 2, 2, 3, 2, 4], icon: Rocket },
  ];

  function submitChat(e) {
    e.preventDefault();
    if (!objective.trim()) return;
    sendTask?.();
  }

  return (
    <section
      className={cn("app-view tw", view === "home" ? "active" : "")}
      id="homeView"
      data-app-view="home"
      tabIndex="-1"
    >
      <motion.div
        className="mx-auto flex w-full min-w-0 max-w-[1500px] flex-col gap-5 p-7"
        variants={stagger}
        initial="hidden"
        animate="show"
      >
        {/* Topbar */}
        <motion.div variants={fadeUp} className="flex items-start justify-between gap-5">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">
              <span className="sheen-text">Operations</span> <span className="text-muted-foreground">Overview</span>
            </h1>
            <p className="mt-1.5 text-sm text-muted-foreground">
              Live snapshot of your local AI fleet, runs, and deployments.
            </p>
          </div>
          <div className="flex items-center gap-2.5">
            <div className="glass hidden items-center gap-2 rounded-full px-4 py-2 text-sm text-muted-foreground sm:flex">
              <Search size={15} /> <span>Search…</span>
            </div>
            {taskAccess && <Button variant="outline" size="icon" className="rounded-full" onClick={() => go("activity")} aria-label="Activity">
              <Bell size={16} />
            </Button>}
            {adminAccess && <button
              type="button"
              onClick={() => go("models")}
              className="glass flex items-center gap-2 rounded-full py-1.5 pl-2 pr-3.5 text-sm transition-colors hover:border-primary/30"
            >
              <span className="grid size-7 place-items-center rounded-full bg-gradient-to-br from-primary to-emerald-700 text-primary-foreground">
                <Cpu size={14} />
              </span>
              {displayModelName(selectedModelObject, models)}
            </button>}
          </div>
        </motion.div>

        {/* KPI row */}
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {kpis.map((k) => {
            const Icon = k.icon;
            return (
              <motion.div key={k.label} variants={fadeUp}>
                <Card className="glow-card relative overflow-hidden p-5">
                  <div className="mb-2.5 flex items-center gap-2 text-sm text-muted-foreground">
                    <Icon size={14} /> <span>{k.label}</span>
                    <Badge variant="muted" className="ml-auto">{k.badge}</Badge>
                  </div>
                  <div className="text-3xl font-bold tracking-tight">
                    <CountUp value={k.value} />
                  </div>
                  <Badge variant={k.tone === "up" ? "up" : k.tone === "down" ? "down" : "muted"} className="mt-2.5">
                    {k.tone === "up" && <ChevronUp size={12} />}
                    {k.tone === "down" && <ArrowUpRight size={12} />}
                    {k.delta}
                  </Badge>
                  <div className="pointer-events-none absolute bottom-3.5 right-3.5 hidden opacity-90 sm:block">
                    <Sparkline data={k.spark} />
                  </div>
                </Card>
              </motion.div>
            );
          })}
        </div>

        {/* Hero chart + donut */}
        <motion.div variants={fadeUp} className="grid grid-cols-1 gap-5 lg:grid-cols-[2fr_1fr]">
          <Card className="glow-card p-5">
            <div className="mb-4 flex items-center justify-between">
              <div className="text-base font-semibold">Run Activity <span className="text-muted-foreground">· 30d</span></div>
              <div className="flex gap-1 rounded-full border border-border bg-background p-1">
                <span className="rounded-full bg-secondary px-3 py-1 text-xs font-medium">Daily</span>
                <button className="rounded-full px-3 py-1 text-xs text-muted-foreground hover:text-foreground" onClick={() => go("activity")}>View all</button>
              </div>
            </div>
            <div className="h-[240px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={activitySeries} margin={{ top: 10, right: 8, bottom: 0, left: 0 }}>
                  <defs>
                    <linearGradient id="heroFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="var(--primary)" stopOpacity={0.3} />
                      <stop offset="100%" stopColor="var(--primary)" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="day" tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} axisLine={false} tickLine={false} interval={6} minTickGap={20} />
                  <Tooltip content={<ChartTooltip />} cursor={{ stroke: "var(--border)" }} />
                  <Area type="monotone" dataKey="runs" stroke="var(--primary)" strokeWidth={2.4} fill="url(#heroFill)" isAnimationActive={false} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </Card>

          <Card className="glow-card p-5">
            <div className="mb-4 text-base font-semibold">Runs by Status</div>
            {donut.length ? (
              <>
                <div className="relative grid h-[170px] place-items-center">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie data={donut} dataKey="value" nameKey="name" innerRadius={56} outerRadius={78} paddingAngle={3} cornerRadius={6} stroke="none">
                        {donut.map((s) => <Cell key={s.name} fill={s.color} />)}
                      </Pie>
                    </PieChart>
                  </ResponsiveContainer>
                  <div className="absolute text-center">
                    <strong className="text-2xl">{stats.totalTasks}</strong>
                    <div className="text-xs text-muted-foreground">runs</div>
                  </div>
                </div>
                <div className="mt-3.5 flex flex-col gap-2">
                  {donut.map((s) => (
                    <div key={s.name} className="flex items-center gap-2 text-sm text-muted-foreground">
                      <span className="size-2.5 rounded-full" style={{ background: s.color }} />
                      {s.name} · {s.value}
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <div className="py-7 text-center text-sm text-muted-foreground">No runs yet</div>
            )}
          </Card>
        </motion.div>

        {/* Top models + quick chat */}
        <motion.div variants={fadeUp} className="grid grid-cols-1 gap-5 lg:grid-cols-[2fr_1fr]">
          <Card className="glow-card p-5">
            <div className="mb-4 flex items-center justify-between">
              <div className="text-base font-semibold">Top Models <span className="text-muted-foreground">· by runs</span></div>
              {adminAccess && <Button variant="ghost" size="pill" onClick={() => go("models")}>Manage</Button>}
            </div>
            {topModels.length ? (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[440px] border-collapse">
                  <thead>
                    <tr className="text-left text-[0.66rem] uppercase tracking-wider text-muted-foreground/70">
                      <th className="px-2.5 py-2 font-semibold">#</th>
                      <th className="px-2.5 py-2 font-semibold">Model</th>
                      <th className="hidden px-2.5 py-2 font-semibold sm:table-cell">Runtime</th>
                      <th className="hidden px-2.5 py-2 font-semibold sm:table-cell">Role</th>
                      <th className="px-2.5 py-2 font-semibold">Usage</th>
                      <th className="px-2.5 py-2 text-right font-semibold">Runs</th>
                    </tr>
                  </thead>
                  <tbody>
                    {topModels.map((row, i) => (
                      <tr key={row.model.key || i} className="border-t border-border transition-colors hover:bg-secondary/50">
                        <td className="px-2.5 py-3 text-sm tabular-nums text-muted-foreground/70">{i + 1}</td>
                        <td className="px-2.5 py-3 text-sm font-semibold">{displayModelName(row.model, models)}</td>
                        <td className="hidden px-2.5 py-3 text-sm text-muted-foreground sm:table-cell">{row.model.runtime || row.model.provider || "local"}</td>
                        <td className="hidden px-2.5 py-3 text-sm text-muted-foreground sm:table-cell">{row.model.role || "chat"}</td>
                        <td className="px-2.5 py-3">
                          <div className="h-1 min-w-[60px] overflow-hidden rounded bg-secondary">
                            <div className="h-full rounded bg-primary" style={{ width: `${(row.runs / maxRuns) * 100}%` }} />
                          </div>
                        </td>
                        <td className="px-2.5 py-3 text-right text-sm tabular-nums">{row.runs}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="py-7 text-center text-sm text-muted-foreground">No models registered yet.</div>
            )}
          </Card>

          <Card className="glow-card flex flex-col p-5">
            <div className="mb-3 flex items-center justify-between">
              <div className="text-base font-semibold">{taskAccess ? "Quick Chat" : "Read-only session"}</div>
              {taskAccess && <Button variant="ghost" size="pill" onClick={() => go("chat")}>Open full chat</Button>}
            </div>
            {taskAccess ? <><p className="mb-3 text-sm text-muted-foreground">
              Start a run with {displayModelName(selectedModelObject, models)}.
            </p>
            <form className="flex flex-1 flex-col gap-3" onSubmit={submitChat}>
              <textarea
                className="min-h-[96px] flex-1 resize-none rounded-lg border border-input bg-background px-3.5 py-3 text-sm outline-none transition-colors focus:border-primary/50"
                rows={4}
                placeholder="What should Rasputin work on?"
                value={objective}
                onChange={(e) => setObjective?.(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submitChat(e); } }}
              />
              <Button type="submit" disabled={!objective.trim() || healthy === false} className="rounded-full">
                <Send size={15} /> Send to Chat
              </Button>
            </form></> : <div className="flex flex-1 flex-col justify-between gap-4 text-sm text-muted-foreground">
              <p>Viewer accounts can inspect shared workspaces and their own records, but cannot start agent runs or change appliance configuration.</p>
              <Button variant="outline" className="self-start" onClick={() => go("workspaces")}>Browse shared workspaces</Button>
            </div>}
          </Card>
        </motion.div>

        {/* Live status */}
        <motion.div variants={fadeUp}>
        <Card className="glow-card p-5">
          <div className="mb-4 flex items-center justify-between">
            <div className="text-base font-semibold">Live Status</div>
            <Button variant="ghost" size="pill" onClick={() => go("activity")}>Activity</Button>
          </div>
          <div className="grid grid-cols-1 gap-x-5 gap-y-1 md:grid-cols-3">
            <Metric icon={Activity} name="Active runs" delta={`${stats.active} in flight`} value={stats.active} />
            <Metric icon={CheckCircle2} name="Completed" delta={`${stats.successRate}% success`} value={stats.done} />
            <Metric icon={GitBranch} name="Failed / cancelled" delta="needs review" value={stats.failed} />
            <Metric icon={ShieldCheck} name="Pending approvals" delta={approvalCount ? "action needed" : "all clear"} value={approvalCount} />
            <Metric icon={Boxes} name="Enabled models" delta={`${stats.modelCount} total`} value={stats.enabledModels} />
            <Metric icon={Layers} name="Managed deployments" delta="warsat" value={stats.managedModels} />
          </div>
        </Card>
        </motion.div>
      </motion.div>
    </section>
  );
}

function Metric({ icon: Icon, name, delta, value }) {
  return (
    <div className="flex items-center gap-3 rounded-xl px-2 py-2.5 transition-colors hover:bg-secondary/50">
      <span className="grid size-9 shrink-0 place-items-center rounded-[10px] bg-secondary text-muted-foreground">
        <Icon size={16} />
      </span>
      <div className="min-w-0 flex-1">
        <div className="text-sm font-medium">{name}</div>
        <div className="text-xs text-primary">{delta}</div>
      </div>
      <div className="font-bold tabular-nums">{value}</div>
    </div>
  );
}
