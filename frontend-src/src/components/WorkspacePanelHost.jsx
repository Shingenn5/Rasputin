import React, { useEffect, useMemo, useRef } from "react";
import { Minus, PanelRightClose, RotateCcw, X } from "lucide-react";

export function WorkspacePanelHost({
  panels,
  activePanelId,
  minimizedPanelIds,
  closePanel,
  minimizePanel,
  restorePanel,
  returnFocus,
}) {
  const panelRef = useRef(null);
  const activePanel = useMemo(
    () => panels.find((panel) => panel.id === activePanelId) || null,
    [panels, activePanelId],
  );
  const minimizedPanels = useMemo(
    () => panels.filter((panel) => minimizedPanelIds.includes(panel.id)),
    [panels, minimizedPanelIds],
  );

  useEffect(() => {
    if (!activePanel || !panelRef.current) return undefined;
    const firstControl = panelRef.current.querySelector("button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])");
    firstControl?.focus?.();
    return undefined;
  }, [activePanel?.id]);

  useEffect(() => {
    if (!activePanel) return undefined;
    function handleKeydown(event) {
      if (event.key === "Escape") {
        closePanel(activePanel.id);
        returnFocus?.();
      }
    }
    window.addEventListener("keydown", handleKeydown);
    return () => window.removeEventListener("keydown", handleKeydown);
  }, [activePanel, closePanel, returnFocus]);

  if (!activePanel && !minimizedPanels.length) return null;

  return (
    <>
      {activePanel && (
        <aside
          ref={panelRef}
          className="workspace-panel-host"
          data-testid="workspace-panel-host"
          role="dialog"
          aria-modal="false"
          aria-labelledby={`workspace-panel-title-${activePanel.id}`}
        >
          <header className="workspace-panel-head">
            <div>
              <span className="eyebrow">{activePanel.kicker || "Focused panel"}</span>
              <h2 id={`workspace-panel-title-${activePanel.id}`}>{activePanel.title}</h2>
              {activePanel.subtitle && <p>{activePanel.subtitle}</p>}
            </div>
            <div className="workspace-panel-actions" aria-label={`${activePanel.title} panel controls`}>
              <button
                type="button"
                className="icon-button"
                aria-label={`Minimize ${activePanel.title} panel`}
                onClick={() => minimizePanel(activePanel.id)}
              >
                <Minus size={17} />
              </button>
              <button
                type="button"
                className="icon-button"
                aria-label={`Close ${activePanel.title} panel`}
                onClick={() => {
                  closePanel(activePanel.id);
                  returnFocus?.();
                }}
              >
                <X size={17} />
              </button>
            </div>
          </header>
          <div className="workspace-panel-body">{activePanel.content}</div>
        </aside>
      )}

      {minimizedPanels.length > 0 && (
        <nav className="workspace-panel-dock" aria-label="Minimized panels" data-testid="workspace-panel-dock">
          {minimizedPanels.map((panel) => (
            <button
              type="button"
              className="workspace-panel-dock-chip"
              key={panel.id}
              onClick={() => restorePanel(panel.id)}
              aria-label={`Restore ${panel.title} panel`}
            >
              <RotateCcw size={14} />
              <span>{panel.title}</span>
            </button>
          ))}
          <button
            type="button"
            className="workspace-panel-dock-close"
            onClick={() => minimizedPanels.forEach((panel) => closePanel(panel.id))}
            aria-label="Close all minimized panels"
          >
            <PanelRightClose size={15} />
          </button>
        </nav>
      )}
    </>
  );
}
