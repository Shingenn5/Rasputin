import React, { useState, useMemo, useCallback, useEffect } from "react";
import {
  Activity,
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  Cloud,
  Cpu,
  Database,
  Download,
  ExternalLink,
  Gauge,
  HardDrive,
  KeyRound,
  Layers,
  MonitorSpeaker,
  Package,
  Play,
  Power,
  RefreshCw,
  Search,
  Server,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  Trash2,
  Users,
  Wrench,
  Zap,
} from "lucide-react";
import {
  discoveredModelIds,
  displayModelName,
  displayModelSecondary,
  isModelHealthy,
  labelize,
  modelMismatchLine,
  runtimeStatus,
} from "../../lib/display.js";
import { actionRegistry, useReliableAction } from "../../lib/actionRegistry.js";
import { api } from "../../api/client.js";
import { SkeletonList } from "../../components/Skeleton.jsx";
import { Button } from "../../components/Button.jsx";
import { Button as UIButton } from "@/components/ui/button.jsx";
import { Badge } from "@/components/ui/badge.jsx";
import { Card } from "@/components/ui/card.jsx";

/* ── Tab config ── */
const modelsTabs = [
  { id: "library",    label: "Library",     icon: BookOpen },
  { id: "installed",  label: "Installed",   icon: Package },
  { id: "running",    label: "Running",     icon: Activity },
  { id: "settings",   label: "Settings",    icon: Settings },
];

/* ── Helpers ── */
function contextWindowFor(m) {
  for (const k of ["contextWindow","context_window","maxModelLen","max_model_len"])
    if (Number.isFinite(Number(m?.[k])) && Number(m?.[k]) > 0) return Number(m[k]);
  return 0;
}

function statusColor(st) {
  if (["reachable","healthy","ready","running"].includes(st)) return "var(--ras-safe)";
  if (["unhealthy","error","failed","blocked"].includes(st)) return "var(--ras-danger)";
  if (["stopped","unknown","warning"].includes(st)) return "var(--ras-warn)";
  return "var(--cc-muted)";
}

/* ═══════════════════════════════════════════
   MAIN COMPONENT
   ═══════════════════════════════════════════ */
export function ModelsView({
  view,
  models,
  selectedModelObject,
  selectedModel,
  setSelectedModel,
  testingMode,
  setTestingMode,
  runModelAction,
  loadModels,
  scanGguf,
  registerLocalModel,
  registerApiModel,
  modelProviders,
  modelCatalog,
  modelCatalogLoading,
  modelCatalogError,
  loadModelCatalog,
  prepareCatalogModelForWarsat,
  warsat,
  warsatHardware,
  warsatRuntimes,
  warsatPlan,
  security,
  openWarsat,
}) {
  const [activeTab, setActiveTab] = useState("library");
  const [uiState, setUiState] = useState({ status: "idle", message: "" });
  const executeAction = useReliableAction("ModelsView");

  /* catalog state */
  const [catalogSearch, setCatalogSearch] = useState("");
  const [catalogPurpose, setCatalogPurpose] = useState("all");
  const [catalogRuntime, setCatalogRuntime] = useState("deployable");
  const [catalogFit, setCatalogFit] = useState("all");
  const [searchMode, setSearchMode] = useState("catalog");
  const [hfQuery, setHfQuery] = useState("");
  const [hfResults, setHfResults] = useState([]);
  const [hfLoading, setHfLoading] = useState(false);
  const [hfSort, setHfSort] = useState("downloads");
  const [activeDownloads, setActiveDownloads] = useState([]);
  const [pageSize, setPageSize] = useState(20);
  const [page, setPage] = useState(1);

  // Back to page 1 whenever the visible set changes shape.
  useEffect(() => {
    setPage(1);
  }, [catalogSearch, catalogPurpose, catalogRuntime, catalogFit, searchMode, hfQuery, pageSize]);

  useEffect(() => {
    if (view !== "models") return;
    const interval = setInterval(async () => {
      try {
        const d = await api("/api/models/downloads/active");
        setActiveDownloads(d || []);
      } catch (e) { }
    }, 1000);
    return () => clearInterval(interval);
  }, [view]);

  /* derived */
  const catalogItems = modelCatalog?.items || [];
  const catalogCategories = modelCatalog?.categories || [];
  const catalogRuntimes = modelCatalog?.runtimes || [];
  const activeModel = selectedModelObject || models?.[0] || null;
  const healthy = isModelHealthy(activeModel);
  const status = runtimeStatus(activeModel);

  const apiProviders = modelProviders?.length ? modelProviders : [
    { id: "openai", name: "OpenAI", defaultKeyEnv: "OPENAI_API_KEY" },
    { id: "anthropic", name: "Anthropic", defaultKeyEnv: "ANTHROPIC_API_KEY" },
    { id: "gemini", name: "Google Gemini", defaultKeyEnv: "GEMINI_API_KEY" },
    { id: "openai-compatible-remote", name: "Other OpenAI-compatible", defaultKeyEnv: "" },
  ];
  const remoteBlocked = security?.privacyLock || !security?.allowRemoteModels;

  const installedModels = useMemo(() => (models || []).filter(m => m.key !== "dry-run" && m.provider !== "hash-vector"), [models]);
  const runningModels = useMemo(() => (models || []).filter(m => {
    const s = (m.runtime_status || m.runtimeStatus || "").toLowerCase();
    return (s === "reachable" || s === "running" || m.container_status === "running")
      && m.key !== "dry-run" && m.provider !== "hash-vector" && m.provider !== "mock";
  }), [models]);

  const filteredCatalog = useMemo(() => {
    const q = catalogSearch.trim().toLowerCase();
    return catalogItems.filter(item => {
      const text = [item.name, item.id, item.modelId, item.provider, item.purpose, ...(item.capabilities || [])].join(" ").toLowerCase();
      if (q && !text.includes(q)) return false;
      if (catalogPurpose !== "all" && item.purpose !== catalogPurpose) return false;
      if (catalogRuntime === "deployable" && !item.deployable) return false;
      if (catalogRuntime !== "all" && catalogRuntime !== "deployable" && !(item.runtimeOptions || []).some(o => o.protocolId === catalogRuntime)) return false;
      return true;
    });
  }, [catalogItems, catalogSearch, catalogPurpose, catalogRuntime]);

  /* HF search with debounce */
  useEffect(() => {
    if (searchMode !== "huggingface") return;
    const t = setTimeout(async () => {
      setHfLoading(true);
      try {
        // Fetch enough results to fill several pages at the chosen size.
        const hfLimit = String(Math.min(500, Math.max(100, pageSize * 5)));
        const p = new URLSearchParams({ q: hfQuery, sort: hfSort, limit: hfLimit, fit: "true" });
        if (catalogPurpose !== "all") {
          const pm = { chat: "text-generation", coding: "text-generation", vision: "image-to-text", embeddings: "feature-extraction", speech: "automatic-speech-recognition" };
          if (pm[catalogPurpose]) p.set("type", pm[catalogPurpose]);
        }
        const d = await api(`/api/model-catalog/search?${p.toString()}`);
        setHfResults(d.items || []);
      } catch (err) {
        console.error("HF Search Error:", err);
        setHfResults([]);
      }
      setHfLoading(false);
    }, 500);
    return () => clearTimeout(t);
  }, [hfQuery, hfSort, catalogPurpose, searchMode, pageSize]);

  const totalVramGb = useMemo(() => {
    const gpus = warsatHardware?.detectedHardware?.gpus || [];
    return gpus.reduce((sum, g) => sum + (g.memoryTotalMb || g.memory_total_mb || 0), 0) / 1024;
  }, [warsatHardware]);

  const displayItems = useMemo(() => {
    const list = searchMode === "huggingface" ? hfResults : filteredCatalog;
    if (catalogFit !== "fits") return list;
    const vramLimit = totalVramGb > 0 ? totalVramGb : 12; // Fallback to 12GB if no GPU detected
    return list.filter(item => {
      if (!item.vramEstimateGb) return true;
      return item.vramEstimateGb <= vramLimit + 1; // 1GB headroom
    });
  }, [searchMode, hfResults, filteredCatalog, catalogFit, totalVramGb]);

  const pageCount = Math.max(1, Math.ceil(displayItems.length / pageSize));
  const currentPage = Math.min(page, pageCount);
  const pagedItems = useMemo(
    () => displayItems.slice((currentPage - 1) * pageSize, currentPage * pageSize),
    [displayItems, currentPage, pageSize]
  );

  /* reliable actions */
  const handleRefresh = () => executeAction("RefreshRegistry", "system", async () => loadModels?.(), setUiState);
  const handleScanGguf = () => executeAction("ScanGGUF", "system", async () => scanGguf?.(), setUiState);
  const handleLoadCatalog = (remote) => executeAction("LoadCatalog", "system", async () => loadModelCatalog?.(remote), setUiState);
  const startDownload = async (modelId) => {
    try {
      await api("/api/models/download", "POST", { modelId });
      setUiState({ status: "success", message: `Started download of ${modelId}` });
    } catch (e) {
      setUiState({ status: "failed", message: `Failed to start download: ${e.message}` });
    }
  };

  /* stats */
  const totalModels = (models || []).length;
  const healthyCount = (models || []).filter(m => isModelHealthy(m)).length;

  const updateTestingMode = useCallback((on) => {
    setTestingMode(!!on);
    if (on && models?.some(m => m.key === "dry-run")) { setSelectedModel?.("dry-run"); return; }
    if (!on && selectedModel === "dry-run") {
      const fb = (models || []).find(m => m.role === "main" && m.key !== "dry-run")
        || (models || []).find(m => m.key !== "dry-run" && m.role !== "embeddings");
      if (fb) setSelectedModel?.(fb.key);
    }
  }, [models, selectedModel, setSelectedModel, setTestingMode]);

  return (
    <section className={`w2-layout app-view models-view tw ${view === "models" ? "active" : ""}`} id="modelsView" data-app-view="models">
      <div className="fx-rise mx-auto flex w-full min-w-0 max-w-[1500px] flex-col gap-5 p-7">

      {/* ── Header ── */}
      <div className="flex items-start justify-between gap-5">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Models <span className="text-muted-foreground">Center</span></h1>
          <p className="mt-1.5 text-sm text-muted-foreground">Discover, deploy, and manage AI models.</p>
        </div>
        <div className="flex gap-3">
          {[
            { v: totalModels, l: "Registered", c: "text-foreground" },
            { v: healthyCount, l: "Healthy", c: "text-primary" },
            { v: runningModels.length, l: "Running", c: "text-amber-400" },
            { v: catalogItems.length, l: "In Catalog", c: "text-sky-400" },
          ].map((s) => (
            <div key={s.l} className="glow-card rounded-xl border border-border bg-card px-4 py-2.5 text-center">
              <div className={`text-xl font-bold ${s.c}`}>{s.v}</div>
              <div className="text-[0.66rem] uppercase tracking-wide text-muted-foreground">{s.l}</div>
            </div>
          ))}
        </div>
      </div>

      {/* ── Tab Bar ── */}
      <div className="flex items-center gap-2 overflow-x-auto">
        {modelsTabs.map(t => {
          const Icon = t.icon;
          return (
            <UIButton key={t.id} variant={activeTab === t.id ? "default" : "outline"} size="sm" type="button" onClick={() => setActiveTab(t.id)}>
              <Icon size={15} /> {t.label}
            </UIButton>
          );
        })}
        <div className="flex-1" />
        {uiState.status !== "idle" && (
          <Badge variant={uiState.status === "failed" ? "down" : uiState.status === "success" ? "up" : "muted"}>
            {uiState.message}
          </Badge>
        )}
        <UIButton variant="outline" size="sm" type="button" onClick={handleRefresh}>
          <RefreshCw size={15} /> Refresh
        </UIButton>
      </div>

      {/* ── Content ── */}
      <div className="w2-main-grid">
        <div className="w2-column">

          {/* ═══ LIBRARY TAB ═══ */}
          {activeTab === "library" && (
            <div className="w2-section" style={{ flex: 1 }}>
              {/* Source toggle */}
              <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                <button className={`w2-button ${searchMode === "catalog" ? "primary" : ""}`} type="button" onClick={() => setSearchMode("catalog")}>
                  <Database size={14} /> Local Catalog
                </button>
                <button className={`w2-button ${searchMode === "huggingface" ? "primary" : ""}`} type="button" onClick={() => setSearchMode("huggingface")}>
                  <Cloud size={14} /> Hugging Face
                </button>
                <div style={{ flex: 1 }} />
                {searchMode === "catalog" && (
                  <>
                    <button className="w2-button" type="button" onClick={() => handleLoadCatalog(false)}>
                      <RefreshCw size={14} /> Local
                    </button>
                    <Button primary onClick={() => handleLoadCatalog(true)} loading={modelCatalogLoading} loadingLabel="Refreshing…" icon={<Cloud size={14} />}>
                      Refresh Remote
                    </Button>
                  </>
                )}
              </div>

              {/* Search + filters */}
              <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                <Search size={16} color="var(--cc-muted)" />
                <input
                  className="w2-input"
                  value={searchMode === "huggingface" ? hfQuery : catalogSearch}
                  onChange={e => searchMode === "huggingface" ? setHfQuery(e.target.value) : setCatalogSearch(e.target.value)}
                  placeholder={searchMode === "huggingface" ? "Search Hugging Face models..." : "Filter catalog by name, provider..."}
                />
                <select className="w2-input" style={{ width: "140px", flex: "none" }} value={catalogPurpose} onChange={e => setCatalogPurpose(e.target.value)}>
                  <option value="all">All types</option>
                  {catalogCategories.map(c => <option key={c.id} value={c.id}>{c.label}</option>)}
                </select>
                {searchMode === "huggingface" && (
                  <select className="w2-input" style={{ width: "130px", flex: "none" }} value={hfSort} onChange={e => setHfSort(e.target.value)}>
                    <option value="downloads">Downloads</option>
                    <option value="likes">Likes</option>
                    <option value="trending">Trending</option>
                    <option value="lastModified">Recent</option>
                  </select>
                )}
                {searchMode === "catalog" && (
                  <select className="w2-input" style={{ width: "130px", flex: "none" }} value={catalogRuntime} onChange={e => setCatalogRuntime(e.target.value)}>
                    <option value="deployable">Deployable</option>
                    <option value="all">All Runtimes</option>
                    {catalogRuntimes.map(r => <option key={r.id} value={r.id}>{r.label}</option>)}
                  </select>
                )}
                <select className="w2-input" style={{ width: "130px", flex: "none" }} value={catalogFit} onChange={e => setCatalogFit(e.target.value)}>
                  <option value="all">Any fit</option>
                  <option value="fits">Fits on device</option>
                </select>
              </div>

              {/* Status line */}
              <div style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>
                {searchMode === "catalog"
                  ? `${filteredCatalog.length} models · Source: ${modelCatalog?.source?.status || "local"}`
                  : hfLoading ? "Searching Hugging Face..." : `${hfResults.length} results`}
              </div>

              {/* Active Downloads */}
              {activeDownloads.length > 0 && (
                <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginBottom: "8px" }}>
                  {activeDownloads.map(dl => (
                    <div key={dl.id} className="w2-card" style={{ padding: "8px 12px", gap: "4px" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.8125rem" }}>
                        <strong>{dl.modelId}</strong>
                        <span style={{ color: "var(--cc-muted)" }}>{dl.status}</span>
                      </div>
                      <div style={{ height: "4px", background: "var(--cc-border)", borderRadius: "2px", overflow: "hidden" }}>
                        <div style={{ height: "100%", width: `${dl.progress || 0}%`, background: "var(--ras-safe)", transition: "width 0.5s ease" }} />
                      </div>
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.6875rem", color: "var(--cc-muted)" }}>
                        <span>{(dl.downloadedBytes / 1024 / 1024 / 1024).toFixed(2)} GB / {dl.totalBytes > 0 ? (dl.totalBytes / 1024 / 1024 / 1024).toFixed(2) + " GB" : "?"}</span>
                        <span>{dl.progress.toFixed(1)}%</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Model list */}
              {pagedItems.map(item => (
                <CatalogCard key={item.id} item={item} prepareCatalogModelForWarsat={prepareCatalogModelForWarsat} searchMode={searchMode} startDownload={startDownload} activeDownloads={activeDownloads} />
              ))}

              {/* Pagination */}
              {displayItems.length > 0 && (
                <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "10px", padding: "6px 0" }}>
                  <button className="w2-button" type="button" disabled={currentPage <= 1} onClick={() => setPage(currentPage - 1)} style={{ fontSize: "0.75rem", padding: "4px 12px" }}>
                    Prev
                  </button>
                  <span style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>
                    Page {currentPage} of {pageCount} · {displayItems.length} models
                  </span>
                  <button className="w2-button" type="button" disabled={currentPage >= pageCount} onClick={() => setPage(currentPage + 1)} style={{ fontSize: "0.75rem", padding: "4px 12px" }}>
                    Next
                  </button>
                  <select className="w2-input" style={{ width: "110px", flex: "none" }} value={pageSize} onChange={e => setPageSize(Number(e.target.value))}>
                    {[10, 20, 40, 80].map(n => <option key={n} value={n}>{n} / page</option>)}
                  </select>
                </div>
              )}

              {/* Loading skeletons while the catalog/search is in flight and nothing is shown yet */}
              {!displayItems.length && (modelCatalogLoading || hfLoading) && (
                <SkeletonList count={5} />
              )}

              {!displayItems.length && !modelCatalogLoading && !hfLoading && (
                <div style={{ padding: "32px", textAlign: "center", color: "var(--cc-muted)", backgroundColor: "var(--cc-surface)", borderRadius: "8px" }}>
                  {searchMode === "huggingface" ? "No models found. Try broadening your search or choosing a different category." : "No models match. Try different filters."}
                </div>
              )}
            </div>
          )}

          {/* ═══ INSTALLED TAB ═══ */}
          {activeTab === "installed" && (
            <div className="w2-section" style={{ flex: 1 }}>
              <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                <h2 style={{ margin: 0, fontSize: "1rem" }}>Local Registry</h2>
                <div style={{ flex: 1 }} />
                <button className="w2-button" type="button" onClick={handleScanGguf}><HardDrive size={14} /> Scan GGUF</button>
                <button className="w2-button" type="button" onClick={handleRefresh}><RefreshCw size={14} /> Refresh</button>
              </div>

              {installedModels.map(model => (
                <InstalledCard key={model.key} model={model} allModels={models} runModelAction={runModelAction} executeAction={executeAction} setUiState={setUiState} />
              ))}

              {!installedModels.length && (
                <div style={{ padding: "32px", textAlign: "center", color: "var(--cc-muted)", backgroundColor: "var(--cc-surface)", borderRadius: "8px" }}>
                  No models registered. Use Library to discover, or Settings to connect endpoints.
                </div>
              )}
            </div>
          )}

          {/* ═══ RUNNING TAB ═══ */}
          {activeTab === "running" && (
            <div className="w2-section" style={{ flex: 1 }}>
              <ActiveModelCard
                model={activeModel}
                models={models}
                healthy={healthy}
                status={status}
                runModelAction={runModelAction}
                executeAction={executeAction}
                setUiState={setUiState}
                openWarsat={openWarsat}
              />

              {runningModels.length > 0 && (
                <div className="w2-card">
                  <h3 style={{ margin: 0, fontSize: "0.875rem" }}>Active Deployments ({runningModels.length})</h3>
                  {runningModels.map(m => (
                    <div key={m.key} className="w2-list-item">
                      <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                        <Activity size={14} color="var(--ras-safe)" />
                        <div>
                          <strong style={{ fontSize: "0.8125rem" }}>{displayModelName(m, models)}</strong>
                          <div style={{ fontSize: "0.6875rem", color: "var(--cc-muted)" }}>{m.runtime || m.provider} · {labelize(m.role || "chat")}</div>
                        </div>
                      </div>
                      <span style={{ fontSize: "0.6875rem", color: "var(--ras-safe)", fontWeight: 600 }}>Online</span>
                    </div>
                  ))}
                </div>
              )}

              <InfraStatusCard warsatHardware={warsatHardware} warsatRuntimes={warsatRuntimes} warsat={warsat} />
            </div>
          )}

          {/* ═══ SETTINGS TAB ═══ */}
          {activeTab === "settings" && (
            <div className="w2-section" style={{ flex: 1 }}>
              {/* Testing Mode */}
              <div className="w2-card">
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div>
                    <strong>Testing Mode</strong>
                    <div style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>Show dry-run model for local smoke tests.</div>
                  </div>
                  <button className={`w2-button ${testingMode ? "primary" : ""}`} type="button" onClick={() => updateTestingMode(!testingMode)}>
                    {testingMode ? "Disable" : "Enable"}
                  </button>
                </div>
              </div>

              {/* Connect Local */}
              <div className="w2-card">
                <h3 style={{ margin: 0, fontSize: "0.875rem" }}><HardDrive size={14} style={{ verticalAlign: "-2px" }} /> Connect Local Endpoint</h3>
                <form onSubmit={registerLocalModel} style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
                  <input className="w2-input" name="name" placeholder="Display Name" />
                  <input className="w2-input" name="model" placeholder="Model ID *" required />
                  <input className="w2-input" name="baseUrl" placeholder="http://127.0.0.1:1234/v1 *" required />
                  <select className="w2-input" name="role" defaultValue="helper">
                    <option value="main">Main</option><option value="coder">Coder</option><option value="researcher">Researcher</option><option value="helper">Helper</option><option value="planner">Planner</option><option value="summarizer">Summarizer</option>
                  </select>
                  <div style={{ gridColumn: "1 / -1" }}>
                    <button className="w2-button primary" type="submit" style={{ width: "100%" }}><CheckCircle2 size={14} /> Connect Model</button>
                  </div>
                </form>
              </div>

              {/* Connect API */}
              <div className="w2-card">
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <h3 style={{ margin: 0, fontSize: "0.875rem" }}><Cloud size={14} style={{ verticalAlign: "-2px" }} /> Connect API Provider</h3>
                  <span style={{ fontSize: "0.6875rem", padding: "2px 10px", borderRadius: "999px", background: remoteBlocked ? "color-mix(in srgb, var(--ras-danger) 15%, var(--cc-surface))" : "color-mix(in srgb, var(--ras-safe) 15%, var(--cc-surface))", color: remoteBlocked ? "var(--ras-danger)" : "var(--ras-safe)", fontWeight: 600 }}>
                    {remoteBlocked ? "Remote blocked" : "Remote allowed"}
                  </span>
                </div>
                <form onSubmit={registerApiModel} style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
                  <select className="w2-input" name="provider" defaultValue="openai">
                    {apiProviders.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                  </select>
                  <input className="w2-input" name="name" placeholder="Display Name" />
                  <input className="w2-input" name="model" placeholder="Model ID *" required />
                  <input className="w2-input" name="baseUrl" placeholder="Base URL (blank = default)" />
                  <select className="w2-input" name="role" defaultValue="helper">
                    <option value="main">Main</option><option value="coder">Coder</option><option value="researcher">Researcher</option><option value="helper">Helper</option>
                  </select>
                  <input className="w2-input" name="apiKey" type="password" autoComplete="off" placeholder="API Key (local secret)" />
                  <div style={{ gridColumn: "1 / -1" }}>
                    <button className="w2-button primary" type="submit" style={{ width: "100%" }}><KeyRound size={14} /> Register API Model</button>
                  </div>
                </form>
              </div>

              {/* Warsat */}
              <div className="w2-card">
                <h3 style={{ margin: 0, fontSize: "0.875rem" }}><Play size={14} style={{ verticalAlign: "-2px" }} /> Warsat Deployment</h3>
                <p style={{ fontSize: "0.75rem", color: "var(--cc-muted)", margin: 0 }}>Use Warsat to deploy local model endpoints via Docker.</p>
                <button className="w2-button primary" type="button" onClick={openWarsat} style={{ alignSelf: "flex-start" }}><Play size={14} /> Open Warsat</button>
              </div>

              {/* Full registry list */}
              <div className="w2-card">
                <h3 style={{ margin: 0, fontSize: "0.875rem" }}><SlidersHorizontal size={14} style={{ verticalAlign: "-2px" }} /> Full Registry</h3>
                {(models || []).map(m => (
                  <div key={m.key} className="w2-list-item" style={{ cursor: "default" }}>
                    <div>
                      <strong style={{ fontSize: "0.8125rem" }}>{displayModelName(m, models)}</strong>
                      <div style={{ fontSize: "0.6875rem", color: "var(--cc-muted)" }}>{labelize(m.role || "chat")} · {m.runtime || m.provider || "local"} · {runtimeStatus(m)}</div>
                    </div>
                    <span style={{ fontSize: "0.6875rem", color: "var(--cc-muted)" }}>{m.key}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

        </div>

        {/* ── Right Column (context) ── */}
        <div className="w2-column">
          <RightPanel
            activeTab={activeTab}
            activeModel={activeModel}
            models={models}
            healthy={healthy}
            status={status}
            warsatHardware={warsatHardware}
          />
        </div>
      </div>
      </div>
    </section>
  );
}


/* ═══════════════════════════════════════════
   CATALOG CARD
   ═══════════════════════════════════════════ */
function CatalogCard({ item, prepareCatalogModelForWarsat, searchMode, startDownload, activeDownloads }) {
  const modelId = item.modelId || item.id;
  const downloadState = (activeDownloads || []).find(dl => dl.modelId === modelId);
  const isDownloading = downloadState && downloadState.status !== "failed" && downloadState.status !== "completed";
  const fmt = (n) => n >= 1e6 ? `${(n / 1e6).toFixed(1)}M` : n >= 1e3 ? `${(n / 1e3).toFixed(1)}K` : n;
  return (
    <div className="ras-list-item glow-card flex flex-col gap-3 rounded-2xl border border-border bg-card p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <strong className="text-sm">{item.name}</strong>
          <div className="truncate text-[0.7rem] text-muted-foreground">{item.modelId || item.id}</div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {item.deployable && <Zap size={13} className="text-primary" />}
          <span className="text-[0.7rem] text-muted-foreground">{labelize(item.purpose || "chat")}</span>
        </div>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {item.vramEstimateGb && <Badge variant="muted">{item.vramEstimateGb} GB VRAM</Badge>}
        {item.downloads > 0 && <Badge variant="muted">↓ {fmt(item.downloads)}</Badge>}
        {item.likes > 0 && <Badge variant="muted">♥ {fmt(item.likes)}</Badge>}
        {item.license && <Badge variant="muted">{item.license}</Badge>}
        {item.fitLabel && searchMode === "catalog" && (
          <Badge variant={item.fitLabel === "Strong fit" ? "up" : item.fitLabel === "Blocked" ? "down" : "muted"}>{item.fitLabel}</Badge>
        )}
      </div>

      {item.summary && <p className="text-xs text-muted-foreground">{item.summary.slice(0, 120)}</p>}

      <div className="flex items-center gap-2">
        {item.deployable && (
          <UIButton size="sm" type="button" onClick={() => prepareCatalogModelForWarsat?.(item)}>
            <Play size={12} /> Deploy via Warsat
          </UIButton>
        )}
        {(searchMode === "huggingface" || item.source === "huggingface") && (
          <UIButton variant={isDownloading ? "default" : "outline"} size="sm" type="button" disabled={isDownloading} onClick={() => startDownload(modelId)}>
            <Download size={12} /> {isDownloading ? "Downloading…" : "Download Weights"}
          </UIButton>
        )}
        {item.sourceUrl && item.source === "huggingface" && (
          <a href={item.sourceUrl} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 text-[0.7rem] text-sky-400 no-underline">
            <ExternalLink size={11} /> HF Page
          </a>
        )}
      </div>
    </div>
  );
}


/* ═══════════════════════════════════════════
   INSTALLED CARD
   ═══════════════════════════════════════════ */
function InstalledCard({ model, allModels, runModelAction, executeAction, setUiState }) {
  const name = displayModelName(model, allModels);
  const secondary = displayModelSecondary(model, allModels);
  const st = runtimeStatus(model);
  const isHealthy = isModelHealthy(model);
  const mismatch = modelMismatchLine(model);
  const ctx = contextWindowFor(model);

  const [busy, setBusy] = useState(null); // which action ("test"|"discover") is in flight
  const runAction = async (key, name, op) => {
    setBusy(key);
    try {
      await executeAction(name, model.key, async () => runModelAction?.(op), setUiState);
    } finally {
      setBusy(null);
    }
  };
  const handleTest = () => runAction("test", "TestHealth", "test");
  const handleDiscover = () => runAction("discover", "Discover", "discover");

  return (
    <div className="ras-list-item glow-card flex flex-col gap-3 rounded-2xl border border-border bg-card p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <Cpu size={18} style={{ color: statusColor(st) }} />
          <div>
            <strong className="text-sm">{name}</strong>
            {secondary && <div className="text-[0.7rem] text-muted-foreground">{secondary}</div>}
          </div>
        </div>
        <Badge variant={isHealthy ? "up" : "down"}>{isHealthy ? "Healthy" : labelize(st)}</Badge>
      </div>

      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
        <span>Model: {model.model || "—"}</span>
        <span>Runtime: {model.runtime || model.provider || "local"}</span>
        <span>Role: {labelize(model.role || "chat")}</span>
        {ctx > 0 && <span>Context: {ctx.toLocaleString()}</span>}
      </div>

      {mismatch && (
        <div className="flex items-center gap-1.5 rounded-lg bg-amber-500/10 px-2.5 py-1.5 text-xs text-amber-400">
          <AlertTriangle size={13} /> {mismatch}
        </div>
      )}

      <div className="flex gap-2">
        <Button onClick={handleTest} loading={busy === "test"} loadingLabel="Testing…" icon={<CheckCircle2 size={12} />} spinnerSize={12} style={{ fontSize: "0.75rem", padding: "4px 10px" }}>Test</Button>
        <Button onClick={handleDiscover} loading={busy === "discover"} loadingLabel="Discovering…" icon={<Search size={12} />} spinnerSize={12} style={{ fontSize: "0.75rem", padding: "4px 10px" }}>Discover</Button>
      </div>
    </div>
  );
}


/* ═══════════════════════════════════════════
   ACTIVE MODEL CARD
   ═══════════════════════════════════════════ */
function ActiveModelCard({ model, models, healthy, status, runModelAction, executeAction, setUiState, openWarsat }) {
  const name = displayModelName(model, models);
  const secondary = displayModelSecondary(model, models);
  const mismatch = modelMismatchLine(model);
  const ctx = contextWindowFor(model);

  const handleTest = () => executeAction("TestHealth", model?.key, async () => runModelAction?.("test"), setUiState);
  const handleDiscover = () => executeAction("Discover", model?.key, async () => runModelAction?.("discover"), setUiState);
  const handleRepair = () => executeAction("Repair", model?.key, async () => runModelAction?.("repair"), setUiState);

  return (
    <div className="w2-card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
          <Cpu size={24} color={healthy ? "var(--ras-safe)" : "var(--ras-danger)"} />
          <div>
            <div style={{ fontSize: "0.6875rem", textTransform: "uppercase", letterSpacing: ".05em", color: "var(--cc-muted)", fontWeight: 600 }}>Active Chat Model</div>
            <h2 style={{ margin: "2px 0 0", fontSize: "1.125rem" }}>{name}</h2>
            {secondary && <p style={{ margin: 0, fontSize: "0.8125rem", color: "var(--cc-muted)" }}>{secondary}</p>}
          </div>
        </div>
        <span style={{ fontSize: "0.75rem", padding: "4px 12px", borderRadius: "999px", background: healthy ? "color-mix(in srgb, var(--ras-safe) 15%, var(--cc-surface))" : "color-mix(in srgb, var(--ras-danger) 15%, var(--cc-surface))", color: healthy ? "var(--ras-safe)" : "var(--ras-danger)", fontWeight: 600 }}>
          {healthy ? "Reachable" : labelize(status)}
        </span>
      </div>

      <div style={{ display: "flex", gap: "16px", fontSize: "0.75rem", color: "var(--cc-muted)", flexWrap: "wrap" }}>
        <span>Model: {model?.model || "Not configured"}</span>
        <span>Endpoint: {model?.url || model?.base_url || "Not set"}</span>
        <span>Runtime: {model?.runtime || model?.provider || "local"}</span>
        {ctx > 0 && <span>Context: {ctx.toLocaleString()}</span>}
      </div>

      {mismatch && (
        <div style={{ display: "flex", gap: "6px", alignItems: "center", fontSize: "0.75rem", color: "var(--ras-warn)", padding: "8px 10px", background: "color-mix(in srgb, var(--ras-warn) 8%, var(--cc-surface))", borderRadius: "6px" }}>
          <Wrench size={13} /> {mismatch}
        </div>
      )}

      <div style={{ display: "flex", gap: "8px" }}>
        <button className="w2-button" type="button" onClick={handleTest}><CheckCircle2 size={14} /> Test</button>
        <button className="w2-button" type="button" onClick={handleDiscover}><Search size={14} /> Discover</button>
        <button className="w2-button" type="button" onClick={handleRepair}><Wrench size={14} /> Repair</button>
        <button className="w2-button primary" type="button" onClick={openWarsat}><Play size={14} /> Warsat</button>
      </div>
    </div>
  );
}


/* ═══════════════════════════════════════════
   INFRA STATUS
   ═══════════════════════════════════════════ */
function InfraStatusCard({ warsatHardware, warsatRuntimes, warsat }) {
  const runtimeCount = warsatRuntimes?.count ?? warsatRuntimes?.containers?.length ?? 0;
  return (
    <div className="w2-card">
      <h3 style={{ margin: 0, fontSize: "0.875rem" }}>Infrastructure</h3>
      <div className="w2-health-grid">
        <div className="w2-health-item"><Server size={16} color="var(--cc-muted)" /> Warsat: {warsatHardware ? labelize(warsatHardware.status || "unknown") : "Not checked"}</div>
        <div className="w2-health-item"><MonitorSpeaker size={16} color="var(--cc-muted)" /> Containers: {runtimeCount}</div>
        <div className="w2-health-item"><ShieldCheck size={16} color="var(--ras-safe)" /> Docker: {warsat?.dockerControlEnabled ? "Enabled" : "Off"}</div>
      </div>
    </div>
  );
}


/* ═══════════════════════════════════════════
   RIGHT PANEL
   ═══════════════════════════════════════════ */
function RightPanel({ activeTab, activeModel, models, healthy, status, warsatHardware }) {
  const name = displayModelName(activeModel, models);

  if (activeTab === "library") {
    return (
      <div className="w2-section">
        <h3 className="w2-section-title">Quick Start</h3>
        <div className="w2-card">
          <strong style={{ fontSize: "0.875rem" }}>How to add a model</strong>
          <ol style={{ margin: 0, paddingLeft: "18px", fontSize: "0.75rem", color: "var(--cc-muted)" }}>
            <li>Browse or search for a model</li>
            <li>Click "Deploy via Warsat" on a deployable model</li>
            <li>Or use Settings to connect a running endpoint</li>
          </ol>
        </div>
        <div className="w2-card">
          <strong style={{ fontSize: "0.875rem" }}>Supported Runtimes</strong>
          <div style={{ fontSize: "0.75rem", color: "var(--cc-muted)", display: "flex", flexDirection: "column", gap: "4px" }}>
            <span>• vLLM CUDA (Hugging Face models)</span>
            <span>• llama.cpp (GGUF files)</span>
            <span>• Ollama (quick experiments)</span>
            <span>• External local endpoints</span>
            <span>• Remote APIs (OpenAI, Anthropic, Gemini)</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="w2-section">
      <h3 className="w2-section-title">Active Model</h3>
      <div className="w2-card">
        <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
          <Cpu size={18} color={healthy ? "var(--ras-safe)" : "var(--ras-danger)"} />
          <strong style={{ fontSize: "0.875rem" }}>{name}</strong>
        </div>
        <div style={{ fontSize: "0.75rem", color: "var(--cc-muted)", display: "flex", flexDirection: "column", gap: "4px" }}>
          <span>Status: {healthy ? "Reachable" : labelize(status)}</span>
          <span>Model: {activeModel?.model || "—"}</span>
          <span>Runtime: {activeModel?.runtime || activeModel?.provider || "—"}</span>
          <span>Role: {labelize(activeModel?.role || "main")}</span>
        </div>
      </div>

      {warsatHardware?.detectedHardware?.gpus?.length > 0 && (
        <>
          <h3 className="w2-section-title">GPU Hardware</h3>
          <div className="w2-card">
            {warsatHardware.detectedHardware.gpus.map((gpu, i) => (
              <div key={i} style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>
                <strong style={{ color: "var(--cc-text)" }}>{gpu.name}</strong>
                <div>{gpu.memory_total_mb ? `${(gpu.memory_total_mb / 1024).toFixed(1)} GB VRAM` : "Unknown VRAM"}</div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
