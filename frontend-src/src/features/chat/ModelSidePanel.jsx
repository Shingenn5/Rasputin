import { useId, useRef, useState } from "react";
import { Check, Search, X } from "lucide-react";

import { displayModelName, displayModelSecondary, runtimeStatus } from "../../lib/display.js";

import { Modal } from "../../components/Modal.jsx";

export function ModelSidePanel({ panelRef, models, visibleModels, selectedModel, setSelectedModel, close, onOpenModels, returnFocusRef }) {
  const [query, setQuery] = useState("");
  const filterId = useId();
  const searchRef = useRef(null);
  const items = visibleModels.filter((model) => {
    const text = [displayModelName(model, models), displayModelSecondary(model, models), model.key, model.model].join(" ").toLowerCase();
    return text.includes(query.trim().toLowerCase());
  });
  return (
    <Modal open onClose={close} title="Select a model to load" size="lg" className="studio-model-picker ras-studio-overlay" initialFocusRef={searchRef} returnFocusRef={returnFocusRef}>
      <div ref={panelRef} data-testid="model-side-panel">
        <div className="studio-model-picker-search">
          <label htmlFor={filterId} className="sr-only">Filter available models</label>
          <Search size={16} aria-hidden="true" />
          <input ref={searchRef} id={filterId} type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search by model, provider, or role..." />
          {query && <button type="button" className="studio-model-filter-clear" aria-label="Clear model filter" onClick={() => { setQuery(""); searchRef.current?.focus(); }}><X size={15} aria-hidden="true" /></button>}
        </div>
        <div className="studio-model-picker-head"><strong>Your models</strong><span role="status">{items.length} available{query ? ` of ${visibleModels.length}` : ""}</span></div>
        <div className="studio-model-picker-list">
          {!items.length && (
            <p className="model-panel-empty" role="status">
              No available chat model matches this filter.
            </p>
          )}
          {items.map((model) => {
            const selected = model.key === selectedModel;
            const status = runtimeStatus(model);
            const context = model.context_window || model.contextWindow;
            return (
              <button
                key={model.key}
                type="button"
                className={selected ? "model-choice is-active" : "model-choice"}
                data-testid="model-option"
                aria-pressed={selected}
                onClick={() => setSelectedModel(model.key)}
              >
                <span className={"model-choice-status status-" + status} aria-hidden="true" />
                <span>
                  <strong>{displayModelName(model, models)}</strong>
                  <small>{displayModelSecondary(model, models) || model.model || model.key}</small>
                </span>
                <em>{context ? Number(context).toLocaleString() + " ctx" : status}</em>
                <Check size={17} className="model-choice-check" aria-hidden="true" />
              </button>
            );
          })}
        </div>
        <footer className="studio-model-picker-footer">
          <span>Only healthy chat-capable models are selectable here.</span>
          <button type="button" className="w2-button" onClick={() => { close(); onOpenModels?.(); }}>Manage models</button>
        </footer>
      </div>
    </Modal>
  );
}
