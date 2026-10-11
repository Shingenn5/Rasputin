import { useState } from "react";
import { Zap } from "lucide-react";
import { postJson } from "../../api/client.js";
import { statusColor } from "./trialPresentation.jsx";

export function PromptLabTab({ models, refresh, setError }) {
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);
  const selectable = (models || []).filter(m => m.key !== "local-embeddings").slice(0, 8);

  async function handleRun(e) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    setRunning(true);
    setError("");
    setResult(null);
    try {
      const exp = await postJson("/api/trials/experiments", {
        name: `Prompt Lab: ${form.get("promptA")?.slice(0, 40)}...`,
        type: "prompt",
        config: {
          promptA: form.get("promptA"),
          promptB: form.get("promptB"),
          modelKey: form.get("modelKey") || "dry-run",
        },
      });
      const ran = await postJson(`/api/trials/experiments/${exp.id}/run`, {});
      setResult(ran);
      await refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setRunning(false);
    }
  }

  const runs = result?.runs || [];
  const lastRun = runs[0];
  const outputs = lastRun?.outputs || [];

  return (
    <div className="w2-section" style={{ flex: 1 }}>
      <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
        <h2 style={{ margin: 0, fontSize: "1rem" }}>Prompt Lab</h2>
        <span style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>A/B test prompts against the same model</span>
      </div>

      <div className="w2-card">
        <form onSubmit={handleRun} style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
          <label style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>
            Prompt A
            <textarea className="w2-input" name="promptA" rows={4} required placeholder="Write the first version of your prompt..." style={{ resize: "vertical" }} />
          </label>
          <label style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>
            Prompt B
            <textarea className="w2-input" name="promptB" rows={4} required placeholder="Write an alternative version..." style={{ resize: "vertical" }} />
          </label>
          <label style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>
            Model
            <select className="w2-input" name="modelKey" defaultValue="dry-run">
              {selectable.map(m => <option key={m.key} value={m.key}>{m.name || m.model || m.key}</option>)}
              <option value="dry-run">Dry Run</option>
            </select>
          </label>
          <div style={{ display: "flex", alignItems: "flex-end" }}>
            <button className="w2-button primary" type="submit" disabled={running} style={{ width: "100%" }}>
              <Zap size={14} /> {running ? "Running A/B Test..." : "Run A/B Test"}
            </button>
          </div>
        </form>
      </div>

      {/* Results */}
      {outputs.length >= 2 && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
          {outputs.map((out, i) => (
            <div key={i} className="w2-card">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <strong style={{ fontSize: "0.875rem" }}>Prompt {out.label || (i === 0 ? "A" : "B")}</strong>
                <span style={{ fontSize: "0.6875rem", color: statusColor(out.status) }}>{out.latencyMs || out.latency_ms}ms</span>
              </div>
              <div style={{ fontSize: "0.75rem", color: "var(--cc-muted)", fontStyle: "italic", borderBottom: "1px solid var(--cc-border)", paddingBottom: "8px" }}>
                {out.prompt?.slice(0, 100)}{(out.prompt?.length || 0) > 100 ? "..." : ""}
              </div>
              <div style={{ fontSize: "0.8125rem", whiteSpace: "pre-wrap", maxHeight: "300px", overflow: "auto" }}>
                {out.error || out.text || "No output"}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
