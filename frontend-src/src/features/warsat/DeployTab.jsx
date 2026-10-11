import React from "react";
import { AlertTriangle, CheckCircle2, Gauge, SlidersHorizontal, Zap } from "lucide-react";

import { labelize } from "../../lib/display.js";

import { api, postJson } from "../../api/client.js";

import { PlanPreview } from "./PlanPreview.jsx";

export const PIPELINE_STEPS = [
  { id: "planned",         label: "Plan" },
  { id: "approvalPending", label: "Approve" },
  { id: "pulling",         label: "Pull" },
  { id: "starting",        label: "Start" },
  { id: "registered",      label: "Register" },
];

export function DeployTab({
  warsat, hardware, protocols, strengthProfiles, protocolId, setProtocolId,
  strengthProfile, setStrengthProfile, selectedProtocol, selectedProfile,
  warsatCatalogItems, selectedCatalogModel, setSelectedCatalogId,
  prepareCatalogModelForWarsat,
  createPlan, plan, error, clearPlan, handleFormChange,
  deployPlan, deploying, deployment, deployLabel, deployDisabled, canDeployPlan,
  approvalPending, approvalClosed, approvalStatus, currentApproval,
  approveApproval, denyApproval, lifecycle,
  runtimeStrategyLabel, enableDockerControl, go,
}) {
  const formRef = React.useRef(null);
  const briefRef = React.useRef(null);
  const [advisor, setAdvisor] = React.useState(null);
  const [advisorBusy, setAdvisorBusy] = React.useState(false);
  const [advisorError, setAdvisorError] = React.useState("");
  const activePhase = deployment?.phase || plan?.phase || "";
  const modelContainerName = deployment?.containerName || plan?.containerName || "";
  const shouldPollDownload = Boolean(
    modelContainerName
    && (deploying || deployment?.status === "starting" || deployment?.phase === "probing")
  );
  const [downloadProgress, setDownloadProgress] = React.useState(null);

  React.useEffect(() => {
    if (!shouldPollDownload) {
      setDownloadProgress(null);
      return undefined;
    }
    let isSubscribed = true;
    let timer = null;
    async function poll() {
      try {
        const progress = await api(`/api/warsat/download-progress?containerName=${encodeURIComponent(modelContainerName)}`);
        if (isSubscribed) setDownloadProgress(progress);
      } catch (err) {
        // The container may not exist during the image-pull phase. Keep the
        // deployment stream authoritative and retry on the next interval.
      }
      if (isSubscribed) timer = setTimeout(poll, 5000);
    }
    poll();
    return () => {
      isSubscribed = false;
      if (timer) clearTimeout(timer);
    };
  }, [modelContainerName, shouldPollDownload]);

  async function analyzeSelectedModel() {
    if (!selectedCatalogModel) return;
    setAdvisorBusy(true);
    setAdvisorError("");
    try {
      setAdvisor(await postJson("/api/warsat/advisor", {
        model: selectedCatalogModel,
        hardware,
        mission: selectedCatalogModel.purpose || "chat",
        protocolId: selectedCatalogModel.recommendedProtocol,
        contextWindow: selectedCatalogModel.contextWindow,
        toolCallParser: selectedCatalogModel.toolCallParserHint,
      }));
    } catch (err) {
      setAdvisor(null);
      setAdvisorError(err.message || String(err));
    } finally {
      setAdvisorBusy(false);
    }
  }

  async function createAdvisorPlan() {
    if (!selectedCatalogModel || !advisor || advisor.blockers?.length) return;
    await prepareCatalogModelForWarsat?.(selectedCatalogModel, {
      protocolId: advisor.planSeed?.protocolId,
      toolCallParser: advisor.planSeed?.toolCallParser,
    });
  }

  // Bring the Mission Brief into view whenever a plan lands — it renders
  // below the recipe form, and without the scroll a generate click looks
  // like nothing happened.
  React.useEffect(() => {
    if (plan && briefRef.current) {
      briefRef.current.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [plan]);

  // Sync the recipe form to each NEW plan (keyed by planId). Filling only
  // empty fields left the previous model's values behind, so sending a
  // second model from the catalog still showed — and regenerated — the
  // first one.
  const lastPlanIdRef = React.useRef(null);
  React.useEffect(() => {
    if (!plan || !formRef.current) return;
    if (lastPlanIdRef.current === plan.planId) return;
    lastPlanIdRef.current = plan.planId;
    const els = formRef.current.elements;
    if (els.modelRef) els.modelRef.value = plan.modelRef || "";
    if (els.modelPath) els.modelPath.value = plan.modelPath || "";
    if (els.hostPort) els.hostPort.value = plan.hostPort || "";
    if (els.role && plan.role) els.role.value = plan.role;
  }, [plan]);

  /* Derive which pipeline step is active/done */
  const stepStatus = (stepId) => {
    const phaseOrder = PIPELINE_STEPS.map(s => s.id);
    const activeIdx = phaseOrder.indexOf(activePhase);
    const stepIdx = phaseOrder.indexOf(stepId);
    if (!plan && !deployment) return "pending";
    if (stepIdx < activeIdx) return "done";
    if (stepIdx === activeIdx) return "active";
    return "pending";
  };

  return (
    <div className="w2-section" style={{ flex: 1 }}>

      {/* ── Pipeline Stepper ── */}
      {(plan || deployment) && (
        <div className="ws-pipeline-stepper">
          {PIPELINE_STEPS.map((step, i) => {
            const st = stepStatus(step.id);
            return (
              <React.Fragment key={step.id}>
                <div className={`ws-pipeline-step is-${st}`}>
                  <div className="ws-pipeline-dot">
                    {st === "done" ? <CheckCircle2 size={14} /> : <span>{i + 1}</span>}
                  </div>
                  <span>{step.label}</span>
                </div>
                {i < PIPELINE_STEPS.length - 1 && (
                  <div className={`ws-pipeline-connector ${st === "done" ? "is-done" : ""}`} />
                )}
              </React.Fragment>
            );
          })}
        </div>
      )}

      <div className="ws-mission-recipe" data-testid="warsat-advisor">
        <div className="ws-recipe-header">
          <Gauge size={14} />
          <span>WarSat Advisor</span>
          <span className="ws-protocol-hint">Observed hardware · deterministic fit · no deployment</span>
        </div>
        <div className="ws-recipe-form">
          <label className="ws-recipe-field" style={{ gridColumn: "1 / -1" }}>
            <span>Catalog model</span>
            <select
              className="w2-input"
              value={selectedCatalogModel?.id || ""}
              onChange={(event) => {
                setSelectedCatalogId(event.target.value);
                setAdvisor(null);
                setAdvisorError("");
              }}
            >
              {(warsatCatalogItems || []).map((item) => (
                <option key={item.id} value={item.id}>{item.name} · {item.fitLabel || "unscored"}</option>
              ))}
            </select>
          </label>
          <div className="ws-recipe-actions" style={{ gridColumn: "1 / -1" }}>
            <button className="w2-button" type="button" onClick={analyzeSelectedModel} disabled={!selectedCatalogModel || advisorBusy}>
              <Gauge size={14} /> {advisorBusy ? "Analyzing…" : "Analyze fit"}
            </button>
            {advisor && !advisor.blockers?.length && (
              <button className="w2-button primary" type="button" onClick={createAdvisorPlan}>
                <Zap size={14} /> Create approval-gated plan
              </button>
            )}
          </div>
        </div>
        {advisorError && <div className="ws-recipe-error"><AlertTriangle size={13} /> {advisorError}</div>}
        {advisor && (
          <div className="mt-3 grid gap-3 md:grid-cols-3" data-testid="warsat-advisor-result">
            <div className="glow-card rounded-xl border border-border bg-card p-3">
              <div className="eyebrow">Verdict</div>
              <strong>{labelize(advisor.status)}</strong>
              <div className="text-xs text-muted-foreground">{advisor.evidence?.confidence || "low"} confidence</div>
            </div>
            <div className="glow-card rounded-xl border border-border bg-card p-3">
              <div className="eyebrow">Observed</div>
              <strong>{advisor.evidence?.observed?.aggregateVramGb ?? "Unknown"} GB VRAM</strong>
              <div className="text-xs text-muted-foreground">{advisor.evidence?.observed?.gpus?.length || 0} visible GPU(s)</div>
            </div>
            <div className="glow-card rounded-xl border border-border bg-card p-3">
              <div className="eyebrow">Estimated</div>
              <strong>{advisor.evidence?.estimated?.modelVramGb ?? "Unknown"} GB demand</strong>
              <div className="text-xs text-muted-foreground">{advisor.evidence?.estimated?.vramMarginGb ?? "Unknown"} GB margin</div>
            </div>
            {!!advisor.blockers?.length && (
              <div className="md:col-span-3 rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-sm" role="alert">
                <strong>Blocked</strong>
                <ul className="mb-0 mt-2">{advisor.blockers.map((item) => <li key={item}>{item}</li>)}</ul>
              </div>
            )}
            {!![...(advisor.warnings || []), ...(advisor.assumptions || [])].length && (
              <div className="md:col-span-3 rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-sm">
                <strong>What remains uncertain</strong>
                <ul className="mb-0 mt-2">{[...(advisor.warnings || []), ...(advisor.assumptions || [])].map((item) => <li key={item}>{item}</li>)}</ul>
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── Launch Recipe Form ── */}
      <div className="ws-mission-recipe">
        <div className="ws-recipe-header">
          <SlidersHorizontal size={14} />
          <span>Launch Recipe</span>
          {runtimeStrategyLabel && (
            <span className="ws-protocol-hint">Runtime strategy: {runtimeStrategyLabel}</span>
          )}
          {protocols.length > 0 && (
            <span className="ws-protocol-hint">{selectedProtocol?.runtime || ""}</span>
          )}
        </div>
        <form ref={formRef} onSubmit={createPlan} onChange={handleFormChange} className="ws-recipe-form">
          <label className="ws-recipe-field">
            <span>Protocol</span>
            <select className="w2-input" name="protocolId" value={protocolId} onChange={e => setProtocolId(e.target.value)} required>
              <option value="" disabled>Choose protocol</option>
              {protocols.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </label>
          <label className="ws-recipe-field">
            <span>{selectedProtocol?.modelFormat === "gguf" ? "Model Name (Optional)" : selectedProtocol?.id === "ollamaOpenaiServer" ? "Ollama Model" : "Model ID (HuggingFace)"}</span>
            <input className="w2-input" name="modelRef" placeholder="e.g. Qwen/Qwen2.5-7B-Instruct" />
          </label>
          {selectedProtocol?.modelFormat === "gguf" && (
            <label className="ws-recipe-field" style={{ gridColumn: "1 / -1" }}>
              <span>Model Path (GGUF)</span>
              <input className="w2-input" name="modelPath" placeholder="models/my-model.gguf" />
            </label>
          )}
          <label className="ws-recipe-field">
            <span>Host Port</span>
            <input className="w2-input" name="hostPort" type="number" min="1024" max="65535" placeholder="Auto" />
          </label>
          <label className="ws-recipe-field">
            <span>Role</span>
            <select className="w2-input" name="role" defaultValue={selectedProtocol?.defaultRole || "helper"}>
              <option value="main">Main</option><option value="planner">Planner</option><option value="coder">Coder</option>
              <option value="researcher">Researcher</option><option value="summarizer">Summarizer</option>
              <option value="embeddings">Embeddings</option><option value="helper">Helper</option>
            </select>
          </label>
          <label className="ws-recipe-field">
            <span>Tool-call parser</span>
            <input
              className="w2-input"
              name="toolCallParser"
              data-testid="warsat-tool-call-parser"
              list="warsat-tool-call-parser-options"
              placeholder="None / model default"
              autoComplete="off"
              spellCheck="false"
            />
            <datalist id="warsat-tool-call-parser-options">
              <option value="hermes" />
              <option value="mistral" />
              <option value="llama3_json" />
              <option value="deepseek_v3" />
            </datalist>
            <small>Set only for a model-specific parser supported by the selected runtime. A wrong parser can corrupt tool calls.</small>
          </label>
          <label className="ws-recipe-field">
            <span>Profile</span>
            <select className="w2-input" name="strengthProfile" value={strengthProfile} onChange={e => setStrengthProfile(e.target.value)}>
              {Object.entries(strengthProfiles).map(([k, p]) => <option key={k} value={k}>{p.label || k}</option>)}
              {!Object.keys(strengthProfiles).length && <option value="balanced">Balanced</option>}
            </select>
          </label>
          <label className="ws-recipe-field" htmlFor="warsatMultiGpu">
            <span>GPU allocation</span>
            <span className="ws-checkbox-row">
              <input
                id="warsatMultiGpu"
                key={`${selectedProtocol?.runtime || "runtime"}-${(hardware?.detectedHardware?.gpus || []).length}`}
                name="multiGpu"
                type="checkbox"
                defaultChecked={selectedProtocol?.runtime === "vllm"
                  ? false
                  : (hardware?.detectedHardware?.gpus || []).length > 1}
              />
              Use all detected GPUs
            </span>
            <small>
              {selectedProtocol?.runtime === "vllm"
                ? "vLLM uses the largest visible GPU by default; enable this only after validating tensor-parallel compatibility."
                : `Auto-shards across ${(hardware?.detectedHardware?.gpus || []).length || "the visible"} GPUs and fits to available VRAM.`}
            </small>
          </label>
          {selectedProtocol?.modelFormat === "gguf" && (
            <details className="rounded-xl border border-border bg-muted/20 p-3" style={{ gridColumn: "1 / -1" }} data-testid="warsat-performance-tuning">
              <summary className="cursor-pointer text-sm font-semibold">Advanced measured performance tuning</summary>
              <p className="mb-3 mt-2 text-xs text-muted-foreground">
                These controls change the exact benchmark identity. Leave them at their safe defaults until Rasputin has measured the alternative on this hardware.
              </p>
              <div className="grid gap-3 md:grid-cols-2">
                <label className="ws-recipe-field">
                  <span>Context window</span>
                  <input className="w2-input" name="contextWindow" type="number" min="512" max="262144" placeholder="Profile default" />
                </label>
                <label className="ws-recipe-field">
                  <span>Split mode</span>
                  <select className="w2-input" name="splitMode" defaultValue="layer">
                    <option value="none">Single GPU</option>
                    <option value="layer">Layer split (compatible)</option>
                    <option value="tensor">Tensor split (experimental)</option>
                  </select>
                </label>
                <label className="ws-recipe-field">
                  <span>Batch size</span>
                  <input className="w2-input" name="batchSize" type="number" min="1" max="65536" defaultValue="768" />
                </label>
                <label className="ws-recipe-field">
                  <span>Microbatch size</span>
                  <input className="w2-input" name="ubatchSize" type="number" min="1" max="65536" defaultValue="256" />
                </label>
                <label className="ws-recipe-field">
                  <span>Flash attention</span>
                  <select className="w2-input" name="flashAttention" defaultValue="auto">
                    <option value="auto">Automatic</option>
                    <option value="on">On</option>
                    <option value="off">Off</option>
                  </select>
                </label>
                <label className="ws-recipe-field">
                  <span>KV cache</span>
                  <select className="w2-input" name="cacheTypeK" defaultValue="f16">
                    <option value="f16">F16 (safe)</option>
                    <option value="q8_0">Q8_0</option>
                    <option value="q4_0">Q4_0</option>
                  </select>
                  <small>Applies to both K and V cache for a comparable benchmark tuple.</small>
                </label>
                <label className="ws-recipe-field" style={{ gridColumn: "1 / -1" }}>
                  <span>Speculative decoding</span>
                  <select className="w2-input" name="speculativeMode" defaultValue="none">
                    <option value="none">Off until benchmarked</option>
                    <option value="ngram-simple">N-gram simple</option>
                    <option value="ngram-mod">N-gram shared cache</option>
                  </select>
                </label>
              </div>
            </details>
          )}
          <div className="ws-recipe-actions">
            <button className="w2-button primary" type="submit" style={{ flex: 1 }}>
              <Zap size={14} /> {plan ? "Regenerate Plan" : "Generate Plan"}
            </button>
            {(plan || error) && (
              <button className="w2-button" type="button" onClick={clearPlan}>Clear</button>
            )}
          </div>
        </form>
        {error && (
          <div className="ws-recipe-error">
            <AlertTriangle size={13} /> {error}
          </div>
        )}
      </div>

      {/* ── Mission Brief (Plan Preview) ── */}
      {plan && (
        <div ref={briefRef}>
          <PlanPreview
            plan={plan}
            deployment={deployment}
            deploying={deploying}
            deployLabel={deployLabel}
            deployDisabled={deployDisabled}
            canDeployPlan={canDeployPlan}
            deployPlan={deployPlan}
            approvalPending={approvalPending}
            approvalClosed={approvalClosed}
            approvalStatus={approvalStatus}
            currentApproval={currentApproval}
            approveApproval={approveApproval}
            denyApproval={denyApproval}
            lifecycle={lifecycle}
            enableDockerControl={enableDockerControl}
            downloadProgress={downloadProgress}
            resourceAdmission={plan?.resourceAdmission}
            resourceAdmissionStatus={plan?.resourceAdmission?.status}
            go={go}
          />
        </div>
      )}
    </div>
  );
}
