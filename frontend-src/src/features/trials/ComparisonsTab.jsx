import { useState } from "react";
import { GitCompare, Plus } from "lucide-react";
import { postJson } from "../../api/client.js";
import { fmtDate } from "./trialPresentation.jsx";

export function ComparisonsTab({ comparisons, experiments, selected, setSelected, refresh, setError }) {
  const [showCreate, setShowCreate] = useState(false);

  async function handleCreate(e) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    try {
      await postJson("/api/trials/comparisons", {
        name: form.get("name") || undefined,
        experimentIds: form.getAll("experimentIds"),
      });
      setShowCreate(false);
      await refresh();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="w2-section" style={{ flex: 1 }}>
      <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
        <h2 style={{ margin: 0, fontSize: "1rem" }}>Comparisons</h2>
        <div style={{ flex: 1 }} />
        <button className="w2-button primary" type="button" onClick={() => setShowCreate(!showCreate)}>
          <Plus size={14} /> Compare
        </button>
      </div>

      {showCreate && (
        <div className="w2-card" style={{ border: "1px solid var(--cc-accent)" }}>
          <form onSubmit={handleCreate} style={{ display: "grid", gap: "8px" }}>
            <label style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>
              Comparison Name
              <input className="w2-input" name="name" placeholder="Model A vs Model B" />
            </label>
            <fieldset style={{ border: "1px solid var(--cc-border)", borderRadius: "6px", padding: "8px" }}>
              <legend style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>Select Experiments</legend>
              {experiments.filter(e => e.status === "completed").map(e => (
                <label key={e.id} style={{ display: "flex", gap: "4px", alignItems: "center", fontSize: "0.8125rem" }}>
                  <input type="checkbox" name="experimentIds" value={e.id} />
                  {e.name}
                </label>
              ))}
            </fieldset>
            <div style={{ display: "flex", gap: "8px" }}>
              <button className="w2-button primary" type="submit"><GitCompare size={14} /> Create Comparison</button>
              <button className="w2-button" type="button" onClick={() => setShowCreate(false)}>Cancel</button>
            </div>
          </form>
        </div>
      )}

      {comparisons.map(cmp => (
        <div key={cmp.id} className="w2-card" style={{ cursor: "pointer", border: selected?.id === cmp.id ? "1px solid var(--cc-accent)" : undefined }} onClick={() => setSelected(cmp)}>
          <strong style={{ fontSize: "0.875rem" }}>{cmp.name}</strong>
          <div style={{ fontSize: "0.6875rem", color: "var(--cc-muted)" }}>{(cmp.experimentIds || []).length} experiments · {fmtDate(cmp.createdAt)}</div>
        </div>
      ))}

      {!comparisons.length && (
        <div style={{ padding: "32px", textAlign: "center", color: "var(--cc-muted)", backgroundColor: "var(--cc-surface)", borderRadius: "8px" }}>
          No comparisons yet. Complete experiments first.
        </div>
      )}
    </div>
  );
}
