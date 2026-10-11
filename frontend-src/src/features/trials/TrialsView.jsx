import { InspectorPanel } from "./TrialInspector.jsx";
import { ReportsTab } from "./ReportsTab.jsx";
import { DatasetsTab } from "./DatasetsTab.jsx";
import { ComparisonsTab } from "./ComparisonsTab.jsx";
import { PromptLabTab } from "./PromptLabTab.jsx";
import { CodingTrialTab } from "./CodingTrialTab.jsx";
import { BenchmarksTab } from "./BenchmarksTab.jsx";
import { ExperimentsTab } from "./ExperimentsTab.jsx";

import { useState, useEffect } from "react";
import { BarChart3, Beaker, Database, FileText, FlaskConical, GitCompare, RefreshCw, Sparkles, Trophy } from "lucide-react";
import { api } from "../../api/client.js";

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
    <section className={`w2-layout app-view trials-view tw ${view === "trials" ? "active" : ""}`} id="trialsView" data-app-view="trials">
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
