import { needsNativeModelDownload } from "./nativeDeployment.js";
import { useState, useEffect } from "react";
import { Copy, Cpu, Download, Gauge, HardDrive, Link2, Play, Pin, PinOff, Power, SlidersHorizontal, Trash2 } from "lucide-react";
import {
  displayModelName,
  isModelHealthy,
  isManagedModelRunning,
  labelize,
  modelMismatchLine,
  runtimeStatus,
} from "../../lib/display.js";

import { Button } from "../../components/Button.jsx";

import { PublisherLogo } from "./PublisherLogo.jsx";


import { contextWindowFor, installedModelArchitecture, installedModelCategory, installedModelFile, installedModelFormat, installedModelParameters, installedModelPath, installedModelPublisher, installedModelQuantization, installedModelSize, modelOperationalSignal } from "./modelPresentation.js";

import { ModelStateSignal } from "./ModelStatus.jsx";
import { ModelRecovery } from "./ModelRecovery.jsx";

export function InstalledModelInspector({ nativeModels = false, model, allModels, chatActive = false, onUseInChat, runModelAction, executeAction, setUiState, onConfigureLoad, onSaved, onFindModels, activeTab, onTabChange }) {
  const [busy, setBusy] = useState("");
  const [deleteArmed, setDeleteArmed] = useState(false);
  const [pinned, setPinned] = useState(false);
  const [inference, setInference] = useState({
    systemPrompt: "",
    temperature: 0.8,
    limitResponse: false,
    maxTokens: 2048,
    stopStrings: "",
  });

  useEffect(() => {
    setDeleteArmed(false);
    if (!model?.key || typeof window === "undefined") return;
    try {
      const pins = JSON.parse(window.localStorage.getItem("rasputin-pinned-models") || "[]");
      setPinned(Array.isArray(pins) && pins.includes(model.key));
      const saved = model.inferenceProfile || model.inference_profile || {};
      setInference({
        systemPrompt: saved.systemPrompt ?? saved.system_prompt ?? "",
        temperature: saved.temperature ?? 0.8,
        limitResponse: Boolean(saved.maxTokens ?? saved.max_tokens),
        maxTokens: saved.maxTokens ?? saved.max_tokens ?? 2048,
        stopStrings: (saved.stopStrings || saved.stop_strings || []).join(", "),
      });
    } catch {
      setPinned(false);
    }
  }, [model?.key]);

  if (!model) {
    return (
      <aside id="installed-model-inspector" className="models-model-inspector is-empty" data-testid="installed-model-inspector">
        <Cpu size={24} aria-hidden="true" />
        <strong>Model details</strong>
        <p>Select a model to see its status, settings, and source file.</p>
      </aside>
    );
  }

  const name = model.name || displayModelName(model, allModels);
  const developer = installedModelPublisher(model);
  const st = runtimeStatus(model);
  const healthy = modelOperationalSignal(model).key === "live";
  const nativeRuntime = model.runtime === "native-llamacpp";
  const needsGguf = needsNativeModelDownload(model, nativeModels);
  const isRunning = isManagedModelRunning(model);
  const operationalSignal = modelOperationalSignal(model);
  const path = installedModelPath(model);
  const context = contextWindowFor(model);
  const mismatch = modelMismatchLine(model);
  const modelId = String(model.model || model.key);
  const sourceUrl = model.sourceUrl || model.source_url || (modelId.includes("/") ? `https://huggingface.co/${modelId}` : "");
  const capabilities = Array.isArray(model.capabilities) && model.capabilities.length ? model.capabilities : ["Text"];
  const tabs = ["info", "load", "inference", "actions"];

  const updateInference = (patch) => {
    setInference((current) => ({ ...current, ...patch }));
  };

  const saveInference = async () => {
    setBusy("inference");
    try {
      await runModelAction?.("inference-profile", model.key, {
        temperature: Number(inference.temperature),
        systemPrompt: inference.systemPrompt,
        maxTokens: inference.limitResponse ? Number(inference.maxTokens) : null,
        stopStrings: inference.stopStrings.split(",").map((value) => value.trim()).filter(Boolean),
      });
      setUiState({ status: "success", message: "Inference settings saved. New model requests use this profile." });
    } catch (error) {
      setUiState({ status: "failed", message: error.message });
    } finally { setBusy(""); }
  };

  const handleLoad = async () => {
    if (isRunning) return;
    if (nativeRuntime || needsGguf) {
      onConfigureLoad?.(model);
      return;
    }
    setBusy("load");
    try {
      await executeAction("StartModel", model.key, async () => runModelAction?.("start", model.key), setUiState);
    } finally {
      setBusy("");
    }
  };

  const handleStop = async () => {
    setBusy("stop");
    try {
      await executeAction("StopModel", model.key, async () => runModelAction?.("stop", model.key), setUiState);
    } finally {
      setBusy("");
    }
  };

  const copyValue = async (value, label) => {
    try {
      await navigator.clipboard.writeText(value);
      setUiState({ status: "success", message: `${label} copied.` });
    } catch {
      setUiState({ status: "failed", message: `Unable to copy ${label.toLowerCase()}.` });
    }
  };

  const togglePinned = () => {
    try {
      const stored = JSON.parse(window.localStorage.getItem("rasputin-pinned-models") || "[]");
      const pins = new Set(Array.isArray(stored) ? stored : []);
      if (pins.has(model.key)) pins.delete(model.key);
      else pins.add(model.key);
      window.localStorage.setItem("rasputin-pinned-models", JSON.stringify([...pins]));
      setPinned(pins.has(model.key));
      setUiState({ status: "success", message: pins.has(model.key) ? "Model pinned." : "Model unpinned." });
    } catch {
      setUiState({ status: "failed", message: "Unable to update pinned models." });
    }
  };

  const handleDelete = async () => {
    setBusy("delete");
    try {
      await executeAction("DeleteModel", model.key, async () => runModelAction?.("delete", model.key), setUiState);
      setDeleteArmed(false);
    } finally {
      setBusy("");
    }
  };

  const infoFacts = [
    ["Developer", developer],
    ["Family", model.family || model.model_family || installedModelArchitecture(model)],
    ["Architecture", installedModelArchitecture(model)],
    ["Parameters", installedModelParameters(model)],
    ["Format", installedModelFormat(model)],
    ["Quantization", installedModelQuantization(model)],
    ["Context", context > 0 ? context.toLocaleString() + " tokens" : "Runtime default"],
    ["Modalities", capabilities.map(labelize).join(", ")],
    ["Purpose", labelize(model.purpose || model.role || "chat")],
    ["License", model.license || "Not declared"],
    ["Downloads", Number(model.downloads || 0).toLocaleString()],
    ["Size on disk", installedModelSize(model)],
    ["Hardware fit", mismatch || (healthy ? "Ready on this workstation" : "Check runtime")],
  ];

  return (
    <aside id="installed-model-inspector" className="models-model-inspector" data-testid="installed-model-inspector" aria-label={`${name} model inspector`}>
      <header className="models-inspector-header">
        <div className="models-inspector-title">
          <PublisherLogo item={model} size="lg" />
          <div><strong>{name}</strong><small>{developer}</small></div>
        </div>
        <ModelStateSignal signal={operationalSignal} chatActive={chatActive} compact />
        <div className="models-inspector-primary-actions">
          <button type="button" className="w2-button" disabled={!healthy || model.enabled === false} onClick={() => onUseInChat?.(model)}><Play size={13} /> Use in New Chat</button>
          {model.managed && (
            isRunning
              ? <Button onClick={handleStop} loading={busy === "stop"} loadingLabel="Stopping…" icon={<Power size={13} />}>Stop Model</Button>
              : <Button disabled={operationalSignal.action === "file" || operationalSignal.action === "wait"} onClick={handleLoad} loading={busy === "load"} loadingLabel="Loading…" icon={<Download size={13} />}>{needsGguf ? "Get GGUF" : "Load Model"}</Button>
          )}
        </div>
      </header>

      <div className="models-inspector-tabs" role="tablist" aria-label="Model inspector sections">
        {tabs.map((tab) => (
          <button
            key={tab}
            id={`model-inspector-tab-${tab}`}
            type="button"
            role="tab"
            aria-selected={activeTab === tab}
            aria-controls={`model-inspector-panel-${tab}`}
            tabIndex={activeTab === tab ? 0 : -1}
            onClick={() => onTabChange?.(tab)}
            onKeyDown={(event) => {
              let next = tabs.indexOf(tab);
              if (event.key === "ArrowRight") next = (next + 1) % tabs.length;
              else if (event.key === "ArrowLeft") next = (next - 1 + tabs.length) % tabs.length;
              else if (event.key === "Home") next = 0;
              else if (event.key === "End") next = tabs.length - 1;
              else return;
              event.preventDefault();
              onTabChange?.(tabs[next]);
              requestAnimationFrame(() => document.getElementById(`model-inspector-tab-${tabs[next]}`)?.focus());
            }}
          >
            {{ info: "Overview", load: "Load settings", inference: "Response", actions: "More" }[tab]}
          </button>
        ))}
      </div>

      {activeTab === "info" && (
        <section id="model-inspector-panel-info" role="tabpanel" aria-labelledby="model-inspector-tab-info" className="models-inspector-section">
          <dl className="model-inspector-essentials">
            <div><dt>Format</dt><dd>{installedModelFormat(model)}</dd></div>
            <div><dt>Size</dt><dd>{installedModelSize(model)}</dd></div>
            <div><dt>Context</dt><dd>{context > 0 ? context.toLocaleString() + " tokens" : "Runtime default"}</dd></div>
          </dl>
          <ModelRecovery key={model.key} model={model} signal={operationalSignal} onConfigureLoad={onConfigureLoad} onSaved={onSaved} onFindModels={onFindModels} />
          {(model.summary || model.description) && <p className="models-inspector-summary">{model.summary || model.description}</p>}
          <details className="models-inspector-disclosure models-inspector-technical">
            <summary><SlidersHorizontal size={14} /> Technical Details</summary>
            <dl className="models-inspector-facts">
              {infoFacts.map(([label, value]) => <div key={label}><dt>{label}</dt><dd title={String(value)}>{value}</dd></div>)}
            </dl>
          </details>
        </section>
      )}

      {activeTab === "load" && (
        <section id="model-inspector-panel-load" role="tabpanel" aria-labelledby="model-inspector-tab-load" className="models-inspector-section">
          <h3>Load Profile</h3>
          <div className="models-inspector-callout"><Gauge size={16} /><span><strong>Automatic placement</strong><small>Rasputin selects a fitting GPU and preserves combined VRAM when this model needs it.</small></span></div>
          <dl className="models-inspector-facts">
            {[
              ["Runtime", model.runtime || model.provider || "Local"],
              ["Device", nativeRuntime ? "Automatic GPU placement" : "Managed endpoint"],
              ["State", labelize(st)],
              ["Compatibility", mismatch || (healthy ? "Ready" : "Needs health check")],
              ["Source file", installedModelFile(model)],
            ].map(([label, value]) => <div key={label}><dt>{label}</dt><dd title={String(value)}>{value}</dd></div>)}
          </dl>
          {model.managed && <button type="button" className="models-inspector-wide-action" onClick={() => onConfigureLoad?.(model)}><SlidersHorizontal size={14} /> Configure advanced load settings</button>}
        </section>
      )}

      {activeTab === "inference" && (
        <section id="model-inspector-panel-inference" role="tabpanel" aria-labelledby="model-inspector-tab-inference" className="models-inspector-section models-inference-panel">
          <div className="models-inference-heading"><h3>System Prompt</h3><span>{inference.systemPrompt.length.toLocaleString()} characters</span></div>
          <textarea aria-label="System prompt" value={inference.systemPrompt} onChange={(event) => updateInference({ systemPrompt: event.target.value })} placeholder={'Example, "Only answer in rhymes"'} />
          <div className="models-inference-group">
            <h3>Generation Settings</h3>
            <label className="models-control-stack"><span>Temperature <output>{Number(inference.temperature).toFixed(1)}</output></span><input aria-label="Temperature" type="range" min="0" max="2" step="0.1" value={inference.temperature} onChange={(event) => updateInference({ temperature: Number(event.target.value) })} /></label>
            <label className="models-control-row"><span>Limit response length</span><input type="checkbox" checked={inference.limitResponse} onChange={(event) => updateInference({ limitResponse: event.target.checked })} /></label>
            {inference.limitResponse && <label className="models-control-row"><span>Maximum tokens</span><input className="models-compact-input" type="number" min="64" step="64" value={inference.maxTokens} onChange={(event) => updateInference({ maxTokens: Number(event.target.value) })} /></label>}
            <label className="models-control-stack"><span>Stop strings</span><input type="text" value={inference.stopStrings} onChange={(event) => updateInference({ stopStrings: event.target.value })} placeholder="Enter strings separated by commas" /></label>
          </div>
          <Button onClick={saveInference} loading={busy === "inference"} loadingLabel="Saving…">Save inference settings</Button>
          <p className="models-inference-note">Saved for new requests to this local model. Response limits stay within Rasputin's context budget. Reasoning is controlled in Chat; GPU, context, and CPU threads are configured in Load Model.</p>
        </section>
      )}

      {activeTab === "actions" && (
        <section id="model-inspector-panel-actions" role="tabpanel" aria-labelledby="model-inspector-tab-actions" className="models-inspector-section models-actions-panel">
          <h3>Model Actions</h3>
          <button type="button" onClick={togglePinned}>{pinned ? <PinOff size={15} /> : <Pin size={15} />}<span><strong>{pinned ? "Unpin model" : "Pin model"}</strong><small>{pinned ? "Remove it from your priority models." : "Keep it at the top of your model workflow."}</small></span></button>
          <button type="button" onClick={() => copyValue(modelId, "Model ID")}><Copy size={15} /><span><strong>Copy model ID</strong><small>{modelId}</small></span></button>
          {path && <button type="button" onClick={() => copyValue(path, "Model path")}><HardDrive size={15} /><span><strong>Copy absolute path</strong><small>{path}</small></span></button>}
          {sourceUrl && <a href={sourceUrl} target="_blank" rel="noopener noreferrer"><Link2 size={15} /><span><strong>Show on web</strong><small>Open the developer source page.</small></span></a>}
          {!deleteArmed ? (
            <button type="button" className="is-danger" onClick={() => setDeleteArmed(true)}><Trash2 size={15} /><span><strong>Delete model</strong><small>Remove this model from Rasputin.</small></span></button>
          ) : (
            <div className="models-delete-confirm" role="alert">
              <p>Delete {name}? This removes its registry entry and may stop a running model.</p>
              <button type="button" onClick={() => setDeleteArmed(false)}>Cancel</button>
              <Button onClick={handleDelete} loading={busy === "delete"} loadingLabel="Deleting…">Confirm Delete</Button>
            </div>
          )}
        </section>
      )}

      <div className="models-inspector-spacer" />
      <details className="models-inspector-disclosure">
        <summary><SlidersHorizontal size={14} /> Model purpose</summary>
        <div><span>Purpose</span><strong>{labelize(installedModelCategory(model))}</strong></div>
        <div><span>Compatibility</span><strong>{mismatch || "No mismatch detected"}</strong></div>
      </details>
      <details className="models-inspector-disclosure">
        <summary><HardDrive size={14} /> Source File</summary>
        <div><span>Path</span><strong title={path || "No local source path"}>{path || "Managed endpoint — no local file"}</strong></div>
        <div><span>Override</span><strong>{nativeRuntime ? "Available in Load Model" : "Managed externally"}</strong></div>
      </details>
    </aside>
  );
}
