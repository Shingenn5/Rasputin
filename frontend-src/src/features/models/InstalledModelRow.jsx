import { ChevronRight } from "lucide-react";
import { displayModelName } from "../../lib/display.js";
import { PublisherLogo } from "./PublisherLogo.jsx";
import { modelOperationalSignal, installedModelFormat, installedModelSize } from "./modelPresentation.js";

export function InstalledCard({ model, allModels, selected = false, chatActive = false, onSelect }) {
  const name = model.name || displayModelName(model, allModels);
  const operationalSignal = modelOperationalSignal(model);
  const size = installedModelSize(model);
  return (
    <article className={`studio-installed-row model-library-card ${selected ? "is-selected" : ""}`}
      id={`installed-model-row-${String(model.key).replace(/[^a-zA-Z0-9_-]/g, "-")}`}
      data-testid="installed-model-row" data-model-key={model.key} data-runtime-state={operationalSignal.key} role="listitem">
      <button className="model-card-select" type="button" onClick={onSelect} aria-pressed={selected} aria-label={`Details and settings for ${name}`} aria-controls="installed-model-inspector">
        <PublisherLogo item={model} size="md" />
        <span className="model-card-identity"><strong>{name}</strong><small>{installedModelFormat(model)}{size !== "—" ? ` · ${size}` : ""}{chatActive ? " · Selected for chat" : ""}</small></span>
        <span className={`model-card-status is-${operationalSignal.key}`}><span aria-hidden="true" /><strong>{operationalSignal.label}</strong></span>
        <ChevronRight size={18} aria-hidden="true" />
      </button>
    </article>
  );
}
