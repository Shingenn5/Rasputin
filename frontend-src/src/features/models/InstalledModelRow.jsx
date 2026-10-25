import { useState } from "react";
import { Play, Power, ChevronRight } from "lucide-react";
import { displayModelName, isManagedModelRunning, isModelHealthy } from "../../lib/display.js";
import { Button } from "../../components/Button.jsx";
import { PublisherLogo } from "./PublisherLogo.jsx";
import { modelOperationalSignal, installedModelFormat, installedModelSize } from "./modelPresentation.js";

export function InstalledCard({ nativeModels = false, model, allModels, selected = false, chatActive = false, onSelect, runModelAction, executeAction, setUiState, onConfigureLoad, onOpenActions, onUseInChat }) {
  const name = model.name || displayModelName(model, allModels);
  const [busy, setBusy] = useState(null);
  const nativeRuntime = model.runtime === "native-llamacpp";
  const isRunning = isManagedModelRunning(model);
  const operationalSignal = modelOperationalSignal(model);

  const runAction = async (key, actionName, op) => {
    setBusy(key);
    try {
      await executeAction(actionName, model.key, async () => runModelAction?.(op, model.key), setUiState);
    } finally {
      setBusy(null);
    }
  };
  const ready = operationalSignal.key === "live";
  const primary = ready ? "Use in chat" : operationalSignal.action === "load" ? "Load model" : operationalSignal.action === "configure" ? "Fix load settings" : operationalSignal.action === "file" ? "Find file" : operationalSignal.action === "download" ? "Get GGUF" : "Fix connection";
  return (
    <article className={`studio-installed-row model-library-card ${selected ? "is-selected" : ""}`}
      id={`installed-model-row-${String(model.key).replace(/[^a-zA-Z0-9_-]/g, "-")}`}
      data-testid="installed-model-row" data-model-key={model.key} data-runtime-state={operationalSignal.key} role="listitem">
      <button className="model-card-select" type="button" onClick={onSelect} aria-pressed={selected} aria-controls="installed-model-inspector">
        <PublisherLogo item={model} size="md" />
        <span><strong>{name}</strong><small>{nativeRuntime ? "Downloaded on this PC" : model.managed ? "Requires a GGUF version" : "Connected model server"} · {installedModelFormat(model)}{nativeRuntime && installedModelSize(model) !== "—" ? ` · ${installedModelSize(model)}` : ""}</small></span>
        <ChevronRight size={18} aria-hidden="true" />
      </button>
      <div className={`model-card-status is-${operationalSignal.key}`}><span aria-hidden="true" /><strong>{operationalSignal.label}</strong>{chatActive && <small>Selected for chat</small>}</div>
      <p className="model-card-reason">{operationalSignal.detail}</p>
      <div className="model-card-actions">
        <Button primary disabled={operationalSignal.action === "wait" || operationalSignal.action === "check" && isRunning && !ready} onClick={() => {
          if (ready) onUseInChat?.(model);
          else if (["load", "configure", "download"].includes(operationalSignal.action)) onConfigureLoad?.(model);
          else onSelect?.();
        }} icon={ready || operationalSignal.action === "load" ? <Play size={14} /> : undefined}>{operationalSignal.action === "wait" ? "Loading…" : primary}</Button>
        {isRunning && <Button onClick={() => runAction("stop", "StopModel", "stop")} loading={busy === "stop"} loadingLabel="Stopping…" icon={<Power size={14} />}>Stop</Button>}
        <button type="button" className="model-card-details" onClick={onSelect}>Details & settings</button>
      </div>
    </article>
  );
}
