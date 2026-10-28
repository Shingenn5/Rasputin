import React, { useEffect, useState } from "react";
import { FlaskConical, Play, RefreshCw, Square } from "lucide-react";
import { api, postJson } from "../../api/client.js";
import { Button } from "../../components/ui/button.jsx";
import "./workstation.css";

export function TrainingView({ view }) {
  const [state, setState] = useState(null);
  const [form, setForm] = useState({ name: "My first fine-tune", modelPath: "", dataset: "", maxSteps: 60, learningRate: 0.0002, rank: 16, maxLength: 1024 });
  const [preflight, setPreflight] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  async function refresh() { setState(await api("/api/training")); }
  useEffect(() => { refresh().catch((e) => setError(e.message)); }, []);
  const active = state?.jobs?.some((j) => ["starting", "running", "stopping"].includes(j.status));
  useEffect(() => {
    if (!active) return undefined;
    const timer = window.setInterval(() => api("/api/training/jobs").then((result) => setState((current) => ({ ...current, jobs: result.jobs }))).catch((e) => setError(e.message)), 2500);
    return () => window.clearInterval(timer);
  }, [active]);
  function update(key, value) { setForm((current) => ({ ...current, [key]: value })); setPreflight(null); }
  async function perform(action, path, body = form) {
    setBusy(action); setError("");
    try {
      const result = await postJson(path, body);
      if (action === "preflight") setPreflight(result);
      else {
        setPreflight(null);
        const result = await api("/api/training/jobs");
        setState((current) => ({ ...current, jobs: result.jobs }));
      }
    } catch (e) { setError(e.message); } finally { setBusy(""); }
  }
  async function readDataset(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    if (file.size > 4 * 1024 * 1024) { setError("Choose a JSONL dataset under 4 MB."); return; }
    try { update("dataset", await file.text()); setError(""); } catch { setError("Unable to read this dataset."); }
  }
  return <section className={`app-view workstation-view ${view === "training" ? "active" : ""}`} data-app-view="training" id="trainingView">
    <header className="workstation-heading"><div><span className="workstation-eyebrow">BUILD</span><h1>Training</h1><p>Teach a local model your examples. Keep the weights and data on your machine.</p></div><FlaskConical aria-hidden="true" size={28} /></header>
    {error && <p role="alert" className="workstation-error">{error}</p>}
    <div className="workstation-grid">
      <form className="workstation-card" onSubmit={(e) => { e.preventDefault(); perform("preflight", "/api/training/preflight"); }}>
        <h2>New fine-tune</h2><p>Supervised LoRA training creates an adapter from original Transformers safetensors weights. GGUF inference files cannot be trained here.</p>
        <label className="workstation-field">Run name<input required maxLength={100} value={form.name} onChange={(e) => update("name", e.target.value)} /></label>
        <label className="workstation-field">Local base model directory<input required value={form.modelPath} onChange={(e) => update("modelPath", e.target.value)} placeholder="Absolute path to original model weights" /></label>
        <label className="workstation-field">Import JSONL dataset<input type="file" accept=".jsonl,.json" onChange={readDataset} /></label>
        <div className="workstation-field"><label htmlFor="training-examples">Training examples</label><textarea id="training-examples" required rows={7} maxLength={4194304} value={form.dataset} onChange={(e) => update("dataset", e.target.value)} placeholder={'{"text":"Question: What is Rasputin? Answer: A local AI workstation."}\n{"text":"Question: Where does my data stay? Answer: On this machine."}'} /></div>
        <p className="workstation-muted">One JSON object per line with a text field. At least 2 examples; up to 10,000 examples and 4 MB. Data is retained with the run in local training storage.</p>
        <details><summary>Training settings</summary><div className="workstation-grid workstation-settings">{[["maxSteps", "Training steps", 1, 10000, 1], ["learningRate", "Learning rate", 0.000001, 0.01, 0.000001], ["rank", "LoRA rank", 4, 64, 1], ["maxLength", "Sequence length", 128, 8192, 1]].map(([key, label, min, max, step]) => <label className="workstation-field" key={key}>{label}<input type="number" required min={min} max={max} step={step} value={form[key]} onChange={(e) => update(key, Number(e.target.value))} /></label>)}</div></details>
        <div className="workstation-actions"><Button variant="outline" type="submit" disabled={!!busy || active}>Check readiness</Button><Button type="button" disabled={!!busy || active || !preflight?.ready} onClick={() => perform("start", "/api/training/jobs")}><Play />Start fine-tune</Button></div>
        {preflight && <div className="workstation-notice" role="status">{preflight.ready ? `${preflight.examples} examples validated. Ready to start; CUDA will be checked by the worker.` : <ul>{preflight.blockers.map((b) => <li key={b}>{b}</li>)}</ul>}</div>}
      </form>
      <div className="workstation-stack"><section className="workstation-card"><h2>Training runtime</h2>{!state ? <p>Checking runtime…</p> : <><span className="workstation-status">{state.capability.ready ? "Dependencies available" : "Setup required"}</span><ul>{state.capability.blockers.map((b) => <li key={b}>{b}</li>)}</ul><p>Requires a CUDA GPU and a compatible separate PyTorch, Transformers, PEFT and TRL environment. Stop inference models before training. No packages or weights are downloaded automatically.</p><p className="workstation-muted">A maintainer provisions the runtime for this build. Packaged training is available only after that runtime has been configured.</p></>}<Button variant="ghost" onClick={() => refresh().catch((e) => setError(e.message))}><RefreshCw />Check again</Button></section>
        <section className="workstation-card"><h2>Runs</h2>{!state?.jobs?.length && <p className="workstation-muted">Your training runs will appear here with progress and status.</p>}<ul className="workstation-list">{state?.jobs?.map((job) => <li key={job.id}><div><strong>{job.name}</strong><small>{job.status} · {job.step}/{job.maxSteps} steps{Number.isFinite(job.loss) ? ` · loss ${job.loss.toFixed(4)}` : ""}</small><p>{job.message}</p>{job.status === "completed" && <a href={`/api/training/jobs/${encodeURIComponent(job.id)}/adapter`}>Download adapter</a>}</div>{["starting", "running"].includes(job.status) && <Button variant="outline" disabled={!!busy} onClick={() => perform("cancel", `/api/training/jobs/${job.id}/cancel`, {})}><Square />Stop</Button>}</li>)}</ul><p className="workstation-muted">Adapters require their original base model. Automatic GGUF merging and registration are not available.</p></section>
      </div>
    </div>
  </section>;
}
