import { useState, useMemo } from "react";
import { FlaskConical, Eye, Play, Plus, RefreshCw, Trash2 } from "lucide-react";
import { api, postJson } from "../../api/client.js";
import { EXP_TYPES, statusIcon, fmtDate, statusColor } from "./trialPresentation.jsx";

export function ExperimentsTab({ experiments, models, datasets, selected, setSelected, refresh, setError, legacyTrials, legacyStatus, runTrialCompare, revealTrial, saveTrialRoute, modeModelOverrides }) {
  const [showCreate, setShowCreate] = useState(false);
  const [showBlind, setShowBlind] = useState(false);
  const [creating, setCreating] = useState(false);
  const [filter, setFilter] = useState("all");
  const selectable = (models || []).filter(m => m.key !== "local-embeddings").slice(0, 8);

  const displayed = useMemo(() => {
    if (filter === "all") return experiments;
    return experiments.filter(e => e.status === filter);
  }, [filter, experiments]);

  async function handleCreate(e) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    setCreating(true);
    setError("");
    try {
      const modelKeys = form.getAll("modelKeys");
      const config = { prompt: form.get("prompt") || "", modelKeys, datasetId: form.get("datasetId") || "" };
      if (form.get("type") === "prompt") {
        config.promptA = form.get("promptA") || "";
        config.promptB = form.get("promptB") || "";
        config.modelKey = form.get("modelKey") || modelKeys[0] || "dry-run";
      }
      await postJson("/api/trials/experiments", {
        name: form.get("name"),
        type: form.get("type"),
        config,
        tags: (form.get("tags") || "").split(",").map(t => t.trim()).filter(Boolean),
      });
      setShowCreate(false);
      await refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setCreating(false);
    }
  }

  async function handleRun(expId) {
    setError("");
    try {
      await postJson(`/api/trials/experiments/${expId}/run`, {});
      await refresh();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleBlindCreate(e) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    setCreating(true);
    setError("");
    try {
      await postJson("/api/trials/blind-comparisons", {
        name: form.get("name"),
        prompts: String(form.get("prompts") || "").split(/\n+/).map(value => value.trim()).filter(Boolean),
        modelKeys: form.getAll("modelKeys"),
        repetitions: Number(form.get("repetitions") || 3),
        seed: form.get("seed") || "rasputin",
        mission: form.get("mission") || "chat",
      });
      setShowBlind(false);
      await refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setCreating(false);
    }
  }

  async function handleBlindReveal(expId) {
    try {
      const revealed = await postJson(`/api/trials/blind-comparisons/${expId}/reveal`, {});
      setSelected(revealed);
      await refresh();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleDelete(expId) {
    if (!window.confirm("Delete this experiment?")) return;
    try {
      await api(`/api/trials/experiments/${expId}`, { method: "DELETE" });
      setSelected(null);
      await refresh();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="w2-section" style={{ flex: 1 }}>
      {/* Header */}
      <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
        <h2 style={{ margin: 0, fontSize: "1rem" }}>Experiments</h2>
        <div style={{ flex: 1 }} />
        {["all", "draft", "running", "completed", "failed"].map(f => (
          <button key={f} className={`w2-button ${filter === f ? "primary" : ""}`} type="button" onClick={() => setFilter(f)} style={{ fontSize: "0.75rem", padding: "4px 10px", textTransform: "capitalize" }}>
            {f} {f === "all" ? `(${experiments.length})` : `(${experiments.filter(e => e.status === f).length})`}
          </button>
        ))}
        <button className="w2-button primary" type="button" onClick={() => setShowCreate(!showCreate)}>
          <Plus size={14} /> New Experiment
        </button>
        <button className="w2-button" type="button" onClick={() => setShowBlind(!showBlind)}>
          <Eye size={14} /> New Blind Compare
        </button>
      </div>

      {showBlind && (
        <div className="w2-card" data-testid="blind-compare-form" style={{ border: "1px solid var(--cc-accent)" }}>
          <h3 style={{ margin: 0, fontSize: "0.875rem" }}>Repeatable Blind Comparison</h3>
          <p style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>Model identities stay hidden until reveal. Every candidate receives the same prompts and generation settings.</p>
          <form onSubmit={handleBlindCreate} style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
            <label>Name<input className="w2-input" name="name" required placeholder="Coding mission comparison" /></label>
            <label>Mission<input className="w2-input" name="mission" defaultValue="coding" /></label>
            <label style={{ gridColumn: "1 / -1" }}>Prompts, one per line<textarea className="w2-input" name="prompts" required rows={4} /></label>
            <label>Repetitions<input className="w2-input" name="repetitions" type="number" min="2" max="10" defaultValue="3" /></label>
            <label>Saved seed<input className="w2-input" name="seed" defaultValue="rasputin" /></label>
            <fieldset style={{ gridColumn: "1 / -1", border: "1px solid var(--cc-border)", padding: "8px" }}>
              <legend>Models</legend>
              {selectable.map(model => (
                <label key={model.key} style={{ marginRight: "12px" }}>
                  <input type="checkbox" name="modelKeys" value={model.key} /> {model.name || model.model || model.key}
                </label>
              ))}
            </fieldset>
            <div style={{ gridColumn: "1 / -1", display: "flex", gap: "8px" }}>
              <button className="w2-button primary" type="submit" disabled={creating}>{creating ? "Running…" : "Run blind comparison"}</button>
              <button className="w2-button" type="button" onClick={() => setShowBlind(false)}>Cancel</button>
            </div>
          </form>
        </div>
      )}

      {/* Create Form */}
      {showCreate && (
        <div className="w2-card" style={{ border: "1px solid var(--cc-accent)" }}>
          <h3 style={{ margin: 0, fontSize: "0.875rem" }}>Create Experiment</h3>
          <form onSubmit={handleCreate} style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
            <label style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>
              Name
              <input className="w2-input" name="name" required placeholder="My model benchmark" />
            </label>
            <label style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>
              Type
              <select className="w2-input" name="type" defaultValue="model">
                {EXP_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </label>
            <label style={{ fontSize: "0.75rem", color: "var(--cc-muted)", gridColumn: "1 / -1" }}>
              Prompt
              <textarea className="w2-input" name="prompt" rows={2} placeholder="Enter a test prompt..." style={{ resize: "vertical" }} />
            </label>
            <label style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>
              Dataset (optional)
              <select className="w2-input" name="datasetId">
                <option value="">None</option>
                {datasets.map(ds => <option key={ds.id} value={ds.id}>{ds.name} ({ds.entries?.length || 0} entries)</option>)}
              </select>
            </label>
            <label style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>
              Tags (comma-separated)
              <input className="w2-input" name="tags" placeholder="benchmark, coding" />
            </label>
            <fieldset style={{ gridColumn: "1 / -1", border: "1px solid var(--cc-border)", borderRadius: "6px", padding: "8px" }}>
              <legend style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>Models</legend>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                {selectable.map(m => (
                  <label key={m.key} style={{ display: "flex", gap: "4px", alignItems: "center", fontSize: "0.8125rem" }}>
                    <input type="checkbox" name="modelKeys" value={m.key} />
                    {m.name || m.model || m.key}
                  </label>
                ))}
                {!selectable.length && <span style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>No models registered yet</span>}
              </div>
            </fieldset>
            <div style={{ gridColumn: "1 / -1", display: "flex", gap: "8px" }}>
              <button className="w2-button primary" type="submit" disabled={creating}>
                <FlaskConical size={14} /> {creating ? "Creating..." : "Create Experiment"}
              </button>
              <button className="w2-button" type="button" onClick={() => setShowCreate(false)}>Cancel</button>
            </div>
          </form>
        </div>
      )}

      {/* Experiment List */}
      {displayed.map(exp => (
        <div key={exp.id} className={`w2-card ${selected?.id === exp.id ? "" : ""}`} style={{ cursor: "pointer", border: selected?.id === exp.id ? "1px solid var(--cc-accent)" : undefined }} onClick={() => setSelected(exp)}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
              {statusIcon(exp.status)}
              <div>
                <strong style={{ fontSize: "0.875rem" }}>{exp.name}</strong>
                <div style={{ fontSize: "0.6875rem", color: "var(--cc-muted)" }}>
                  {exp.type} · {fmtDate(exp.createdAt)}
                </div>
              </div>
            </div>
            <div style={{ display: "flex", gap: "6px" }}>
              <span style={{ fontSize: "0.6875rem", padding: "2px 10px", borderRadius: "999px", background: `color-mix(in srgb, ${statusColor(exp.status)} 15%, var(--cc-surface))`, color: statusColor(exp.status), fontWeight: 600, textTransform: "capitalize" }}>
                {exp.status}
              </span>
            </div>
          </div>
          {exp.metrics && Object.keys(exp.metrics).length > 0 && (
            <div style={{ display: "flex", gap: "16px", fontSize: "0.75rem", color: "var(--cc-muted)" }}>
              {exp.metrics.totalDurationMs != null && <span>Duration: {exp.metrics.totalDurationMs}ms</span>}
              {exp.metrics.modelCount != null && <span>Models: {exp.metrics.modelCount}</span>}
              {exp.metrics.successCount != null && <span>Success: {exp.metrics.successCount}</span>}
            </div>
          )}
          <div style={{ display: "flex", gap: "6px" }}>
            {exp.status === "draft" && (
              <button className="w2-button primary" type="button" onClick={(e) => { e.stopPropagation(); handleRun(exp.id); }} style={{ fontSize: "0.75rem", padding: "4px 10px" }}>
                <Play size={12} /> Run
              </button>
            )}
            {exp.status === "completed" && (
              exp.type === "blind_compare" && !exp.config?.revealed ? (
                <button className="w2-button primary" type="button" onClick={(e) => { e.stopPropagation(); handleBlindReveal(exp.id); }} style={{ fontSize: "0.75rem", padding: "4px 10px" }}>
                  <Eye size={12} /> Reveal identities
                </button>
              ) : exp.type !== "blind_compare" && (
              <button className="w2-button" type="button" onClick={(e) => { e.stopPropagation(); handleRun(exp.id); }} style={{ fontSize: "0.75rem", padding: "4px 10px" }}>
                <RefreshCw size={12} /> Re-run
              </button>
              )
            )}
            <button className="w2-button" type="button" onClick={(e) => { e.stopPropagation(); handleDelete(exp.id); }} style={{ fontSize: "0.75rem", padding: "4px 10px", color: "var(--ras-danger)" }}>
              <Trash2 size={12} />
            </button>
          </div>
        </div>
      ))}

      {!displayed.length && (
        <div style={{ padding: "32px", textAlign: "center", color: "var(--cc-muted)", backgroundColor: "var(--cc-surface)", borderRadius: "8px" }}>
          No experiments yet. Create one to start measuring.
        </div>
      )}
    </div>
  );
}
