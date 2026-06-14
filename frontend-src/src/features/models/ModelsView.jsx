import React from "react";
import {
  CheckCircle2,
  Cloud,
  Cpu,
  HardDrive,
  KeyRound,
  Play,
  RefreshCw,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Wrench,
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

const deploymentSteps = [
  ["Select", "Choose a managed runtime or connect an existing localhost endpoint."],
  ["Profile", "Pick a VRAM target, quantization preference, context length, and exposed local port."],
  ["Generate", "Create a Docker Compose launch plan and Dockerfile only when the selected runtime needs one."],
  ["Review", "Show mounts, environment variables, ports, and security flags before anything starts."],
  ["Deploy", "Run only after Docker control is enabled and the plan is explicitly approved."],
];

const runtimeOptions = [
  ["vLLM CUDA", "Best for a larger primary chat or coding model with enough VRAM.", "Hugging Face model id"],
  ["llama.cpp GGUF", "Best for smaller helper models, quantized local files, and low VRAM.", "Mounted .gguf file"],
  ["Ollama", "Good for quick local model testing through Ollama's OpenAI-compatible API.", "Ollama model name"],
  ["External local endpoint", "Use LM Studio, Ollama, text-generation-webui, or anything exposing a local /v1 API.", "localhost /v1 endpoint"],
];

const hardwareProfiles = [
  ["Small", "4-8 GB VRAM", "helper, summarize, organize"],
  ["Medium", "10-16 GB VRAM", "chat, analyze, code helper"],
  ["Large", "20+ GB VRAM", "main model, coding, long context"],
  ["Custom", "manual limits", "advanced tuning"],
];

const modelSections = [
  ["overview", "Overview", "active model and readiness"],
  ["catalog", "Catalog", "find deployable models"],
  ["connect", "Connect", "local and API endpoints"],
  ["registry", "Registry", "advanced model controls"],
];

function firstNumber(...values) {
  for (const value of values) {
    const parsed = Number(value);
    if (Number.isFinite(parsed) && parsed > 0) return parsed;
  }
  return 0;
}

function contextWindowFor(model) {
  return firstNumber(
    model?.contextWindow,
    model?.context_window,
    model?.maxModelLen,
    model?.max_model_len,
    model?.settings?.contextWindow,
    model?.limits?.contextWindow,
  );
}

function readinessTone(status) {
  if (["ready", "pass", "reachable", "healthy", "ok", "registered"].includes(status)) return "ready";
  if (["blocked", "fail", "failed", "error", "unreachable"].includes(status)) return "blocked";
  return "warning";
}

function formatContextWindow(value) {
  return value ? `${Number(value).toLocaleString()} tokens` : "Not declared";
}

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
  const activeModel = selectedModelObject || models?.[0] || null;
  const activeName = displayModelName(activeModel, models);
  const secondary = displayModelSecondary(activeModel, models);
  const healthy = isModelHealthy(activeModel);
  const status = runtimeStatus(activeModel);
  const mismatch = modelMismatchLine(activeModel);
  const discovered = discoveredModelIds(activeModel);
  const apiProviders = modelProviders?.length ? modelProviders : [
    { id: "openai", name: "OpenAI", defaultBaseUrl: "https://api.openai.com/v1", defaultKeyEnv: "OPENAI_API_KEY" },
    { id: "anthropic", name: "Anthropic", defaultBaseUrl: "https://api.anthropic.com/v1", defaultKeyEnv: "ANTHROPIC_API_KEY" },
    { id: "gemini", name: "Google Gemini", defaultBaseUrl: "https://generativelanguage.googleapis.com/v1beta", defaultKeyEnv: "GEMINI_API_KEY" },
    { id: "openai-compatible-remote", name: "Other OpenAI-compatible API", defaultBaseUrl: "", defaultKeyEnv: "" },
  ];
  const remoteBlocked = security?.privacyLock || !security?.allowRemoteModels;
  const catalogItems = modelCatalog?.items || [];
  const catalogCategories = modelCatalog?.categories || [];
  const catalogRuntimes = modelCatalog?.runtimes || [];
  const [catalogSearch, setCatalogSearch] = React.useState("");
  const [catalogPurpose, setCatalogPurpose] = React.useState("all");
  const [catalogRuntime, setCatalogRuntime] = React.useState("deployable");
  const [selectedCatalogId, setSelectedCatalogId] = React.useState(catalogItems[0]?.id || "");
  const [modelSection, setModelSection] = React.useState("overview");
  const updateTestingMode = React.useCallback((enabled) => {
    const next = !!enabled;
    setTestingMode(next);
    if (next && models?.some((model) => model.key === "dry-run")) {
      setSelectedModel?.("dry-run");
      return;
    }
    if (!next && selectedModel === "dry-run") {
      const fallback = (models || []).find((model) => model.role === "main" && model.key !== "dry-run")
        || (models || []).find((model) => model.key !== "dry-run" && model.role !== "embeddings");
      if (fallback) setSelectedModel?.(fallback.key);
    }
  }, [models, selectedModel, setSelectedModel, setTestingMode]);
  const filteredCatalogItems = React.useMemo(() => {
    const search = catalogSearch.trim().toLowerCase();
    return catalogItems.filter((item) => {
      const matchesSearch = !search || [
        item.name,
        item.id,
        item.modelId,
        item.provider,
        item.purpose,
        ...(item.capabilities || []),
      ].join(" ").toLowerCase().includes(search);
      const matchesPurpose = catalogPurpose === "all" || item.purpose === catalogPurpose;
      const options = item.runtimeOptions || [];
      const matchesRuntime = catalogRuntime === "all"
        || (catalogRuntime === "deployable" && item.deployable)
        || options.some((option) => option.protocolId === catalogRuntime);
      return matchesSearch && matchesPurpose && matchesRuntime;
    });
  }, [catalogItems, catalogPurpose, catalogRuntime, catalogSearch]);
  const selectedCatalogModel = filteredCatalogItems.find((item) => item.id === selectedCatalogId)
    || filteredCatalogItems[0]
    || catalogItems[0];
  const contextWindow = contextWindowFor(activeModel);
  const contextStatus = activeModel?.key === "dry-run"
    ? "ready"
    : contextWindow >= 4096
      ? "ready"
      : contextWindow >= 1024
        ? "warning"
        : "warning";
  const contextText = activeModel?.key === "dry-run"
    ? "Testing Mode uses Rasputin's internal dry-run path."
    : contextWindow >= 4096
      ? "Enough room for normal chat and retrieved local context."
      : contextWindow >= 1024
        ? "Small context window. Rasputin will trim workspace and retrieval context aggressively."
        : "No context window is declared. Rasputin will assume a conservative local budget.";
  const endpointKind = activeModel?.provider?.includes("remote")
    ? "Remote API"
    : activeModel?.url || activeModel?.baseUrl
      ? "Local endpoint"
      : activeModel?.key === "dry-run"
        ? "Testing Mode"
        : "Endpoint missing";
  const warsatStatus = warsatHardware?.status || (warsat?.count ? "warning" : "warning");
  const warsatRuntimeCount = warsatRuntimes?.count ?? warsatRuntimes?.containers?.length ?? 0;
  const hasLaunchPlan = Boolean(warsatPlan);
  const readinessItems = [
    {
      id: "active-model",
      title: "Active chat model",
      value: activeName,
      detail: healthy ? `${activeName} is reachable.` : modelMismatchLine(activeModel) || activeModel?.lastError || "Health check has not passed yet.",
      status: healthy ? "ready" : "blocked",
      action: "Test health",
      onAction: () => runModelAction("test"),
    },
    {
      id: "vllm-discovery",
      title: "vLLM discovery and repair",
      value: discovered.length ? `${discovered.length} model${discovered.length === 1 ? "" : "s"} discovered` : "No discovery result yet",
      detail: mismatch || "Use discovery to verify the endpoint model id matches Rasputin's registry.",
      status: mismatch ? "blocked" : discovered.length ? "ready" : "warning",
      action: mismatch ? "Repair mismatch" : "Discover vLLM",
      onAction: () => runModelAction(mismatch ? "repair" : "discover"),
    },
    {
      id: "context-window",
      title: "Context window",
      value: formatContextWindow(contextWindow),
      detail: contextText,
      status: contextStatus,
    },
    {
      id: "warsat-readiness",
      title: "Warsat hardware",
      value: warsatHardware ? labelize(warsatHardware.status || "unknown") : "Not checked",
      detail: `${warsatRuntimeCount} managed runtime${warsatRuntimeCount === 1 ? "" : "s"} detected. Docker control is ${warsat?.dockerControlEnabled ? "enabled" : "off by default"}.`,
      status: readinessTone(warsatStatus),
      action: "Open Warsat",
      onAction: openWarsat,
    },
    {
      id: "launch-plan",
      title: "Launch-plan readiness",
      value: hasLaunchPlan ? "Plan prepared" : selectedCatalogModel?.deployable ? "Catalog model selected" : "No deployable model selected",
      detail: hasLaunchPlan
        ? "Review and approve the plan in Warsat before any container starts."
        : selectedCatalogModel?.deployable
          ? "Send the selected catalog model to Warsat to generate a reviewed plan."
          : "Pick a Warsat-ready catalog model before deployment planning.",
      status: hasLaunchPlan || selectedCatalogModel?.deployable ? "ready" : "warning",
      action: selectedCatalogModel?.deployable ? "Prepare in Warsat" : "Open Warsat",
      onAction: selectedCatalogModel?.deployable ? () => prepareCatalogModelForWarsat?.(selectedCatalogModel) : openWarsat,
    },
  ];
  const selectedSection = modelSections.find(([id]) => id === modelSection) || modelSections[0];
  const moveModelSection = React.useCallback((direction) => {
    const current = modelSections.findIndex(([id]) => id === modelSection);
    const next = (current + direction + modelSections.length) % modelSections.length;
    setModelSection(modelSections[next][0]);
  }, [modelSection]);
  const handleModelSectionKeyDown = React.useCallback((event) => {
    if (event.key === "ArrowDown" || event.key === "ArrowRight") {
      event.preventDefault();
      moveModelSection(1);
    }
    if (event.key === "ArrowUp" || event.key === "ArrowLeft") {
      event.preventDefault();
      moveModelSection(-1);
    }
    if (event.key === "Home") {
      event.preventDefault();
      setModelSection(modelSections[0][0]);
    }
    if (event.key === "End") {
      event.preventDefault();
      setModelSection(modelSections[modelSections.length - 1][0]);
    }
  }, [moveModelSection]);

  return (
    <section className={`app-view models-view ${view === "models" ? "active" : ""}`} id="modelsView" data-app-view="models">
      <header className="page-header models-header">
        <div>
          <h1>Models</h1>
          <p>Inspect the active local model and plan model containers without leaving Rasputin.</p>
        </div>
        <div className="models-header-actions">
          <button className="ras-button ghost" type="button" onClick={loadModels}>
            <RefreshCw size={17} aria-hidden="true" />
            Refresh registry
          </button>
          <button className="ras-button primary" type="button" onClick={() => runModelAction("discover")}>
            <Search size={17} aria-hidden="true" />
            Discover vLLM
          </button>
        </div>
      </header>

      <div className="models-content gui-workspace models-gui-workspace">
        <aside className="gui-sidebar models-gui-sidebar models-nav-panel" aria-label="Model sections">
          <section className="model-section-card">
            <span className="eyebrow">Model Workspace</span>
            <h2>{selectedSection[1]}</h2>
            <p>{selectedSection[2]}</p>
            <div className="model-section-status">
              <span className={`model-health-pill ${healthy ? "is-healthy" : "is-unhealthy"}`}>
                {healthy ? "Reachable" : labelize(status)}
              </span>
              <strong>{activeModel?.model || activeName}</strong>
              <small>{endpointKind}</small>
            </div>
          </section>
          <nav
            className="model-section-tabs"
            aria-label="Model page sections"
            role="tablist"
            aria-orientation="vertical"
            onKeyDown={handleModelSectionKeyDown}
          >
            {modelSections.map(([id, label, help]) => (
              <button
                className={`model-section-tab ${modelSection === id ? "is-active" : ""}`}
                type="button"
                role="tab"
                id={`model-section-${id}`}
                aria-selected={modelSection === id}
                aria-controls={`model-panel-${id}`}
                tabIndex={modelSection === id ? 0 : -1}
                onClick={() => setModelSection(id)}
                data-testid="model-section-tab"
                key={id}
              >
                <span>{label}</span>
                <small>{help}</small>
              </button>
            ))}
          </nav>
        </aside>

        <div className="gui-main models-gui-main" role="tabpanel" id={`model-panel-${modelSection}`} aria-labelledby={`model-section-${modelSection}`}>
        {modelSection === "overview" && (
        <>
        <section className="model-readiness-panel" aria-labelledby="modelReadinessTitle" data-testid="model-readiness-panel">
          <div className="model-readiness-head">
            <div>
              <span className="eyebrow">Runtime Readiness</span>
              <h2 id="modelReadinessTitle">Connect, verify, then plan deployment.</h2>
              <p>
                Follow these checks before private testing. Rasputin keeps the actual model id visible and only moves
                into Warsat deployment after a reviewed launch plan exists.
              </p>
            </div>
            <div className="model-readiness-summary" role="status" aria-live="polite">
              <span className={`model-health-pill ${healthy ? "is-healthy" : "is-unhealthy"}`}>
                {healthy ? "Chat ready" : "Chat blocked"}
              </span>
              <strong>{endpointKind}</strong>
            </div>
          </div>
          <div className="model-readiness-grid">
            {readinessItems.map((item) => (
              <article className={`model-readiness-step is-${item.status}`} key={item.id}>
                <div>
                  <span>{item.title}</span>
                  <strong>{item.value}</strong>
                  <p>{item.detail}</p>
                </div>
                {item.action && (
                  <button
                    className="ras-button small-button"
                    type="button"
                    onClick={item.onAction}
                    aria-label={`${item.action}: ${item.title}`}
                  >
                    {item.action}
                  </button>
                )}
              </article>
            ))}
          </div>
        </section>

        <section className="models-grid">
          <article className="model-command-card" data-testid="active-model-card" id="models-active-card">
            <div className="model-command-top">
              <span className="model-glyph" aria-hidden="true"><Cpu size={22} /></span>
              <div>
                <span className="eyebrow">Active Chat Model</span>
                <h2>{activeName}</h2>
                {secondary && <p>{secondary}</p>}
              </div>
              <span className={`model-health-pill ${healthy ? "is-healthy" : "is-unhealthy"}`}>
                {healthy ? "Reachable" : labelize(status)}
              </span>
            </div>

            <div className="model-truth-grid">
              <div>
                <span>Configured model id</span>
                <strong>{activeModel?.model || "No model configured"}</strong>
              </div>
              <div>
                <span>Endpoint</span>
                <strong>{activeModel?.url || activeModel?.baseUrl || "Local endpoint not set"}</strong>
              </div>
              <div>
                <span>Runtime</span>
                <strong>{activeModel?.runtime || activeModel?.provider || "local"}</strong>
              </div>
              <div>
                <span>Last health</span>
                <strong>{runtimeStatus(activeModel)}</strong>
              </div>
            </div>

            {mismatch && (
              <div className="model-warning" role="status">
                <Wrench size={17} aria-hidden="true" />
                <span>{mismatch}</span>
              </div>
            )}

            {!mismatch && activeModel?.lastError && (
              <div className="model-warning" role="status">
                <Wrench size={17} aria-hidden="true" />
                <span>{activeModel.lastError}</span>
              </div>
            )}

            {!!discovered.length && (
              <div className="model-discovery-list">
                <span>Discovered</span>
                {discovered.slice(0, 4).map((id) => <code key={id}>{id}</code>)}
              </div>
            )}

            <div className="model-action-row">
              <button className="ras-button" type="button" onClick={() => runModelAction("test")}>
                <CheckCircle2 size={17} aria-hidden="true" />
                Test health
              </button>
              <button className="ras-button" type="button" onClick={() => runModelAction("repair")}>
                <Wrench size={17} aria-hidden="true" />
                Use discovered model
              </button>
              <button className="ras-button" type="button" data-testid="gguf-scan" onClick={scanGguf}>
                <HardDrive size={17} aria-hidden="true" />
                Scan GGUF library
              </button>
            </div>
          </article>

          <aside className="model-health-card">
            <span className="eyebrow">Safety State</span>
            <h2>Local runtime control stays gated.</h2>
            <p>
              Rasputin prepares and deploys Docker model runtimes through Warsat. Starting containers stays behind
              Docker-control permission and an explicit approval step.
            </p>
            <div className="safety-stack">
              <span><ShieldCheck size={16} aria-hidden="true" /> Ports bind to 127.0.0.1</span>
              <span><ShieldCheck size={16} aria-hidden="true" /> Model mounts default read-only</span>
              <span><ShieldCheck size={16} aria-hidden="true" /> Compose plans are previewed first</span>
            </div>
          </aside>
        </section>
        </>
        )}

        {modelSection === "catalog" && (
        <section className="model-catalog-panel" aria-labelledby="modelCatalogTitle" data-testid="models-dev-catalog">
          <div className="model-catalog-head">
            <div>
              <span className="eyebrow">Model Catalog</span>
              <h2 id="modelCatalogTitle">Choose a model, then prepare it in Warsat</h2>
              <p>
                Rasputin keeps a local deployable shortlist and can refresh public metadata from models.dev.
                API-only entries stay out of Warsat unless they have a real local runtime target.
              </p>
            </div>
            <div className="model-catalog-actions">
              <button className="ras-button" type="button" onClick={() => loadModelCatalog?.(false)}>
                <RefreshCw size={17} aria-hidden="true" />
                Load local catalog
              </button>
              <button className="ras-button primary" type="button" onClick={() => loadModelCatalog?.(true)} disabled={modelCatalogLoading}>
                <Cloud size={17} aria-hidden="true" />
                {modelCatalogLoading ? "Refreshing..." : "Refresh models.dev"}
              </button>
            </div>
          </div>

          <div className="model-catalog-meta" role="status">
            <span>{modelCatalog?.count || catalogItems.length || 0} models</span>
            <span>{modelCatalog?.deployableCount || 0} Warsat-ready</span>
            <span>Source: {modelCatalog?.source?.status || "local fallback"}</span>
            {modelCatalogError && <strong>{modelCatalogError}</strong>}
          </div>

          <div className="model-catalog-layout">
            <aside className="model-catalog-filters" aria-label="Model catalog filters">
              <label>
                <span>Search</span>
                <input
                  value={catalogSearch}
                  onChange={(event) => setCatalogSearch(event.target.value)}
                  placeholder="coder, 7b, vision, qwen"
                />
              </label>
              <label>
                <span>Use</span>
                <select value={catalogPurpose} onChange={(event) => setCatalogPurpose(event.target.value)}>
                  <option value="all">All uses</option>
                  {catalogCategories.map((category) => (
                    <option key={category.id} value={category.id}>{category.label}</option>
                  ))}
                </select>
              </label>
              <label>
                <span>Runtime</span>
                <select value={catalogRuntime} onChange={(event) => setCatalogRuntime(event.target.value)}>
                  <option value="deployable">Warsat-ready</option>
                  <option value="all">All catalog entries</option>
                  {catalogRuntimes.map((runtime) => (
                    <option key={runtime.id} value={runtime.id}>{runtime.label}</option>
                  ))}
                </select>
              </label>
              <button
                className="ras-button ghost"
                type="button"
                onClick={() => {
                  setCatalogSearch("");
                  setCatalogPurpose("all");
                  setCatalogRuntime("deployable");
                }}
              >
                Clear filters
              </button>
            </aside>

            <div className="model-catalog-list" aria-label="Model catalog results">
              {filteredCatalogItems.slice(0, 36).map((item) => (
                <button
                  className={`model-catalog-row ${selectedCatalogModel?.id === item.id ? "is-selected" : ""}`}
                  key={item.id}
                  type="button"
                  onClick={() => setSelectedCatalogId(item.id)}
                  data-testid="catalog-model-card"
                >
                  <span>
                    <strong>{item.name}</strong>
                    <small>{item.modelId || item.id}</small>
                  </span>
                  <span className="model-catalog-row-meta">
                    <em>{labelize(item.purpose || "chat")}</em>
                    <em>{item.fitLabel ? `${item.fitLabel} ${item.fitScore ?? ""}`.trim() : "Fit unknown"}</em>
                    <em>{item.vramEstimateGb ? `${item.vramEstimateGb} GB est.` : "VRAM unknown"}</em>
                    <em>{item.deployable ? "Warsat-ready" : "API only"}</em>
                  </span>
                </button>
              ))}
              {!filteredCatalogItems.length && (
                <div className="model-catalog-empty">No models match those filters.</div>
              )}
            </div>

            <aside className="model-catalog-detail" aria-label="Selected catalog model">
              {selectedCatalogModel ? (
                <>
                  <span className="eyebrow">{selectedCatalogModel.source || "catalog"}</span>
                  <h3>{selectedCatalogModel.name}</h3>
                  <p>{selectedCatalogModel.summary || "No summary available."}</p>
                  <dl className="model-catalog-detail-grid">
                    <dt>Model id</dt><dd>{selectedCatalogModel.modelId || selectedCatalogModel.id}</dd>
                    <dt>Provider</dt><dd>{selectedCatalogModel.provider}</dd>
                    <dt>Use</dt><dd>{labelize(selectedCatalogModel.purpose || "chat")}</dd>
                    <dt>Context</dt><dd>{selectedCatalogModel.contextWindow ? Number(selectedCatalogModel.contextWindow).toLocaleString() : "Unknown"}</dd>
                    <dt>VRAM</dt><dd>{selectedCatalogModel.vramEstimateGb ? `${selectedCatalogModel.vramEstimateGb} GB estimated` : "Unknown"}</dd>
                    <dt>Fit</dt><dd>{selectedCatalogModel.fitLabel ? `${selectedCatalogModel.fitLabel} (${selectedCatalogModel.fitScore ?? 0})` : "Unknown"}</dd>
                    <dt>Runtime</dt><dd>{selectedCatalogModel.recommendedProtocol || "API only"}</dd>
                  </dl>
                  {!!(selectedCatalogModel.fitReasons || selectedCatalogModel.blockedReasons || []).length && (
                    <ul className="model-catalog-note-list">
                      {[...(selectedCatalogModel.blockedReasons || []), ...(selectedCatalogModel.fitReasons || [])].slice(0, 4).map((reason) => (
                        <li key={reason}>{reason}</li>
                      ))}
                    </ul>
                  )}
                  <div className="model-catalog-capabilities">
                    {(selectedCatalogModel.capabilities || []).slice(0, 8).map((capability) => (
                      <span key={capability}>{labelize(capability)}</span>
                    ))}
                  </div>
                  <button
                    className="ras-button primary"
                    type="button"
                    disabled={!selectedCatalogModel.deployable}
                    onClick={() => prepareCatalogModelForWarsat?.(selectedCatalogModel)}
                    data-testid="catalog-send-to-warsat"
                  >
                    <Play size={17} aria-hidden="true" />
                    {selectedCatalogModel.deployable ? "Prepare in Warsat" : "API-only model"}
                  </button>
                  {!selectedCatalogModel.deployable && (
                    <small className="model-catalog-note">Register API-only models in the API Providers section below.</small>
                  )}
                </>
              ) : (
                <p>No model selected.</p>
              )}
            </aside>
          </div>
        </section>
        )}

        {modelSection === "overview" && (
        <section className="model-builder-panel" aria-labelledby="modelBuilderTitle">
          <div className="section-row">
            <div>
              <span className="eyebrow">Warsat Deployment Plan</span>
              <h2 id="modelBuilderTitle">Generate and deploy model containers with Warsat</h2>
              <p>
                Use Warsat to select a runtime, choose hardware limits, review the Docker command, request approval,
                and deploy a local-only model endpoint.
              </p>
            </div>
            <button className="ras-button primary" type="button" onClick={openWarsat}>
              <Play size={17} aria-hidden="true" />
              Open Warsat
            </button>
          </div>

          <details className="model-plan-details">
            <summary>Show deployment details</summary>
            <div className="deployment-layout">
              <div className="deployment-column">
                <h3>Runtime choices</h3>
                <div className="runtime-option-grid">
                  {runtimeOptions.map(([name, text, input]) => (
                    <article className="runtime-option" key={name}>
                      <strong>{name}</strong>
                      <p>{text}</p>
                      <small>{input}</small>
                    </article>
                  ))}
                </div>
              </div>

              <div className="deployment-column">
                <h3>Hardware profiles</h3>
                <div className="hardware-profile-grid">
                  {hardwareProfiles.map(([name, vram, usage]) => (
                    <article className="hardware-profile" key={name}>
                      <span>{name}</span>
                      <strong>{vram}</strong>
                      <small>{usage}</small>
                    </article>
                  ))}
                </div>
              </div>
            </div>

            <ol className="deployment-steps">
              {deploymentSteps.map(([title, text]) => (
                <li key={title}>
                  <span>{title}</span>
                  <p>{text}</p>
                </li>
              ))}
            </ol>
          </details>
        </section>
        )}

        {modelSection === "connect" && (
        <>
        <details className="advanced-block model-builder-panel local-model-panel" data-testid="local-model-advanced">
          <summary>
            <span>Connect a local endpoint</span>
            <small>LM Studio, Ollama, text-generation-webui, or another localhost server</small>
          </summary>
          <div className="section-row" aria-labelledby="localModelTitle">
            <div>
              <span className="eyebrow">Local Endpoint</span>
              <h2 id="localModelTitle">Connect any OpenAI-compatible localhost model</h2>
              <p>
                Use this for models Rasputin does not launch itself: LM Studio, Ollama, text-generation-webui,
                a custom server, or another local wrapper. The endpoint must stay local while privacy lock is on.
              </p>
            </div>
          </div>
          <form className="local-model-form" onSubmit={registerLocalModel} data-testid="local-model-form">
            <label>
              <span>Display name</span>
              <input name="name" placeholder="My Local Coder" />
            </label>
            <label>
              <span>Model id</span>
              <input name="model" placeholder="qwen2.5-coder:7b" required />
            </label>
            <label>
              <span>Base endpoint</span>
              <input name="baseUrl" placeholder="http://127.0.0.1:1234/v1" required />
            </label>
            <label>
              <span>Purpose</span>
              <select name="role" defaultValue="helper">
                <option value="main">Main</option>
                <option value="planner">Planner</option>
                <option value="executor">Executor</option>
                <option value="coder">Coder</option>
                <option value="researcher">Researcher</option>
                <option value="summarizer">Summarizer</option>
                <option value="memory">Memory</option>
                <option value="helper">Helper</option>
              </select>
            </label>
            <label>
              <span>Provider</span>
              <select name="provider" defaultValue="openai-compatible">
                <option value="openai-compatible">OpenAI-compatible</option>
                <option value="ollama">Ollama</option>
                <option value="lm-studio">LM Studio</option>
                <option value="text-generation-webui">text-generation-webui</option>
                <option value="custom-local">Custom local</option>
              </select>
            </label>
            <label>
              <span>Context window</span>
              <input name="contextWindow" type="number" min="512" placeholder="4096" />
            </label>
            <label>
              <span>Max output tokens</span>
              <input name="maxTokens" type="number" min="1" placeholder="512" />
            </label>
            <label className="local-model-notes">
              <span>Notes</span>
              <input name="notes" placeholder="Started outside Rasputin" />
            </label>
            <div className="local-model-actions">
              <button className="ras-button primary" type="submit">
                <CheckCircle2 size={17} aria-hidden="true" />
                Connect local model
              </button>
              <small>After connecting, use Test health to verify `/models` and chat completion support.</small>
            </div>
          </form>
        </details>

        <details className="advanced-block model-builder-panel api-model-panel" data-testid="api-model-advanced">
          <summary>
            <span>Connect an API provider</span>
            <small>External providers stay blocked while Privacy Lock is enabled</small>
          </summary>
          <div className="section-row" aria-labelledby="apiModelTitle">
            <div>
              <span className="eyebrow">API Providers</span>
              <h2 id="apiModelTitle">Connect OpenAI, Anthropic, Gemini, or another API</h2>
              <p>
                Use this only when you intentionally want Rasputin to call an external provider. Keys are stored as
                environment references or in Rasputin's ignored local secret store, never in the model registry.
              </p>
            </div>
            <span className={`model-health-pill ${remoteBlocked ? "is-unhealthy" : "is-healthy"}`}>
              {remoteBlocked ? "Remote blocked" : "Remote allowed"}
            </span>
          </div>
          {remoteBlocked && (
            <div className="model-warning" role="status">
              <ShieldCheck size={17} aria-hidden="true" />
              <span>Safety currently blocks remote model endpoints. Disable Privacy lock and enable Remote models before testing an API provider.</span>
            </div>
          )}
          <form className="local-model-form" onSubmit={registerApiModel} data-testid="api-model-form">
            <label>
              <span>Provider</span>
              <select name="provider" defaultValue="openai">
                {apiProviders.map((provider) => (
                  <option value={provider.id} key={provider.id}>{provider.name}</option>
                ))}
              </select>
            </label>
            <label>
              <span>Display name</span>
              <input name="name" placeholder="Claude Writer" />
            </label>
            <label>
              <span>Model id</span>
              <input name="model" placeholder="gpt-4o-mini / claude-3-5-sonnet-20241022 / gemini-2.5-flash" required />
            </label>
            <label>
              <span>Base endpoint</span>
              <input name="baseUrl" placeholder="Leave blank for provider default" />
            </label>
            <label>
              <span>Purpose</span>
              <select name="role" defaultValue="helper">
                <option value="main">Main</option>
                <option value="planner">Planner</option>
                <option value="executor">Executor</option>
                <option value="coder">Coder</option>
                <option value="researcher">Researcher</option>
                <option value="summarizer">Summarizer</option>
                <option value="memory">Memory</option>
                <option value="helper">Helper</option>
              </select>
            </label>
            <label>
              <span>API key environment variable</span>
              <input name="apiKeyEnv" placeholder="OPENAI_API_KEY" />
            </label>
            <label>
              <span>Or local secret key</span>
              <input name="apiKey" type="password" autoComplete="off" placeholder="Stored in ignored local secrets" />
            </label>
            <label>
              <span>Anthropic version</span>
              <input name="anthropicVersion" placeholder="2023-06-01" />
            </label>
            <label>
              <span>Context window</span>
              <input name="contextWindow" type="number" min="512" placeholder="8192" />
            </label>
            <label>
              <span>Max output tokens</span>
              <input name="maxTokens" type="number" min="1" placeholder="512" />
            </label>
            <label className="local-model-notes">
              <span>Notes</span>
              <input name="notes" placeholder="External API; do not use for private local files" />
            </label>
            <div className="local-model-actions">
              <button className="ras-button primary" type="submit">
                <KeyRound size={17} aria-hidden="true" />
                Register API model
              </button>
              <small>Use env vars for shared setups. Use the local secret field for one-machine testing only.</small>
            </div>
          </form>
          <div className="api-provider-grid" aria-label="Supported API provider styles">
            {apiProviders.map((provider) => (
              <article className="runtime-option" key={provider.id}>
                <strong><Cloud size={15} aria-hidden="true" /> {provider.name}</strong>
                <p>{provider.apiStyle || "OpenAI-compatible"}</p>
                <small>{provider.defaultKeyEnv || "custom key source"}</small>
              </article>
            ))}
          </div>
        </details>
        </>
        )}

        {modelSection === "registry" && (
        <details className="advanced-model-registry" data-testid="advanced-model-registry">
          <summary data-testid="advanced-model-registry-toggle">
            <SlidersHorizontal size={17} aria-hidden="true" />
            Advanced model registry
          </summary>
          <div className="advanced-model-body">
            <div className="testing-mode-control">
              <label className="testing-mode-label">
                <input
                  data-testid="testing-mode-toggle"
                  type="checkbox"
                  checked={testingMode}
                  onClick={(event) => updateTestingMode(event.currentTarget.checked)}
                  onInput={(event) => updateTestingMode(event.currentTarget.checked)}
                  onChange={(event) => updateTestingMode(event.currentTarget.checked)}
                />
                <span>
                  <strong>Testing Mode</strong>
                  <small>Show dry-run in the chat model picker and select it for local smoke tests.</small>
                </span>
              </label>
              <button
                className="ras-button ghost small-button"
                type="button"
                data-testid="testing-mode-action"
                aria-label={testingMode ? "Disable Testing Mode" : "Enable Testing Mode"}
                onClick={() => updateTestingMode(!testingMode)}
              >
                {testingMode ? "Disable" : "Enable"}
              </button>
            </div>
            <div id="modelRegistry" className="model-list registry-grid">
              {(models || []).map((model) => (
                <article className="model-row registry-row" key={model.key}>
                  <strong>{displayModelName(model, models)}</strong>
                  <dl className="model-meta-grid mb-0">
                    <dt>Purpose</dt><dd>{labelize(model.role || "chat")}</dd>
                    <dt>Runtime</dt><dd>{model.runtime || model.provider || "local"}</dd>
                    <dt>Health</dt><dd>{runtimeStatus(model)}</dd>
                    {model.runtime === "remote-api" && <><dt>API key</dt><dd>{model.hasApiKey ? `Configured (${model.apiKeySource || "secret"})` : "Missing"}</dd></>}
                    <dt>Key</dt><dd>{model.key}</dd>
                  </dl>
                </article>
              ))}
            </div>
          </div>
        </details>
        )}
        </div>
      </div>
    </section>
  );
}
