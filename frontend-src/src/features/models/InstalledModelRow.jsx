import { needsNativeModelDownload } from "./nativeDeployment.js";
import { useState } from "react";
import { AlertTriangle, Play, Power } from "lucide-react";
import { displayModelName, displayModelSecondary, isManagedModelRunning, modelMismatchLine } from "../../lib/display.js";
import { Button } from "../../components/Button.jsx";
import { PublisherLogo } from "./PublisherLogo.jsx";
import { modelOperationalSignal } from "./modelPresentation.js";
import { ModelStateSignal } from "./ModelStatus.jsx";

export function InstalledCard({ nativeModels = false, model, allModels, selected = false, chatActive = false, onSelect, runModelAction, executeAction, setUiState, onConfigureLoad, onOpenActions }) {
  const name = model.name || displayModelName(model, allModels);
  const secondary = displayModelSecondary(model, allModels);
  const mismatch = modelMismatchLine(model);
  const [busy, setBusy] = useState(null);
  const nativeRuntime = model.runtime === "native-llamacpp";
  const needsGguf = needsNativeModelDownload(model, nativeModels);
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
  const handleRuntime = () => (nativeRuntime || needsGguf) && !isRunning
    ? onConfigureLoad?.(model)
    : runAction(isRunning ? "stop" : "start", isRunning ? "StopModel" : "StartModel", isRunning ? "stop" : "start");

  return (
    <div
      id={`installed-model-row-${String(model.key).replace(/[^a-zA-Z0-9_-]/g, "-")}`}
      className={`studio-installed-row models-inventory-row ${selected ? "is-selected" : ""} ${chatActive ? "is-chat-active" : ""}`}
      data-testid="installed-model-row"
      data-model-key={model.key}
      data-runtime-state={operationalSignal.key}
      role="row"
      aria-selected={selected}
      aria-current={chatActive ? "true" : undefined}
      aria-controls="installed-model-inspector"
      tabIndex={selected ? 0 : -1}
      onClick={onSelect}
      onKeyDown={(event) => {
        if (event.target === event.currentTarget && (event.key === "Enter" || event.key === " ")) {
          event.preventDefault();
          onSelect?.();
        }
      }}
    >
      <span className="studio-installed-model" role="cell">
        <PublisherLogo item={model} size="md" />
        <span>
          <strong>{name}</strong>
          <small>{secondary || model.model || model.key}</small>
        </span>
      </span>
      <ModelStateSignal signal={operationalSignal} chatActive={chatActive} role="cell" />
      <span className="studio-installed-actions" role="cell">
        {model.managed && (
          <Button
            onClick={(event) => { event?.stopPropagation?.(); handleRuntime(); }}
            loading={busy === "start" || busy === "stop"}
            loadingLabel={isRunning ? "Stopping…" : "Starting…"}
            icon={isRunning ? <Power size={12} /> : <Play size={12} />}
            spinnerSize={12}
          >
            {isRunning ? "Stop" : needsGguf ? "Get GGUF" : nativeRuntime ? "Load" : "Start"}
          </Button>
        )}
        <button
          type="button"
          className="models-row-actions-trigger"
          aria-label={`Open actions for ${name}`}
          onClick={(event) => {
            event.stopPropagation();
            onOpenActions?.();
          }}
        >
          •••
        </button>
      </span>
      {mismatch && <span className="sr-only"><AlertTriangle size={11} /> {mismatch}</span>}
    </div>
  );
}
