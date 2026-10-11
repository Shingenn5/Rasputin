import { useState, useEffect } from "react";
import { Loader2, Play, Trophy } from "lucide-react";
import { api, postJson } from "../../api/client.js";
import { fmtDate } from "./trialPresentation.jsx";

export function CodingTrialTab({ models, setError }) {
  const [runs, setRuns] = useState([]);
  const [running, setRunning] = useState(false);
  const [status, setStatus] = useState("");
  const selectable = (models || []).filter(m => m.key !== "local-embeddings").slice(0, 8);

  async function loadRuns() {
    try {
      const data = await api("/api/trials");
      setRuns((data.runs || []).filter(r => r.kind === "coding"));
    } catch (err) {
      setError(err.message);
    }
  }
  useEffect(() => { loadRuns(); }, []);

  async function handleRun(e) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const modelKeys = form.getAll("modelKeys");
    setRunning(true);
    setStatus("");
    try {
      await postJson("/api/trials/coding-compare", {
        objective: form.get("objective") || "",
        code: form.get("code") || "",
        tests: form.get("tests") || "",
        modelKeys,
      });
      e.target.reset();
      await loadRuns();
    } catch (err) {
      setError(err.message);
    } finally {
      setRunning(false);
    }
  }

  async function handleReveal(runId) {
    try {
      await postJson(`/api/trials/${runId}/reveal`, {});
      await loadRuns();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handlePin(runId, outputId) {
    try {
      const result = await postJson(`/api/trials/${runId}/pin-role`, { outputId, role: "coder" });
      setStatus(`Pinned ${result.route.modelName} to the coder role — code mode now routes to it.`);
      await loadRuns();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="w2-section" style={{ flex: 1 }}>
      <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
        <h2 style={{ margin: 0, fontSize: "1rem" }}>Coding Trial</h2>
        <span style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>
          Blind-compare models on a coding subtask. Outputs are scored objectively; reveal, then pin the winner to the coder role.
        </span>
      </div>

      <div className="w2-card">
        <form onSubmit={handleRun} style={{ display: "grid", gap: "8px" }}>
          <label style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>
            Objective
            <textarea className="w2-input" name="objective" rows={2} required placeholder="Implement add(a, b) returning the sum." style={{ resize: "vertical" }} />
          </label>
          <label style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>
            Starting Code (optional)
            <textarea className="w2-input" name="code" rows={4} placeholder="def add(a, b):\n    ..." style={{ resize: "vertical", fontFamily: "monospace" }} />
          </label>
          <label style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>
            Tests (optional — plain asserts, run against each candidate when shell execution is permitted)
            <textarea className="w2-input" name="tests" rows={3} placeholder="assert add(2, 3) == 5" style={{ resize: "vertical", fontFamily: "monospace" }} />
          </label>
          <fieldset style={{ border: "1px solid var(--cc-border)", borderRadius: "6px", padding: "8px" }}>
            <legend style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>Models (up to 4, blind-labeled A-D)</legend>
            {selectable.map(m => (
              <label key={m.key} style={{ display: "flex", gap: "4px", alignItems: "center", fontSize: "0.8125rem" }}>
                <input type="checkbox" name="modelKeys" value={m.key} />
                {m.name || m.model || m.key}
              </label>
            ))}
            {!selectable.length && <span style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>No models registered yet</span>}
          </fieldset>
          <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
            <button className="w2-button primary" type="submit" disabled={running}>
              {running ? <Loader2 size={14} style={{ animation: "spin 1s linear infinite" }} /> : <Play size={14} />}
              {running ? "Running trial..." : "Run Blind Trial"}
            </button>
            {status && <span style={{ fontSize: "0.75rem", color: "var(--ras-safe)" }}>{status}</span>}
          </div>
        </form>
      </div>

      {runs.map(run => (
        <div key={run.id} className="w2-card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "8px" }}>
            <div>
              <strong style={{ fontSize: "0.875rem" }}>{run.objective || run.prompt}</strong>
              <div style={{ fontSize: "0.6875rem", color: "var(--cc-muted)" }}>
                {fmtDate(run.createdAt)} · tests {run.testsExecuted ? "executed" : "not executed"}
                {run.suggestedLabel && <> · top score: <strong>{run.suggestedLabel}</strong></>}
              </div>
            </div>
            {!run.revealed && (
              <button className="w2-button" type="button" onClick={() => handleReveal(run.id)}>Reveal Models</button>
            )}
          </div>
          <div style={{ display: "grid", gap: "8px", marginTop: "8px" }}>
            {(run.outputs || []).map(output => (
              <div key={output.id} style={{ border: "1px solid var(--cc-border)", borderRadius: "6px", padding: "8px" }}>
                <div style={{ display: "flex", gap: "10px", alignItems: "center", fontSize: "0.8125rem", flexWrap: "wrap" }}>
                  <strong>{output.label}</strong>
                  {run.revealed && <span style={{ color: "var(--cc-accent)" }}>{output.modelKey}</span>}
                  <span>score {output.scoring?.score ?? "—"}</span>
                  <span style={{ color: output.scoring?.syntaxOk ? "var(--ras-safe)" : "var(--ras-danger)" }}>
                    syntax {output.scoring?.syntaxOk ? "ok" : "invalid"}
                  </span>
                  {output.scoring?.testsRan && (
                    <span style={{ color: output.scoring?.testsPassed ? "var(--ras-safe)" : "var(--ras-danger)" }}>
                      tests {output.scoring?.testsPassed ? "passed" : "failed"}
                    </span>
                  )}
                  <span style={{ color: "var(--cc-muted)" }}>{output.latencyMs} ms</span>
                  <div style={{ flex: 1 }} />
                  {run.revealed && output.status === "done" && (
                    <button className="w2-button" type="button" onClick={() => handlePin(run.id, output.id)} style={{ fontSize: "0.75rem", padding: "4px 10px" }}>
                      <Trophy size={12} /> Pin to coder role
                    </button>
                  )}
                </div>
                {output.status === "error" && <div style={{ fontSize: "0.75rem", color: "var(--ras-danger)" }}>{output.error}</div>}
                {output.text && (
                  <pre style={{ fontSize: "0.6875rem", maxHeight: "140px", overflow: "auto", marginTop: "6px", marginBottom: 0 }}>{output.text}</pre>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}

      {!runs.length && (
        <div style={{ padding: "32px", textAlign: "center", color: "var(--cc-muted)", backgroundColor: "var(--cc-surface)", borderRadius: "8px" }}>
          No coding trials yet. Pick two or more models and run a blind comparison.
        </div>
      )}
    </div>
  );
}
