import { useState } from "react";
import { FileText, Plus } from "lucide-react";
import { postJson } from "../../api/client.js";
import { fmtDate } from "./trialPresentation.jsx";

export function ReportsTab({ reports, experiments, selected, setSelected, refresh, setError }) {
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);

  async function handleCreate(e) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    setCreating(true);
    try {
      await postJson("/api/trials/reports", {
        name: form.get("name"),
        type: form.get("type"),
        experimentIds: form.getAll("experimentIds"),
      });
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
        <h2 style={{ margin: 0, fontSize: "1rem" }}>Reports</h2>
        <div style={{ flex: 1 }} />
        <button className="w2-button primary" type="button" onClick={() => setShowCreate(!showCreate)}>
          <Plus size={14} /> Generate Report
        </button>
      </div>

      {showCreate && (
        <div className="w2-card" style={{ border: "1px solid var(--cc-accent)" }}>
          <form onSubmit={handleCreate} style={{ display: "grid", gap: "8px" }}>
            <label style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>
              Report Name
              <input className="w2-input" name="name" required placeholder="Monthly benchmark report" />
            </label>
            <label style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>
              Report Type
              <select className="w2-input" name="type" defaultValue="experiment">
                <option value="experiment">Experiment Report</option>
                <option value="benchmark">Benchmark Report</option>
                <option value="comparison">Comparison Report</option>
                <option value="evaluation">Evaluation Report</option>
              </select>
            </label>
            <fieldset style={{ border: "1px solid var(--cc-border)", borderRadius: "6px", padding: "8px" }}>
              <legend style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>Include Experiments</legend>
              {experiments.filter(e => e.status === "completed").map(e => (
                <label key={e.id} style={{ display: "flex", gap: "4px", alignItems: "center", fontSize: "0.8125rem" }}>
                  <input type="checkbox" name="experimentIds" value={e.id} />
                  {e.name}
                </label>
              ))}
            </fieldset>
            <div style={{ display: "flex", gap: "8px" }}>
              <button className="w2-button primary" type="submit" disabled={creating}>{creating ? "Generating..." : "Generate Report"}</button>
              <button className="w2-button" type="button" onClick={() => setShowCreate(false)}>Cancel</button>
            </div>
          </form>
        </div>
      )}

      {reports.map(rpt => (
        <div key={rpt.id} className="w2-card" style={{ cursor: "pointer", border: selected?.id === rpt.id ? "1px solid var(--cc-accent)" : undefined }} onClick={() => setSelected(rpt)}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <strong style={{ fontSize: "0.875rem" }}>{rpt.name}</strong>
              <div style={{ fontSize: "0.6875rem", color: "var(--cc-muted)" }}>{rpt.type} · {fmtDate(rpt.createdAt)}</div>
            </div>
            <FileText size={16} color="var(--cc-muted)" />
          </div>
        </div>
      ))}

      {!reports.length && (
        <div style={{ padding: "32px", textAlign: "center", color: "var(--cc-muted)", backgroundColor: "var(--cc-surface)", borderRadius: "8px" }}>
          No reports yet. Complete experiments to generate reports.
        </div>
      )}
    </div>
  );
}
