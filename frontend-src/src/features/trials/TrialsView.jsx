import React, { useState, useMemo, useEffect } from "react";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Beaker,
  BookOpen,
  CheckCircle2,
  ClipboardList,
  Database,
  FileText,
  FlaskConical,
  GitCompare,
  Layers,
  Loader2,
  Play,
  Plus,
  RefreshCw,
  Search,
  Sparkles,
  Square,
  Star,
  Trash2,
  Trophy,
  Zap,
} from "lucide-react";
import { api, postJson } from "../../api/client.js";

/* ── Tab config ── */
const trialsTabs = [
  { id: "experiments", label: "Experiments", icon: FlaskConical },
  { id: "codingtrial", label: "Coding Trial", icon: Trophy },
  { id: "benchmarks",  label: "Benchmarks",  icon: BarChart3 },
  { id: "promptlab",   label: "Prompt Lab",  icon: Sparkles },
  { id: "comparisons", label: "Comparisons", icon: GitCompare },
  { id: "datasets",    label: "Datasets",    icon: Database },
  { id: "reports",     label: "Reports",     icon: FileText },
];

const EXP_TYPES = [
  { value: "model", label: "Model Test" },
  { value: "prompt", label: "Prompt Test" },
  { value: "agent", label: "Agent Test" },
  { value: "workflow", label: "Workflow Test" },
  { value: "rag", label: "RAG Test" },
  { value: "tool", label: "Tool Test" },
  { value: "custom", label: "Custom" },
];

/* ── Helpers ── */
function statusColor(st) {
  if (["completed", "done", "success", "running"].includes(st)) return "var(--ras-safe)";
  if (["failed", "error", "cancelled"].includes(st)) return "var(--ras-danger)";
  if (["draft", "pending", "paused"].includes(st)) return "var(--ras-warn)";
  return "var(--cc-muted)";
}

function statusIcon(st) {
  if (st === "running") return <Loader2 size={14} color="var(--ras-safe)" style={{ animation: "spin 1s linear infinite" }} />;
  if (["completed", "done", "success"].includes(st)) return <CheckCircle2 size={14} color="var(--ras-safe)" />;
  if (["failed", "error"].includes(st)) return <AlertTriangle size={14} color="var(--ras-danger)" />;
  return <Activity size={14} color="var(--cc-muted)" />;
}

function fmtDate(ts) {
  if (!ts) return "—";
  return new Date(ts * 1000).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

/* ── Radar Chart SVG ── */
function RadarChart({ scores, size = 200 }) {
  const categories = ["accuracy", "reasoning", "reliability", "performance", "efficiency", "safety", "usability"];
  const labels = ["Accuracy", "Reasoning", "Reliability", "Performance", "Efficiency", "Safety", "Usability"];
  const cx = size / 2;
  const cy = size / 2;
  const maxR = size * 0.38;
  const angleStep = (2 * Math.PI) / categories.length;
  const offset = -Math.PI / 2;

  function point(i, r) {
    const a = offset + i * angleStep;
    return [cx + r * Math.cos(a), cy + r * Math.sin(a)];
  }

  const rings = [0.25, 0.5, 0.75, 1.0];
  const dataPoints = categories.map((cat, i) => {
    const val = Math.min(Math.max((scores?.[cat] || 0) / 100, 0), 1);
    return point(i, val * maxR);
  });
  const polyPoints = dataPoints.map(p => p.join(",")).join(" ");

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ overflow: "visible" }}>
      {/* Grid rings */}
      {rings.map(r => (
        <polygon
          key={r}
          points={categories.map((_, i) => point(i, r * maxR).join(",")).join(" ")}
          fill="none"
          stroke="var(--cc-border)"
          strokeWidth="0.5"
          opacity="0.5"
        />
      ))}
      {/* Axis lines */}
      {categories.map((_, i) => {
        const [ex, ey] = point(i, maxR);
        return <line key={i} x1={cx} y1={cy} x2={ex} y2={ey} stroke="var(--cc-border)" strokeWidth="0.5" opacity="0.3" />;
      })}
      {/* Data polygon */}
      <polygon points={polyPoints} fill="color-mix(in srgb, var(--cc-accent) 25%, transparent)" stroke="var(--cc-accent)" strokeWidth="2" />
      {/* Data dots */}
      {dataPoints.map(([x, y], i) => (
        <circle key={i} cx={x} cy={y} r="3" fill="var(--cc-accent)" />
      ))}
      {/* Labels */}
      {categories.map((_, i) => {
        const [lx, ly] = point(i, maxR + 16);
        return (
          <text key={i} x={lx} y={ly} textAnchor="middle" dominantBaseline="middle" fontSize="9" fill="var(--cc-muted)" fontWeight="500">
            {labels[i]}
          </text>
        );
      })}
    </svg>
  );
}


/* ═══════════════════════════════════════════
   MAIN COMPONENT
   ═══════════════════════════════════════════ */
export function TrialsView({
  view,
  models,
  /* legacy props */
  trials: legacyTrials,
  status: legacyStatus,
  runTrialCompare,
  revealTrial,
  saveTrialRoute,
  modeModelOverrides,
}) {
  const [activeTab, setActiveTab] = useState("experiments");
  const [experiments, setExperiments] = useState([]);
  const [datasets, setDatasets] = useState([]);
  const [benchmarks, setBenchmarks] = useState([]);
  const [comparisons, setComparisons] = useState([]);
  const [scorecards, setScorecards] = useState([]);
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState(null);

  async function refresh() {
    setLoading(true);
    setError("");
    try {
      const [exps, dss, bms, cmps, scs, rpts] = await Promise.all([
        api("/api/trials/experiments"),
        api("/api/trials/datasets"),
        api("/api/trials/benchmarks"),
        api("/api/trials/comparisons"),
        api("/api/trials/scorecards"),
        api("/api/trials/reports"),
      ]);
      setExperiments(exps || []);
      setDatasets(dss || []);
      setBenchmarks(bms || []);
      setComparisons(cmps || []);
      setScorecards(scs || []);
      setReports(rpts || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (view === "trials") refresh();
  }, [view]);

  if (view !== "trials") return null;

  const completedExperiments = experiments.filter(e => e.status === "completed");
  const runningExperiments = experiments.filter(e => e.status === "running");

  return (
    <section className="w2-layout app-view trials-view tw active" id="trialsView" data-app-view="trials">
      <div className="fx-rise mx-auto flex w-full min-w-0 max-w-[1500px] flex-col gap-5 p-7">

      {/* ── Header ── */}
      <div className="flex items-start justify-between gap-5">
        <div>
          <h1 className="flex items-center gap-2 text-3xl font-bold tracking-tight">
            <Beaker size={26} className="text-primary" /> Trials <span className="text-muted-foreground">Lab</span>
          </h1>
          <p className="mt-1.5 text-sm text-muted-foreground">Experimentation &amp; evaluation center. Measure what works best.</p>
        </div>
        <div className="flex flex-wrap justify-end gap-3">
          {[
            { v: experiments.length, l: "Experiments", c: "text-foreground" },
            { v: runningExperiments.length, l: "Running", c: runningExperiments.length > 0 ? "text-primary" : "text-muted-foreground" },
            { v: completedExperiments.length, l: "Completed", c: "text-primary" },
            { v: datasets.length, l: "Datasets", c: "text-foreground" },
            { v: scorecards.length, l: "Scorecards", c: "text-foreground" },
            { v: reports.length, l: "Reports", c: "text-foreground" },
          ].map((s) => (
            <div key={s.l} className="glow-card rounded-xl border border-border bg-card px-3.5 py-2 text-center">
              <div className={`text-lg font-bold ${s.c}`}>{s.v}</div>
              <div className="text-[0.62rem] uppercase tracking-wide text-muted-foreground">{s.l}</div>
            </div>
          ))}
        </div>
      </div>

      {/* ── Tab Bar ── */}
      <div style={{ padding: "0 24px", display: "flex", gap: "12px", overflowX: "auto", marginBottom: "16px" }}>
        {trialsTabs.map(t => {
          const Icon = t.icon;
          return (
            <button key={t.id} className={`w2-button ${activeTab === t.id ? "primary" : ""}`} type="button" onClick={() => { setActiveTab(t.id); setSelected(null); }}>
              <Icon size={16} /> {t.label}
            </button>
          );
        })}
        <div style={{ flex: 1 }} />
        {error && (
          <div style={{ padding: "8px 16px", borderRadius: "4px", fontSize: "0.875rem", backgroundColor: "var(--ras-danger)", color: "#fff" }}>{error}</div>
        )}
        <button className="w2-button" type="button" onClick={refresh}><RefreshCw size={16} /> Refresh</button>
      </div>

      {/* ── Content ── */}
      <div className="w2-main-grid">
        <div className="w2-column">

          {activeTab === "experiments" && (
            <ExperimentsTab
              experiments={experiments}
              models={models}
              datasets={datasets}
              selected={selected}
              setSelected={setSelected}
              refresh={refresh}
              setError={setError}
              /* legacy */
              legacyTrials={legacyTrials}
              legacyStatus={legacyStatus}
              runTrialCompare={runTrialCompare}
              revealTrial={revealTrial}
              saveTrialRoute={saveTrialRoute}
              modeModelOverrides={modeModelOverrides}
            />
          )}

          {activeTab === "benchmarks" && (
            <BenchmarksTab benchmarks={benchmarks} experiments={experiments} selected={selected} setSelected={setSelected} refresh={refresh} setError={setError} />
          )}

          {activeTab === "codingtrial" && (
            <CodingTrialTab models={models} setError={setError} />
          )}

          {activeTab === "promptlab" && (
            <PromptLabTab models={models} refresh={refresh} setError={setError} />
          )}

          {activeTab === "comparisons" && (
            <ComparisonsTab comparisons={comparisons} experiments={experiments} selected={selected} setSelected={setSelected} refresh={refresh} setError={setError} />
          )}

          {activeTab === "datasets" && (
            <DatasetsTab datasets={datasets} selected={selected} setSelected={setSelected} refresh={refresh} setError={setError} />
          )}

          {activeTab === "reports" && (
            <ReportsTab reports={reports} experiments={experiments} selected={selected} setSelected={setSelected} refresh={refresh} setError={setError} />
          )}

        </div>

        {/* ── Inspector Panel ── */}
        <div className="w2-column">
          <InspectorPanel selected={selected} scorecards={scorecards} experiments={experiments} refresh={refresh} setError={setError} />
        </div>
      </div>
      </div>
    </section>
  );
}


/* ═══════════════════════════════════════════
   EXPERIMENTS TAB
   ═══════════════════════════════════════════ */
function ExperimentsTab({ experiments, models, datasets, selected, setSelected, refresh, setError, legacyTrials, legacyStatus, runTrialCompare, revealTrial, saveTrialRoute, modeModelOverrides }) {
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [filter, setFilter] = useState("all");
  const selectable = (models || []).filter(m => m.key !== "local-embeddings").slice(0, 8);

  const displayed = useMemo(() => {
    if (filter === "all") return experiments;
    return experiments.filter(e => e.status === filter);
  }, [filter, experiments]);

  async function handleCreate(e) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    setCreating(true);
    setError("");
    try {
      const modelKeys = form.getAll("modelKeys");
      const config = { prompt: form.get("prompt") || "", modelKeys, datasetId: form.get("datasetId") || "" };
      if (form.get("type") === "prompt") {
        config.promptA = form.get("promptA") || "";
        config.promptB = form.get("promptB") || "";
        config.modelKey = form.get("modelKey") || modelKeys[0] || "dry-run";
      }
      await postJson("/api/trials/experiments", {
        name: form.get("name"),
        type: form.get("type"),
        config,
        tags: (form.get("tags") || "").split(",").map(t => t.trim()).filter(Boolean),
      });
      setShowCreate(false);
      await refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setCreating(false);
    }
  }

  async function handleRun(expId) {
    setError("");
    try {
      await postJson(`/api/trials/experiments/${expId}/run`, {});
      await refresh();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleDelete(expId) {
    if (!window.confirm("Delete this experiment?")) return;
    try {
      await api(`/api/trials/experiments/${expId}`, { method: "DELETE" });
      setSelected(null);
      await refresh();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="w2-section" style={{ flex: 1 }}>
      {/* Header */}
      <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
        <h2 style={{ margin: 0, fontSize: "1rem" }}>Experiments</h2>
        <div style={{ flex: 1 }} />
        {["all", "draft", "running", "completed", "failed"].map(f => (
          <button key={f} className={`w2-button ${filter === f ? "primary" : ""}`} type="button" onClick={() => setFilter(f)} style={{ fontSize: "0.75rem", padding: "4px 10px", textTransform: "capitalize" }}>
            {f} {f === "all" ? `(${experiments.length})` : `(${experiments.filter(e => e.status === f).length})`}
          </button>
        ))}
        <button className="w2-button primary" type="button" onClick={() => setShowCreate(!showCreate)}>
          <Plus size={14} /> New Experiment
        </button>
      </div>

      {/* Create Form */}
      {showCreate && (
        <div className="w2-card" style={{ border: "1px solid var(--cc-accent)" }}>
          <h3 style={{ margin: 0, fontSize: "0.875rem" }}>Create Experiment</h3>
          <form onSubmit={handleCreate} style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
            <label style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>
              Name
              <input className="w2-input" name="name" required placeholder="My model benchmark" />
            </label>
            <label style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>
              Type
              <select className="w2-input" name="type" defaultValue="model">
                {EXP_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </label>
            <label style={{ fontSize: "0.75rem", color: "var(--cc-muted)", gridColumn: "1 / -1" }}>
              Prompt
              <textarea className="w2-input" name="prompt" rows={2} placeholder="Enter a test prompt..." style={{ resize: "vertical" }} />
            </label>
            <label style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>
              Dataset (optional)
              <select className="w2-input" name="datasetId">
                <option value="">None</option>
                {datasets.map(ds => <option key={ds.id} value={ds.id}>{ds.name} ({ds.entries?.length || 0} entries)</option>)}
              </select>
            </label>
            <label style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>
              Tags (comma-separated)
              <input className="w2-input" name="tags" placeholder="benchmark, coding" />
            </label>
            <fieldset style={{ gridColumn: "1 / -1", border: "1px solid var(--cc-border)", borderRadius: "6px", padding: "8px" }}>
              <legend style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>Models</legend>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                {selectable.map(m => (
                  <label key={m.key} style={{ display: "flex", gap: "4px", alignItems: "center", fontSize: "0.8125rem" }}>
                    <input type="checkbox" name="modelKeys" value={m.key} />
                    {m.name || m.model || m.key}
                  </label>
                ))}
                {!selectable.length && <span style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>No models registered yet</span>}
              </div>
            </fieldset>
            <div style={{ gridColumn: "1 / -1", display: "flex", gap: "8px" }}>
              <button className="w2-button primary" type="submit" disabled={creating}>
                <FlaskConical size={14} /> {creating ? "Creating..." : "Create Experiment"}
              </button>
              <button className="w2-button" type="button" onClick={() => setShowCreate(false)}>Cancel</button>
            </div>
          </form>
        </div>
      )}

      {/* Experiment List */}
      {displayed.map(exp => (
        <div key={exp.id} className={`w2-card ${selected?.id === exp.id ? "" : ""}`} style={{ cursor: "pointer", border: selected?.id === exp.id ? "1px solid var(--cc-accent)" : undefined }} onClick={() => setSelected(exp)}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
              {statusIcon(exp.status)}
              <div>
                <strong style={{ fontSize: "0.875rem" }}>{exp.name}</strong>
                <div style={{ fontSize: "0.6875rem", color: "var(--cc-muted)" }}>
                  {exp.type} · {fmtDate(exp.createdAt)}
                </div>
              </div>
            </div>
            <div style={{ display: "flex", gap: "6px" }}>
              <span style={{ fontSize: "0.6875rem", padding: "2px 10px", borderRadius: "999px", background: `color-mix(in srgb, ${statusColor(exp.status)} 15%, var(--cc-surface))`, color: statusColor(exp.status), fontWeight: 600, textTransform: "capitalize" }}>
                {exp.status}
              </span>
            </div>
          </div>
          {exp.metrics && Object.keys(exp.metrics).length > 0 && (
            <div style={{ display: "flex", gap: "16px", fontSize: "0.75rem", color: "var(--cc-muted)" }}>
              {exp.metrics.totalDurationMs != null && <span>Duration: {exp.metrics.totalDurationMs}ms</span>}
              {exp.metrics.modelCount != null && <span>Models: {exp.metrics.modelCount}</span>}
              {exp.metrics.successCount != null && <span>Success: {exp.metrics.successCount}</span>}
            </div>
          )}
          <div style={{ display: "flex", gap: "6px" }}>
            {exp.status === "draft" && (
              <button className="w2-button primary" type="button" onClick={(e) => { e.stopPropagation(); handleRun(exp.id); }} style={{ fontSize: "0.75rem", padding: "4px 10px" }}>
                <Play size={12} /> Run
              </button>
            )}
            {exp.status === "completed" && (
              <button className="w2-button" type="button" onClick={(e) => { e.stopPropagation(); handleRun(exp.id); }} style={{ fontSize: "0.75rem", padding: "4px 10px" }}>
                <RefreshCw size={12} /> Re-run
              </button>
            )}
            <button className="w2-button" type="button" onClick={(e) => { e.stopPropagation(); handleDelete(exp.id); }} style={{ fontSize: "0.75rem", padding: "4px 10px", color: "var(--ras-danger)" }}>
              <Trash2 size={12} />
            </button>
          </div>
        </div>
      ))}

      {!displayed.length && (
        <div style={{ padding: "32px", textAlign: "center", color: "var(--cc-muted)", backgroundColor: "var(--cc-surface)", borderRadius: "8px" }}>
          No experiments yet. Create one to start measuring.
        </div>
      )}
    </div>
  );
}


/* ═══════════════════════════════════════════
   BENCHMARKS TAB
   ═══════════════════════════════════════════ */
function BenchmarksTab({ benchmarks, experiments, selected, setSelected, refresh, setError }) {
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);

  async function handleCreate(e) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const expIds = form.getAll("experimentIds");
    setCreating(true);
    try {
      await postJson("/api/trials/benchmarks", { name: form.get("name"), experimentIds: expIds });
      setShowCreate(false);
      await refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="w2-section" style={{ flex: 1 }}>
      <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
        <h2 style={{ margin: 0, fontSize: "1rem" }}>Benchmarks</h2>
        <div style={{ flex: 1 }} />
        <button className="w2-button primary" type="button" onClick={() => setShowCreate(!showCreate)}>
          <Plus size={14} /> New Benchmark
        </button>
      </div>

      {showCreate && (
        <div className="w2-card" style={{ border: "1px solid var(--cc-accent)" }}>
          <form onSubmit={handleCreate} style={{ display: "grid", gap: "8px" }}>
            <label style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>
              Benchmark Name
              <input className="w2-input" name="name" required placeholder="Model speed comparison" />
            </label>
            <fieldset style={{ border: "1px solid var(--cc-border)", borderRadius: "6px", padding: "8px" }}>
              <legend style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>Include Experiments</legend>
              {experiments.filter(e => e.status === "completed").map(e => (
                <label key={e.id} style={{ display: "flex", gap: "4px", alignItems: "center", fontSize: "0.8125rem" }}>
                  <input type="checkbox" name="experimentIds" value={e.id} />
                  {e.name}
                </label>
              ))}
              {!experiments.filter(e => e.status === "completed").length && <span style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>Complete experiments first</span>}
            </fieldset>
            <div style={{ display: "flex", gap: "8px" }}>
              <button className="w2-button primary" type="submit" disabled={creating}>{creating ? "Creating..." : "Create Benchmark"}</button>
              <button className="w2-button" type="button" onClick={() => setShowCreate(false)}>Cancel</button>
            </div>
          </form>
        </div>
      )}

      {benchmarks.map(bm => (
        <div key={bm.id} className="w2-card" style={{ cursor: "pointer", border: selected?.id === bm.id ? "1px solid var(--cc-accent)" : undefined }} onClick={() => setSelected(bm)}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <strong style={{ fontSize: "0.875rem" }}>{bm.name}</strong>
              <div style={{ fontSize: "0.6875rem", color: "var(--cc-muted)" }}>{(bm.experimentIds || []).length} experiments · {fmtDate(bm.createdAt)}</div>
            </div>
            <span style={{ fontSize: "0.6875rem", padding: "2px 10px", borderRadius: "999px", background: `color-mix(in srgb, ${statusColor(bm.status)} 15%, var(--cc-surface))`, color: statusColor(bm.status), fontWeight: 600 }}>{bm.status}</span>
          </div>
        </div>
      ))}

      {!benchmarks.length && (
        <div style={{ padding: "32px", textAlign: "center", color: "var(--cc-muted)", backgroundColor: "var(--cc-surface)", borderRadius: "8px" }}>
          No benchmarks yet. Complete experiments first, then create benchmarks.
        </div>
      )}
    </div>
  );
}


/* ═══════════════════════════════════════════
   CODING TRIAL TAB — blind-compare models on a real coding subtask,
   score objectively (syntax + operator tests), pin winner to coder role
   ═══════════════════════════════════════════ */
function CodingTrialTab({ models, setError }) {
  const [runs, setRuns] = useState([]);
  const [running, setRunning] = useState(false);
  const [status, setStatus] = useState("");
  const selectable = (models || []).filter(m => m.key !== "local-embeddings").slice(0, 8);

  async function loadRuns() {
    try {
      const data = await api("/api/trials");
      setRuns((data.runs || []).filter(r => r.kind === "coding"));
    } catch (err) {
      setError(err.message);
    }
  }
  useEffect(() => { loadRuns(); }, []);

  async function handleRun(e) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const modelKeys = form.getAll("modelKeys");
    setRunning(true);
    setStatus("");
    try {
      await postJson("/api/trials/coding-compare", {
        objective: form.get("objective") || "",
        code: form.get("code") || "",
        tests: form.get("tests") || "",
        modelKeys,
      });
      e.target.reset();
      await loadRuns();
    } catch (err) {
      setError(err.message);
    } finally {
      setRunning(false);
    }
  }

  async function handleReveal(runId) {
    try {
      await postJson(`/api/trials/${runId}/reveal`, {});
      await loadRuns();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handlePin(runId, outputId) {
    try {
      const result = await postJson(`/api/trials/${runId}/pin-role`, { outputId, role: "coder" });
      setStatus(`Pinned ${result.route.modelName} to the coder role — code mode now routes to it.`);
      await loadRuns();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="w2-section" style={{ flex: 1 }}>
      <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
        <h2 style={{ margin: 0, fontSize: "1rem" }}>Coding Trial</h2>
        <span style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>
          Blind-compare models on a coding subtask. Outputs are scored objectively; reveal, then pin the winner to the coder role.
        </span>
      </div>

      <div className="w2-card">
        <form onSubmit={handleRun} style={{ display: "grid", gap: "8px" }}>
          <label style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>
            Objective
            <textarea className="w2-input" name="objective" rows={2} required placeholder="Implement add(a, b) returning the sum." style={{ resize: "vertical" }} />
          </label>
          <label style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>
            Starting Code (optional)
            <textarea className="w2-input" name="code" rows={4} placeholder="def add(a, b):\n    ..." style={{ resize: "vertical", fontFamily: "monospace" }} />
          </label>
          <label style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>
            Tests (optional — plain asserts, run against each candidate when shell execution is permitted)
            <textarea className="w2-input" name="tests" rows={3} placeholder="assert add(2, 3) == 5" style={{ resize: "vertical", fontFamily: "monospace" }} />
          </label>
          <fieldset style={{ border: "1px solid var(--cc-border)", borderRadius: "6px", padding: "8px" }}>
            <legend style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>Models (up to 4, blind-labeled A-D)</legend>
            {selectable.map(m => (
              <label key={m.key} style={{ display: "flex", gap: "4px", alignItems: "center", fontSize: "0.8125rem" }}>
                <input type="checkbox" name="modelKeys" value={m.key} />
                {m.name || m.model || m.key}
              </label>
            ))}
            {!selectable.length && <span style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>No models registered yet</span>}
          </fieldset>
          <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
            <button className="w2-button primary" type="submit" disabled={running}>
              {running ? <Loader2 size={14} style={{ animation: "spin 1s linear infinite" }} /> : <Play size={14} />}
              {running ? "Running trial..." : "Run Blind Trial"}
            </button>
            {status && <span style={{ fontSize: "0.75rem", color: "var(--ras-safe)" }}>{status}</span>}
          </div>
        </form>
      </div>

      {runs.map(run => (
        <div key={run.id} className="w2-card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "8px" }}>
            <div>
              <strong style={{ fontSize: "0.875rem" }}>{run.objective || run.prompt}</strong>
              <div style={{ fontSize: "0.6875rem", color: "var(--cc-muted)" }}>
                {fmtDate(run.createdAt)} · tests {run.testsExecuted ? "executed" : "not executed"}
                {run.suggestedLabel && <> · top score: <strong>{run.suggestedLabel}</strong></>}
              </div>
            </div>
            {!run.revealed && (
              <button className="w2-button" type="button" onClick={() => handleReveal(run.id)}>Reveal Models</button>
            )}
          </div>
          <div style={{ display: "grid", gap: "8px", marginTop: "8px" }}>
            {(run.outputs || []).map(output => (
              <div key={output.id} style={{ border: "1px solid var(--cc-border)", borderRadius: "6px", padding: "8px" }}>
                <div style={{ display: "flex", gap: "10px", alignItems: "center", fontSize: "0.8125rem", flexWrap: "wrap" }}>
                  <strong>{output.label}</strong>
                  {run.revealed && <span style={{ color: "var(--cc-accent)" }}>{output.modelKey}</span>}
                  <span>score {output.scoring?.score ?? "—"}</span>
                  <span style={{ color: output.scoring?.syntaxOk ? "var(--ras-safe)" : "var(--ras-danger)" }}>
                    syntax {output.scoring?.syntaxOk ? "ok" : "invalid"}
                  </span>
                  {output.scoring?.testsRan && (
                    <span style={{ color: output.scoring?.testsPassed ? "var(--ras-safe)" : "var(--ras-danger)" }}>
                      tests {output.scoring?.testsPassed ? "passed" : "failed"}
                    </span>
                  )}
                  <span style={{ color: "var(--cc-muted)" }}>{output.latencyMs} ms</span>
                  <div style={{ flex: 1 }} />
                  {run.revealed && output.status === "done" && (
                    <button className="w2-button" type="button" onClick={() => handlePin(run.id, output.id)} style={{ fontSize: "0.75rem", padding: "4px 10px" }}>
                      <Trophy size={12} /> Pin to coder role
                    </button>
                  )}
                </div>
                {output.status === "error" && <div style={{ fontSize: "0.75rem", color: "var(--ras-danger)" }}>{output.error}</div>}
                {output.text && (
                  <pre style={{ fontSize: "0.6875rem", maxHeight: "140px", overflow: "auto", marginTop: "6px", marginBottom: 0 }}>{output.text}</pre>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}

      {!runs.length && (
        <div style={{ padding: "32px", textAlign: "center", color: "var(--cc-muted)", backgroundColor: "var(--cc-surface)", borderRadius: "8px" }}>
          No coding trials yet. Pick two or more models and run a blind comparison.
        </div>
      )}
    </div>
  );
}


/* ═══════════════════════════════════════════
   PROMPT LAB TAB
   ═══════════════════════════════════════════ */
function PromptLabTab({ models, refresh, setError }) {
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);
  const selectable = (models || []).filter(m => m.key !== "local-embeddings").slice(0, 8);

  async function handleRun(e) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    setRunning(true);
    setError("");
    setResult(null);
    try {
      const exp = await postJson("/api/trials/experiments", {
        name: `Prompt Lab: ${form.get("promptA")?.slice(0, 40)}...`,
        type: "prompt",
        config: {
          promptA: form.get("promptA"),
          promptB: form.get("promptB"),
          modelKey: form.get("modelKey") || "dry-run",
        },
      });
      const ran = await postJson(`/api/trials/experiments/${exp.id}/run`, {});
      setResult(ran);
      await refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setRunning(false);
    }
  }

  const runs = result?.runs || [];
  const lastRun = runs[0];
  const outputs = lastRun?.outputs || [];

  return (
    <div className="w2-section" style={{ flex: 1 }}>
      <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
        <h2 style={{ margin: 0, fontSize: "1rem" }}>Prompt Lab</h2>
        <span style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>A/B test prompts against the same model</span>
      </div>

      <div className="w2-card">
        <form onSubmit={handleRun} style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
          <label style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>
            Prompt A
            <textarea className="w2-input" name="promptA" rows={4} required placeholder="Write the first version of your prompt..." style={{ resize: "vertical" }} />
          </label>
          <label style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>
            Prompt B
            <textarea className="w2-input" name="promptB" rows={4} required placeholder="Write an alternative version..." style={{ resize: "vertical" }} />
          </label>
          <label style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>
            Model
            <select className="w2-input" name="modelKey" defaultValue="dry-run">
              {selectable.map(m => <option key={m.key} value={m.key}>{m.name || m.model || m.key}</option>)}
              <option value="dry-run">Dry Run</option>
            </select>
          </label>
          <div style={{ display: "flex", alignItems: "flex-end" }}>
            <button className="w2-button primary" type="submit" disabled={running} style={{ width: "100%" }}>
              <Zap size={14} /> {running ? "Running A/B Test..." : "Run A/B Test"}
            </button>
          </div>
        </form>
      </div>

      {/* Results */}
      {outputs.length >= 2 && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
          {outputs.map((out, i) => (
            <div key={i} className="w2-card">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <strong style={{ fontSize: "0.875rem" }}>Prompt {out.label || (i === 0 ? "A" : "B")}</strong>
                <span style={{ fontSize: "0.6875rem", color: statusColor(out.status) }}>{out.latencyMs || out.latency_ms}ms</span>
              </div>
              <div style={{ fontSize: "0.75rem", color: "var(--cc-muted)", fontStyle: "italic", borderBottom: "1px solid var(--cc-border)", paddingBottom: "8px" }}>
                {out.prompt?.slice(0, 100)}{(out.prompt?.length || 0) > 100 ? "..." : ""}
              </div>
              <div style={{ fontSize: "0.8125rem", whiteSpace: "pre-wrap", maxHeight: "300px", overflow: "auto" }}>
                {out.error || out.text || "No output"}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}


/* ═══════════════════════════════════════════
   COMPARISONS TAB
   ═══════════════════════════════════════════ */
function ComparisonsTab({ comparisons, experiments, selected, setSelected, refresh, setError }) {
  const [showCreate, setShowCreate] = useState(false);

  async function handleCreate(e) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    try {
      await postJson("/api/trials/comparisons", {
        name: form.get("name") || undefined,
        experimentIds: form.getAll("experimentIds"),
      });
      setShowCreate(false);
      await refresh();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="w2-section" style={{ flex: 1 }}>
      <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
        <h2 style={{ margin: 0, fontSize: "1rem" }}>Comparisons</h2>
        <div style={{ flex: 1 }} />
        <button className="w2-button primary" type="button" onClick={() => setShowCreate(!showCreate)}>
          <Plus size={14} /> Compare
        </button>
      </div>

      {showCreate && (
        <div className="w2-card" style={{ border: "1px solid var(--cc-accent)" }}>
          <form onSubmit={handleCreate} style={{ display: "grid", gap: "8px" }}>
            <label style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>
              Comparison Name
              <input className="w2-input" name="name" placeholder="Model A vs Model B" />
            </label>
            <fieldset style={{ border: "1px solid var(--cc-border)", borderRadius: "6px", padding: "8px" }}>
              <legend style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>Select Experiments</legend>
              {experiments.filter(e => e.status === "completed").map(e => (
                <label key={e.id} style={{ display: "flex", gap: "4px", alignItems: "center", fontSize: "0.8125rem" }}>
                  <input type="checkbox" name="experimentIds" value={e.id} />
                  {e.name}
                </label>
              ))}
            </fieldset>
            <div style={{ display: "flex", gap: "8px" }}>
              <button className="w2-button primary" type="submit"><GitCompare size={14} /> Create Comparison</button>
              <button className="w2-button" type="button" onClick={() => setShowCreate(false)}>Cancel</button>
            </div>
          </form>
        </div>
      )}

      {comparisons.map(cmp => (
        <div key={cmp.id} className="w2-card" style={{ cursor: "pointer", border: selected?.id === cmp.id ? "1px solid var(--cc-accent)" : undefined }} onClick={() => setSelected(cmp)}>
          <strong style={{ fontSize: "0.875rem" }}>{cmp.name}</strong>
          <div style={{ fontSize: "0.6875rem", color: "var(--cc-muted)" }}>{(cmp.experimentIds || []).length} experiments · {fmtDate(cmp.createdAt)}</div>
        </div>
      ))}

      {!comparisons.length && (
        <div style={{ padding: "32px", textAlign: "center", color: "var(--cc-muted)", backgroundColor: "var(--cc-surface)", borderRadius: "8px" }}>
          No comparisons yet. Complete experiments first.
        </div>
      )}
    </div>
  );
}


/* ═══════════════════════════════════════════
   DATASETS TAB
   ═══════════════════════════════════════════ */
function DatasetsTab({ datasets, selected, setSelected, refresh, setError }) {
  const [showCreate, setShowCreate] = useState(false);
  const [seeding, setSeeding] = useState(false);

  async function handleCreate(e) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    let entries = [];
    try {
      const raw = form.get("entries") || "[]";
      entries = JSON.parse(raw);
    } catch {
      setError("Entries must be valid JSON array");
      return;
    }
    try {
      await postJson("/api/trials/datasets", {
        name: form.get("name"),
        type: form.get("type"),
        entries,
        tags: (form.get("tags") || "").split(",").map(t => t.trim()).filter(Boolean),
      });
      setShowCreate(false);
      await refresh();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleSeed() {
    setSeeding(true);
    try {
      await postJson("/api/trials/datasets/seed", {});
      await refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setSeeding(false);
    }
  }

  async function handleDelete(dsId) {
    if (!window.confirm("Delete this dataset?")) return;
    try {
      await api(`/api/trials/datasets/${dsId}`, { method: "DELETE" });
      setSelected(null);
      await refresh();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="w2-section" style={{ flex: 1 }}>
      <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
        <h2 style={{ margin: 0, fontSize: "1rem" }}>Datasets</h2>
        <div style={{ flex: 1 }} />
        <button className="w2-button" type="button" onClick={handleSeed} disabled={seeding}>
          <Sparkles size={14} /> {seeding ? "Seeding..." : "Seed Defaults"}
        </button>
        <button className="w2-button primary" type="button" onClick={() => setShowCreate(!showCreate)}>
          <Plus size={14} /> New Dataset
        </button>
      </div>

      {showCreate && (
        <div className="w2-card" style={{ border: "1px solid var(--cc-accent)" }}>
          <form onSubmit={handleCreate} style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
            <label style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>
              Name
              <input className="w2-input" name="name" required placeholder="My evaluation set" />
            </label>
            <label style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>
              Type
              <select className="w2-input" name="type" defaultValue="questions">
                <option value="questions">Questions</option>
                <option value="tasks">Tasks</option>
                <option value="documents">Documents</option>
                <option value="evaluation">Evaluation</option>
                <option value="scenarios">Scenarios</option>
              </select>
            </label>
            <label style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>
              Tags (comma-separated)
              <input className="w2-input" name="tags" placeholder="reasoning, math" />
            </label>
            <div />
            <label style={{ fontSize: "0.75rem", color: "var(--cc-muted)", gridColumn: "1 / -1" }}>
              Entries (JSON array)
              <textarea className="w2-input" name="entries" rows={4} placeholder='[{"prompt": "What is 2+2?", "expected": "4"}]' style={{ resize: "vertical", fontFamily: "monospace" }} />
            </label>
            <div style={{ gridColumn: "1 / -1", display: "flex", gap: "8px" }}>
              <button className="w2-button primary" type="submit"><Database size={14} /> Create Dataset</button>
              <button className="w2-button" type="button" onClick={() => setShowCreate(false)}>Cancel</button>
            </div>
          </form>
        </div>
      )}

      {datasets.map(ds => (
        <div key={ds.id} className="w2-card" style={{ cursor: "pointer", border: selected?.id === ds.id ? "1px solid var(--cc-accent)" : undefined }} onClick={() => setSelected(ds)}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <strong style={{ fontSize: "0.875rem" }}>{ds.name}</strong>
              <div style={{ fontSize: "0.6875rem", color: "var(--cc-muted)" }}>{ds.type} · {(ds.entries || []).length} entries · v{ds.version || 1}</div>
            </div>
            <div style={{ display: "flex", gap: "4px" }}>
              {(ds.tags || []).map(tag => (
                <span key={tag} style={{ fontSize: "0.6875rem", padding: "1px 8px", borderRadius: "999px", background: "var(--cc-surface)", border: "1px solid var(--cc-border)" }}>{tag}</span>
              ))}
            </div>
          </div>
          <button className="w2-button" type="button" onClick={(e) => { e.stopPropagation(); handleDelete(ds.id); }} style={{ fontSize: "0.75rem", padding: "4px 10px", color: "var(--ras-danger)", alignSelf: "flex-start" }}>
            <Trash2 size={12} /> Delete
          </button>
        </div>
      ))}

      {!datasets.length && (
        <div style={{ padding: "32px", textAlign: "center", color: "var(--cc-muted)", backgroundColor: "var(--cc-surface)", borderRadius: "8px" }}>
          No datasets yet. Click "Seed Defaults" to create starter evaluation sets.
        </div>
      )}
    </div>
  );
}


/* ═══════════════════════════════════════════
   REPORTS TAB
   ═══════════════════════════════════════════ */
function ReportsTab({ reports, experiments, selected, setSelected, refresh, setError }) {
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);

  async function handleCreate(e) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    setCreating(true);
    try {
      await postJson("/api/trials/reports", {
        name: form.get("name"),
        type: form.get("type"),
        experimentIds: form.getAll("experimentIds"),
      });
      setShowCreate(false);
      await refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="w2-section" style={{ flex: 1 }}>
      <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
        <h2 style={{ margin: 0, fontSize: "1rem" }}>Reports</h2>
        <div style={{ flex: 1 }} />
        <button className="w2-button primary" type="button" onClick={() => setShowCreate(!showCreate)}>
          <Plus size={14} /> Generate Report
        </button>
      </div>

      {showCreate && (
        <div className="w2-card" style={{ border: "1px solid var(--cc-accent)" }}>
          <form onSubmit={handleCreate} style={{ display: "grid", gap: "8px" }}>
            <label style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>
              Report Name
              <input className="w2-input" name="name" required placeholder="Monthly benchmark report" />
            </label>
            <label style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>
              Report Type
              <select className="w2-input" name="type" defaultValue="experiment">
                <option value="experiment">Experiment Report</option>
                <option value="benchmark">Benchmark Report</option>
                <option value="comparison">Comparison Report</option>
                <option value="evaluation">Evaluation Report</option>
              </select>
            </label>
            <fieldset style={{ border: "1px solid var(--cc-border)", borderRadius: "6px", padding: "8px" }}>
              <legend style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>Include Experiments</legend>
              {experiments.filter(e => e.status === "completed").map(e => (
                <label key={e.id} style={{ display: "flex", gap: "4px", alignItems: "center", fontSize: "0.8125rem" }}>
                  <input type="checkbox" name="experimentIds" value={e.id} />
                  {e.name}
                </label>
              ))}
            </fieldset>
            <div style={{ display: "flex", gap: "8px" }}>
              <button className="w2-button primary" type="submit" disabled={creating}>{creating ? "Generating..." : "Generate Report"}</button>
              <button className="w2-button" type="button" onClick={() => setShowCreate(false)}>Cancel</button>
            </div>
          </form>
        </div>
      )}

      {reports.map(rpt => (
        <div key={rpt.id} className="w2-card" style={{ cursor: "pointer", border: selected?.id === rpt.id ? "1px solid var(--cc-accent)" : undefined }} onClick={() => setSelected(rpt)}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <strong style={{ fontSize: "0.875rem" }}>{rpt.name}</strong>
              <div style={{ fontSize: "0.6875rem", color: "var(--cc-muted)" }}>{rpt.type} · {fmtDate(rpt.createdAt)}</div>
            </div>
            <FileText size={16} color="var(--cc-muted)" />
          </div>
        </div>
      ))}

      {!reports.length && (
        <div style={{ padding: "32px", textAlign: "center", color: "var(--cc-muted)", backgroundColor: "var(--cc-surface)", borderRadius: "8px" }}>
          No reports yet. Complete experiments to generate reports.
        </div>
      )}
    </div>
  );
}


/* ═══════════════════════════════════════════
   INSPECTOR PANEL
   ═══════════════════════════════════════════ */
function InspectorPanel({ selected, scorecards, experiments, refresh, setError }) {
  const [generatingScorecard, setGeneratingScorecard] = useState(false);

  async function handleGenerateScorecard() {
    if (!selected?.id) return;
    setGeneratingScorecard(true);
    try {
      await postJson("/api/trials/scorecards", { experimentId: selected.id });
      await refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setGeneratingScorecard(false);
    }
  }

  // Find scorecard for selected experiment
  const relatedScorecard = scorecards.find(sc => sc.subjectId === selected?.id);

  return (
    <>
      <div className="w2-card" style={{ flex: 1 }}>
        <h3 style={{ margin: "0 0 8px 0", fontSize: "0.875rem" }}>Inspector</h3>
        {selected ? (
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            <div style={{ background: "var(--cc-bg)", padding: "12px", borderRadius: "6px" }}>
              <h4 style={{ margin: "0 0 8px 0", fontSize: "1rem" }}>{selected.name}</h4>
              <div style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: "6px 12px", fontSize: "0.75rem" }}>
                <span style={{ color: "var(--cc-muted)" }}>ID</span>
                <span style={{ fontFamily: "monospace", fontSize: "0.6875rem" }}>{selected.id}</span>
                {selected.type && <>
                  <span style={{ color: "var(--cc-muted)" }}>Type</span>
                  <span style={{ textTransform: "capitalize" }}>{selected.type}</span>
                </>}
                {selected.status && <>
                  <span style={{ color: "var(--cc-muted)" }}>Status</span>
                  <span style={{ color: statusColor(selected.status), textTransform: "capitalize" }}>{selected.status}</span>
                </>}
                {selected.createdAt && <>
                  <span style={{ color: "var(--cc-muted)" }}>Created</span>
                  <span>{fmtDate(selected.createdAt)}</span>
                </>}
                {selected.entries && <>
                  <span style={{ color: "var(--cc-muted)" }}>Entries</span>
                  <span>{selected.entries.length}</span>
                </>}
              </div>
            </div>

            {/* Tags */}
            {(selected.tags || []).length > 0 && (
              <div style={{ display: "flex", flexWrap: "wrap", gap: "4px" }}>
                {selected.tags.map(tag => (
                  <span key={tag} style={{ fontSize: "0.6875rem", padding: "1px 8px", borderRadius: "999px", background: "var(--cc-surface)", border: "1px solid var(--cc-border)" }}>{tag}</span>
                ))}
              </div>
            )}

            {/* Metrics */}
            {selected.metrics && Object.keys(selected.metrics).length > 0 && (
              <div style={{ background: "var(--cc-bg)", padding: "12px", borderRadius: "6px" }}>
                <strong style={{ fontSize: "0.75rem", color: "var(--cc-muted)", textTransform: "uppercase", letterSpacing: ".05em" }}>Metrics</strong>
                <div style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: "4px 12px", fontSize: "0.75rem", marginTop: "8px" }}>
                  {Object.entries(selected.metrics).filter(([k]) => k !== "results" && k !== "error").map(([k, v]) => (
                    <React.Fragment key={k}>
                      <span style={{ color: "var(--cc-muted)" }}>{k}</span>
                      <span>{typeof v === "number" ? v.toLocaleString() : String(v)}</span>
                    </React.Fragment>
                  ))}
                </div>
              </div>
            )}

            {/* Report content preview */}
            {selected.contentMd && (
              <div style={{ background: "var(--cc-bg)", padding: "12px", borderRadius: "6px", maxHeight: "400px", overflow: "auto" }}>
                <strong style={{ fontSize: "0.75rem", color: "var(--cc-muted)", textTransform: "uppercase", letterSpacing: ".05em" }}>Report Preview</strong>
                <pre style={{ fontSize: "0.75rem", whiteSpace: "pre-wrap", marginTop: "8px", fontFamily: "inherit" }}>
                  {selected.contentMd}
                </pre>
              </div>
            )}

            {/* Actions */}
            <div style={{ display: "flex", flexDirection: "column", gap: "6px", marginTop: "auto" }}>
              {selected.status === "completed" && (
                <button className="w2-button primary" type="button" onClick={handleGenerateScorecard} disabled={generatingScorecard}>
                  <Star size={14} /> {generatingScorecard ? "Generating..." : "Generate Scorecard"}
                </button>
              )}
            </div>
          </div>
        ) : (
          <div style={{ color: "var(--cc-muted)", fontSize: "0.875rem", textAlign: "center", marginTop: "32px" }}>
            Select an item to inspect.
          </div>
        )}
      </div>

      {/* Scorecard display */}
      {relatedScorecard && (
        <div className="w2-card">
          <h3 style={{ margin: "0 0 8px 0", fontSize: "0.875rem" }}><Trophy size={14} style={{ verticalAlign: "-2px", marginRight: "4px" }} />Scorecard</h3>
          <div style={{ display: "flex", justifyContent: "center" }}>
            <RadarChart scores={relatedScorecard.scores} size={200} />
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "4px", fontSize: "0.75rem" }}>
            {Object.entries(relatedScorecard.scores || {}).map(([cat, score]) => (
              <div key={cat} style={{ display: "flex", justifyContent: "space-between", padding: "4px 8px", background: "var(--cc-bg)", borderRadius: "4px" }}>
                <span style={{ color: "var(--cc-muted)", textTransform: "capitalize" }}>{cat}</span>
                <strong style={{ color: score >= 70 ? "var(--ras-safe)" : score >= 40 ? "var(--ras-warn)" : "var(--ras-danger)" }}>{score}</strong>
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  );
}
