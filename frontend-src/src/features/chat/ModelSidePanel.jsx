import { useState } from "react";
import { Search } from "lucide-react";

import { displayModelName, displayModelSecondary, runtimeStatus } from "../../lib/display.js";

import { Modal } from "../../components/Modal.jsx";

export function ModelSidePanel({ panelRef, models, visibleModels, selectedModel, setSelectedModel, close, onOpenModels, returnFocusRef }) {
  const [query, setQuery] = useState("");
  const items = visibleModels.filter((model) => {
    const text = [displayModelName(model, models), displayModelSecondary(model, models), model.key, model.model].join(" ").toLowerCase();
    return text.includes(query.trim().toLowerCase());
  });
  return (
    <Modal open onClose={close} title="Select a model to load" size="lg" className="studio-model-picker" returnFocusRef={returnFocusRef}>
      <div ref={panelRef} data-testid="model-side-panel">
        <label className="studio-model-picker-search">
          <Search size={16} aria-hidden="true" />
          <input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Filter local models..." autoFocus />
        </label>
        <div className="studio-model-picker-head"><strong>Your models</strong><span>Available</span></div>
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
