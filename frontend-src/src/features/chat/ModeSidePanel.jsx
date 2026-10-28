import { Bot, X } from "lucide-react";

import { displayModelName, displayModelSecondary, labelize } from "../../lib/display.js";

export function ModeSidePanel({
  panelRef,
  modes,
  activeMode,
  models,
  visibleModels,
  modeModelOverrides,
  setModeModelOverride,
  modelKeyForMode,
  setTaskMode,
  subagentCount,
  setSubagentCount,
  close,
}) {
  function modelForMode(mode) {
    const key = modelKeyForMode?.(mode.value, modeModelOverrides);
    return visibleModels.find((model) => model.key === key)
      || visibleModels.find((model) => model.role === mode.role)
      || null;
  }

  return (
    <aside
      ref={panelRef}
      className="mode-side-panel"
      data-testid="mode-side-panel"
      role="dialog"
      aria-modal="false"
      aria-labelledby="modePanelTitle"
    >
      <header className="mode-panel-head">
        <div>
          <h2 id="modePanelTitle">Choose mode</h2>
        </div>
        <button className="icon-button" type="button" aria-label="Close mode panel" onClick={close}>
          <X size={18} />
        </button>
      </header>

      <div className="mode-panel-list">
        {modes.map((mode) => {
          const routed = modelForMode(mode);
          const override = modeModelOverrides?.[mode.value] || "";
          return (
            <article className={activeMode === mode.value ? "mode-card is-active" : "mode-card"} key={mode.value} data-testid="mode-option">
              <button type="button" className="mode-card-main" aria-pressed={activeMode === mode.value} onClick={() => setTaskMode(mode.value)}>
                <Bot size={18} aria-hidden="true" />
                <span>
                  <strong>{mode.label}</strong>
                  <small>{mode.description}</small>
                </span>
              </button>
              <dl className="mode-route-grid">
                <dt>Role</dt>
                <dd>{labelize(mode.role)}</dd>
                <dt>Model</dt>
                <dd>{routed ? displayModelName(routed, models) : "No available model"}</dd>
                {routed && displayModelSecondary(routed, models) && (
                  <>
                    <dt>Registry</dt>
                    <dd>{displayModelSecondary(routed, models)}</dd>
                  </>
                )}
              </dl>
              <label className="mode-model-override">
                <span>Override model</span>
                <select
                  value={override}
                  aria-label={`${mode.label} model override`}
                  onChange={(event) => setModeModelOverride(mode.value, event.target.value)}
                >
                  <option value="">Use {labelize(mode.role)} route</option>
                  {visibleModels.map((model) => (
                    <option key={model.key} value={model.key}>{displayModelName(model, models)}</option>
                  ))}
                </select>
              </label>
              <p>{mode.permission}</p>
            </article>
          );
        })}
      </div>

      <section className="mode-subagent-panel" aria-label="Parallel sub-agent controls">
        <div>
          <h3>Parallel sub-agents</h3>
          <p>Use these for larger non-chat jobs. Normal chat messages can already run at the same time.</p>
        </div>
        <label>
          <span>Count</span>
          <input
            type="number"
            min="0"
            max="4"
            value={subagentCount}
            onChange={(event) => setSubagentCount(Math.max(0, Math.min(Number(event.target.value || 0), 4)))}
          />
        </label>
      </section>
    </aside>
  );
}
