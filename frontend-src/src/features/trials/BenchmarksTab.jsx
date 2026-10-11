import { useState } from "react";
import { Plus } from "lucide-react";
import { postJson } from "../../api/client.js";
import { fmtDate, statusColor } from "./trialPresentation.jsx";

export function BenchmarksTab({ benchmarks, experiments, selected, setSelected, refresh, setError }) {
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);

  async function handleCreate(e) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const expIds = form.getAll("experimentIds");
    setCreating(true);
    try {
      await postJson("/api/trials/benchmarks", { name: form.get("name"), experimentIds: expIds });
      setShowCreate(false);
      await refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="w2-section" style={{ flex: 1 }}>
      <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
        <h2 style={{ margin: 0, fontSize: "1rem" }}>Benchmarks</h2>
        <div style={{ flex: 1 }} />
        <button className="w2-button primary" type="button" onClick={() => setShowCreate(!showCreate)}>
          <Plus size={14} /> New Benchmark
        </button>
      </div>

      {showCreate && (
        <div className="w2-card" style={{ border: "1px solid var(--cc-accent)" }}>
          <form onSubmit={handleCreate} style={{ display: "grid", gap: "8px" }}>
            <label style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>
              Benchmark Name
              <input className="w2-input" name="name" required placeholder="Model speed comparison" />
            </label>
            <fieldset style={{ border: "1px solid var(--cc-border)", borderRadius: "6px", padding: "8px" }}>
              <legend style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>Include Experiments</legend>
              {experiments.filter(e => e.status === "completed").map(e => (
                <label key={e.id} style={{ display: "flex", gap: "4px", alignItems: "center", fontSize: "0.8125rem" }}>
                  <input type="checkbox" name="experimentIds" value={e.id} />
                  {e.name}
                </label>
              ))}
              {!experiments.filter(e => e.status === "completed").length && <span style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>Complete experiments first</span>}
            </fieldset>
            <div style={{ display: "flex", gap: "8px" }}>
              <button className="w2-button primary" type="submit" disabled={creating}>{creating ? "Creating..." : "Create Benchmark"}</button>
              <button className="w2-button" type="button" onClick={() => setShowCreate(false)}>Cancel</button>
            </div>
          </form>
        </div>
      )}

      {benchmarks.map(bm => (
        <div key={bm.id} className="w2-card" style={{ cursor: "pointer", border: selected?.id === bm.id ? "1px solid var(--cc-accent)" : undefined }} onClick={() => setSelected(bm)}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <strong style={{ fontSize: "0.875rem" }}>{bm.name}</strong>
              <div style={{ fontSize: "0.6875rem", color: "var(--cc-muted)" }}>{(bm.experimentIds || []).length} experiments · {fmtDate(bm.createdAt)}</div>
            </div>
            <span style={{ fontSize: "0.6875rem", padding: "2px 10px", borderRadius: "999px", background: `color-mix(in srgb, ${statusColor(bm.status)} 15%, var(--cc-surface))`, color: statusColor(bm.status), fontWeight: 600 }}>{bm.status}</span>
          </div>
        </div>
      ))}

      {!benchmarks.length && (
        <div style={{ padding: "32px", textAlign: "center", color: "var(--cc-muted)", backgroundColor: "var(--cc-surface)", borderRadius: "8px" }}>
          No benchmarks yet. Complete experiments first, then create benchmarks.
        </div>
      )}
    </div>
  );
}
