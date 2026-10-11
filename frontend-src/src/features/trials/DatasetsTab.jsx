import { useState } from "react";
import { Database, Plus, Sparkles, Trash2 } from "lucide-react";
import { api, postJson } from "../../api/client.js";

export function DatasetsTab({ datasets, selected, setSelected, refresh, setError }) {
  const [showCreate, setShowCreate] = useState(false);
  const [seeding, setSeeding] = useState(false);

  async function handleCreate(e) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    let entries = [];
    try {
      const raw = form.get("entries") || "[]";
      entries = JSON.parse(raw);
    } catch {
      setError("Entries must be valid JSON array");
      return;
    }
    try {
      await postJson("/api/trials/datasets", {
        name: form.get("name"),
        type: form.get("type"),
        entries,
        tags: (form.get("tags") || "").split(",").map(t => t.trim()).filter(Boolean),
      });
      setShowCreate(false);
      await refresh();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleSeed() {
    setSeeding(true);
    try {
      await postJson("/api/trials/datasets/seed", {});
      await refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setSeeding(false);
    }
  }

  async function handleDelete(dsId) {
    if (!window.confirm("Delete this dataset?")) return;
    try {
      await api(`/api/trials/datasets/${dsId}`, { method: "DELETE" });
      setSelected(null);
      await refresh();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="w2-section" style={{ flex: 1 }}>
      <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
        <h2 style={{ margin: 0, fontSize: "1rem" }}>Datasets</h2>
        <div style={{ flex: 1 }} />
        <button className="w2-button" type="button" onClick={handleSeed} disabled={seeding}>
          <Sparkles size={14} /> {seeding ? "Seeding..." : "Seed Defaults"}
        </button>
        <button className="w2-button primary" type="button" onClick={() => setShowCreate(!showCreate)}>
          <Plus size={14} /> New Dataset
        </button>
      </div>

      {showCreate && (
        <div className="w2-card" style={{ border: "1px solid var(--cc-accent)" }}>
          <form onSubmit={handleCreate} style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
            <label style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>
              Name
              <input className="w2-input" name="name" required placeholder="My evaluation set" />
            </label>
            <label style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>
              Type
              <select className="w2-input" name="type" defaultValue="questions">
                <option value="questions">Questions</option>
                <option value="tasks">Tasks</option>
                <option value="documents">Documents</option>
                <option value="evaluation">Evaluation</option>
                <option value="scenarios">Scenarios</option>
              </select>
            </label>
            <label style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>
              Tags (comma-separated)
              <input className="w2-input" name="tags" placeholder="reasoning, math" />
            </label>
            <div />
            <label style={{ fontSize: "0.75rem", color: "var(--cc-muted)", gridColumn: "1 / -1" }}>
              Entries (JSON array)
              <textarea className="w2-input" name="entries" rows={4} placeholder='[{"prompt": "What is 2+2?", "expected": "4"}]' style={{ resize: "vertical", fontFamily: "monospace" }} />
            </label>
            <div style={{ gridColumn: "1 / -1", display: "flex", gap: "8px" }}>
              <button className="w2-button primary" type="submit"><Database size={14} /> Create Dataset</button>
              <button className="w2-button" type="button" onClick={() => setShowCreate(false)}>Cancel</button>
            </div>
          </form>
        </div>
      )}

      {datasets.map(ds => (
        <div key={ds.id} className="w2-card" style={{ cursor: "pointer", border: selected?.id === ds.id ? "1px solid var(--cc-accent)" : undefined }} onClick={() => setSelected(ds)}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <strong style={{ fontSize: "0.875rem" }}>{ds.name}</strong>
              <div style={{ fontSize: "0.6875rem", color: "var(--cc-muted)" }}>{ds.type} · {(ds.entries || []).length} entries · v{ds.version || 1}</div>
            </div>
            <div style={{ display: "flex", gap: "4px" }}>
              {(ds.tags || []).map(tag => (
                <span key={tag} style={{ fontSize: "0.6875rem", padding: "1px 8px", borderRadius: "999px", background: "var(--cc-surface)", border: "1px solid var(--cc-border)" }}>{tag}</span>
              ))}
            </div>
          </div>
          <button className="w2-button" type="button" onClick={(e) => { e.stopPropagation(); handleDelete(ds.id); }} style={{ fontSize: "0.75rem", padding: "4px 10px", color: "var(--ras-danger)", alignSelf: "flex-start" }}>
            <Trash2 size={12} /> Delete
          </button>
        </div>
      ))}

      {!datasets.length && (
        <div style={{ padding: "32px", textAlign: "center", color: "var(--cc-muted)", backgroundColor: "var(--cc-surface)", borderRadius: "8px" }}>
          No datasets yet. Click "Seed Defaults" to create starter evaluation sets.
        </div>
      )}
    </div>
  );
}
